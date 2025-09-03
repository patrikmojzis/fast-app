from __future__ import annotations

import asyncio
import json
import os
import pickle
import signal
import time
from dataclasses import dataclass, field
import sys
from typing import Any, Callable, Optional, Set

import aio_pika
from aio_pika import ExchangeType, Message

from fast_app.utils.queue_utils import import_from_path, boot_if_needed
from fast_app.core.context import context


# Environment configuration with sensible defaults
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
JOBS_QUEUE = os.getenv("ASYNC_FARM_JOBS_QUEUE", "async_farm.jobs")
CONTROL_EXCHANGE = os.getenv("ASYNC_FARM_CONTROL_EXCHANGE", "async_farm.control")

CONCURRENCY = int(os.getenv("PREFETCH_PER_WORKER", os.getenv("ASYNC_FARM_CONCURRENCY", "10")))
HEARTBEAT_INTERVAL_S = int(os.getenv("HEARTBEAT_INTERVAL_S", "5"))
SOFT_TIMEOUT_S = int(os.getenv("SOFT_TIMEOUT_S", "30"))
HARD_TIMEOUT_S = int(os.getenv("HARD_TIMEOUT_S", "60"))
WORKER_SHUTDOWN_GRACE_S = int(os.getenv("WORKER_SHUTDOWN_GRACE_S", "15"))


@dataclass
class AckGuard:
    acked: bool = False


class AsyncFarmWorker:
    """RabbitMQ worker executing callables with bounded asyncio concurrency."""

    def __init__(self, manager_id: Optional[str] = None) -> None:
        self.manager_id = manager_id or os.getenv("MANAGER_ID") or ""
        self.worker_start_ts = time.time()
        # Include start_ts to avoid PID reuse collisions
        self.worker_id = f"worker_{os.getpid()}_{int(self.worker_start_ts)}"

        self.connection: Optional[Any] = None
        self.channel: Optional[Any] = None
        self.jobs_queue: Optional[aio_pika.Queue] = None
        self.control_exchange: Optional[aio_pika.Exchange] = None
        self.control_queue: Optional[aio_pika.Queue] = None
        self.consumer_tag: Optional[str] = None

        self.active_tasks: Set[asyncio.Task[Any]] = set()
        self.shutdown_requested: bool = False
        self.hard_timeout_triggered: bool = False

    # ------------------------- lifecycle -------------------------
    async def start(self) -> None:
        self.connection = await aio_pika.connect_robust(RABBITMQ_URL)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=CONCURRENCY)

        # Jobs queue (durable)
        self.jobs_queue = await self.channel.declare_queue(JOBS_QUEUE, durable=True)

        # Control exchange + queues
        self.control_exchange = await self.channel.declare_exchange(CONTROL_EXCHANGE, ExchangeType.DIRECT, durable=True)

        # Worker command queue (exclusive per worker)
        self.control_queue = await self.channel.declare_queue(
            f"async_farm.control.worker.{self.worker_id}", exclusive=True, auto_delete=True
        )
        await self.control_queue.bind(self.control_exchange, routing_key=f"worker.{self.worker_id}")

        # Start consumers and heartbeat
        self.consumer_tag = await self.jobs_queue.consume(self.on_message, no_ack=False)

        loop = asyncio.get_running_loop()
        try:
            loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(self.request_shutdown()))
            loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(self.request_shutdown()))
        except NotImplementedError:
            # Signals may be unavailable (e.g., on Windows or non-main thread)
            pass

        try:
            await asyncio.gather(
                self.heartbeat_loop(),
                self.control_loop(),
                self.drain_loop(),
                self.supervisor_watchdog_loop(),
            )
        finally:
            await self.request_shutdown()

    async def request_shutdown(self, grace_s: Optional[int] = None) -> None:
        if self.shutdown_requested:
            return
        self.shutdown_requested = True
        if self.consumer_tag and self.channel:
            try:
                await self.channel.basic_cancel(self.consumer_tag)
            except Exception:
                pass
        # Wait for tasks to drain with grace
        deadline = time.time() + float(grace_s or WORKER_SHUTDOWN_GRACE_S)
        while self.active_tasks and time.time() < deadline:
            await asyncio.sleep(0.2)

    async def close_connections(self) -> None:
        try:
            if self.channel:
                await self.channel.close()
        finally:
            if self.connection:
                await self.connection.close()

    # ------------------------- consumers -------------------------
    async def on_message(self, message: aio_pika.IncomingMessage) -> None:
        if self.shutdown_requested:
            await message.nack(requeue=True)
            return

        task = asyncio.create_task(self.handle_message_with_timeouts(message))
        self.active_tasks.add(task)
        task.add_done_callback(lambda _: self.active_tasks.discard(task))

    def task_done(self, message: aio_pika.IncomingMessage, task: "asyncio.Task[Any]") -> None:
        return

    async def control_loop(self) -> None:
        assert self.control_queue is not None
        async with self.control_queue.iterator() as queue_iter:
            async for message in queue_iter:
                try:
                    payload = json.loads(message.body.decode("utf-8"))
                    if payload.get("type") == "shutdown":
                        await self.request_shutdown(grace_s=int(payload.get("grace_s", WORKER_SHUTDOWN_GRACE_S)))
                finally:
                    await message.ack()
                if self.shutdown_requested:
                    break

    async def heartbeat_loop(self) -> None:
        assert self.control_exchange is not None
        routing_keys = [f"supervisor.{self.manager_id}"] if self.manager_id else ["supervisor"]
        while not self.shutdown_requested:
            body = json.dumps(
                {
                    "type": "heartbeat",
                    "manager_id": self.manager_id,
                    "worker_id": self.worker_id,
                    "pid": os.getpid(),
                    "start_ts": self.worker_start_ts,
                    "active_tasks": len(self.active_tasks),
                    "ts": time.time(),
                }
            ).encode("utf-8")
            for rk in routing_keys:
                try:
                    await self.control_exchange.publish(
                        Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
                        routing_key=rk,
                    )
                except Exception as e:
                    # Best-effort heartbeat; ignore failures
                    print(f"Error publishing heartbeat: {e}")
            await asyncio.sleep(HEARTBEAT_INTERVAL_S)

    async def drain_loop(self) -> None:
        # Keep the worker alive until shutdown is requested and tasks drained
        try:
            while not self.shutdown_requested:
                await asyncio.sleep(0.5)
            # drain
            while self.active_tasks:
                await asyncio.sleep(0.2)
        finally:
            await self.close_connections()

    async def supervisor_watchdog_loop(self) -> None:
        # Watch for supervisor heartbeat; if supervisor stops sending recent ts, shutdown
        if not self.manager_id:
            return
        assert self.channel is not None
        assert self.control_exchange is not None

        queue = await self.channel.declare_queue(
            f"async_farm.control.worker_watchdog.{self.worker_id}", exclusive=True, auto_delete=True
        )
        await queue.bind(self.control_exchange, routing_key=f"supervisor_heartbeat.{self.manager_id}")

        timeout_s = 3 * max(1, HEARTBEAT_INTERVAL_S)

        async with queue.iterator() as it:
            while not self.shutdown_requested:
                try:
                    message = await asyncio.wait_for(it.__anext__(), timeout=timeout_s)
                except asyncio.TimeoutError:
                    await self.request_shutdown()
                    break
                try:
                    payload = json.loads(message.body.decode("utf-8"))
                    if payload.get("type") == "supervisor_heartbeat":
                        try:
                            hb_ts = float(payload.get("ts", time.time()))
                        except Exception:
                            hb_ts = time.time()
                        if time.time() - hb_ts >= timeout_s:
                            await message.ack()
                            await self.request_shutdown()
                            break
                finally:
                    await message.ack()

    # ------------------------- task handling -------------------------
    async def handle_message_with_timeouts(self, message: aio_pika.IncomingMessage) -> None:
        try:
            await self.run_message_with_timeouts(message)
        except Exception:
            guard = AckGuard()
            await self.ack_once(message, guard)

    async def run_message_with_timeouts(self, message: aio_pika.IncomingMessage) -> None:
        payload = pickle.loads(message.body)

        func_path = payload.get("func_path")
        args_pickled = payload.get("args_pickled", pickle.dumps((), protocol=pickle.HIGHEST_PROTOCOL))
        kwargs_pickled = payload.get("kwargs_pickled", pickle.dumps({}, protocol=pickle.HIGHEST_PROTOCOL))
        if payload.get("args_compressed"):
            import zlib
            args_pickled = zlib.decompress(args_pickled)
        if payload.get("kwargs_compressed"):
            import zlib
            kwargs_pickled = zlib.decompress(kwargs_pickled)
        args = pickle.loads(args_pickled)
        kwargs = pickle.loads(kwargs_pickled)

        # Install context snapshot and boot if provided
        try:
            snap = payload.get("ctx_snapshot") or {}
            if isinstance(snap, dict):
                context.install(snap)
        except Exception:
            # Do not fail task on context installation issues
            pass

        boot_args = payload.get("boot_args") or {}
        try:
            boot_if_needed(boot_args)
        except Exception:
            # Best-effort boot
            pass

        func: Callable[..., Any]
        if not func_path:
            # Reject non-importable tasks for safety
            await self.ack_once(message, AckGuard())
            return
        func = import_from_path(func_path)

        async def run_callable() -> Any:
            return await func(*args, **kwargs)

        # Implement soft/hard timeouts
        task = asyncio.create_task(run_callable())

        # Per-message header overrides
        headers = (message.headers or {})
        soft_timeout_s = self.safe_int(headers.get("soft_timeout_s"), SOFT_TIMEOUT_S, 0, 24 * 3600)
        hard_timeout_s = self.safe_int(headers.get("hard_timeout_s"), HARD_TIMEOUT_S, 1, 48 * 3600)
        if hard_timeout_s <= soft_timeout_s:
            hard_timeout_s = soft_timeout_s + 1

        guard = AckGuard()

        async def soft_timeout() -> None:
            for _ in range(soft_timeout_s):
                if task.done():
                    return
                await asyncio.sleep(1)

            if not task.done():
                task.cancel()

        async def hard_timeout() -> None:
            for _ in range(hard_timeout_s):
                if task.done():
                    return
                await asyncio.sleep(1)

            if not task.done() and not self.hard_timeout_triggered:
                self.hard_timeout_triggered = True
                await self.ack_once(message, guard)
                await self.publish_stuck_task_event()
                await self.request_shutdown(120)  # 2 minutes
                sys.exit(1)

        soft_t = asyncio.create_task(soft_timeout())
        hard_t = asyncio.create_task(hard_timeout())

        try:
            await task
            await self.ack_once(message, guard)
        except asyncio.CancelledError:
            # Soft timeout cancellation
            await self.ack_once(message, guard)
        except Exception:
            # User code raised; ack to avoid poison loop
            await self.ack_once(message, guard)
        finally:
            soft_t.cancel()
            hard_t.cancel()

    async def publish_stuck_task_event(self) -> None:
        try:
            if self.control_exchange is None:
                return
            routing_key = f"supervisor.{self.manager_id}" if self.manager_id else "supervisor"
            body = json.dumps({
                "type": "stuck_task",
                "worker_id": self.worker_id,
                "pid": os.getpid(),
                "start_ts": self.worker_start_ts,
                "ts": time.time(),
            }).encode("utf-8")
            await self.control_exchange.publish(
                Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
                routing_key=routing_key,
            )
        except Exception:
            pass

    async def ack_once(self, message: aio_pika.IncomingMessage, guard: AckGuard) -> None:
        if guard.acked:
            return
        try:
            await message.ack()
            guard.acked = True
        except Exception:
            pass

    @staticmethod
    def safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            iv = int(value)
        except Exception:
            return default
        if iv < minimum:
            return minimum
        if iv > maximum:
            return maximum
        return iv


def _run() -> None:
    worker = AsyncFarmWorker(manager_id=os.getenv("MANAGER_ID"))
    asyncio.run(worker.start())


if __name__ == "__main__":
    _run()


