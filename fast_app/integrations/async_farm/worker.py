from __future__ import annotations

import asyncio
import json
import os
import pickle
import signal
import time
import logging
from dataclasses import dataclass, field
import sys
from typing import Any, Callable, Optional, Set

import aio_pika
from aio_pika import ExchangeType, Message

from fast_app.utils.queue_utils import import_from_path, boot_if_needed
from fast_app.core.context import context
from fast_app.utils.serialisation import safe_int
from fast_app.utils.logging import setup_logging
from fast_app.utils.async_farm_utils import decode_message, ack_once, AckGuard


# Environment configuration with sensible defaults
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
JOBS_QUEUE = os.getenv("ASYNC_FARM_JOBS_QUEUE", "async_farm.jobs")
SUPERVISOR_TO_WORKERS_EXCHANGE = os.getenv("ASYNC_FARM_CONTROL_EXCHANGE", "async_farm.supervisor")
WORKER_TO_SUPERVISOR_EXCHANGE = os.getenv("ASYNC_FARM_WORKER_EXCHANGE", "async_farm.worker")

CONCURRENCY = int(os.getenv("PREFETCH_PER_WORKER", os.getenv("ASYNC_FARM_CONCURRENCY", "10")))
HEARTBEAT_INTERVAL_S = int(os.getenv("HEARTBEAT_INTERVAL_S", "5"))
SOFT_TIMEOUT_S = int(os.getenv("SOFT_TIMEOUT_S", "30"))
HARD_TIMEOUT_S = int(os.getenv("HARD_TIMEOUT_S", "60"))
WORKER_SHUTDOWN_GRACE_S = int(os.getenv("WORKER_SHUTDOWN_GRACE_S", "15"))


class AsyncFarmWorker:
    """RabbitMQ worker executing callables with bounded asyncio concurrency."""

    def __init__(self, supervisor_id: Optional[str] = None) -> None:
        self.supervisor_id = supervisor_id or os.getenv("SUPERVISOR_ID") or None
        self.start_timestamp = time.time()
        self.worker_id = f"worker_{os.getpid()}_{int(self.start_timestamp)}"  # Include start_ts to avoid PID reuse collisions

        self.connection: Optional[aio_pika.RobustConnection] = None
        self.control_channel: Optional[aio_pika.RobustConnection] = None
        self.jobs_channel: Optional[aio_pika.RobustChannel] = None
        self.supervisor_to_workers_exchange: Optional[aio_pika.RobustExchange] = None
        self.worker_to_supervisor_exchange: Optional[aio_pika.RobustExchange] = None
        self.jobs_queue: Optional[aio_pika.RobustQueue] = None
        self.worker_queue: Optional[aio_pika.RobustQueue] = None
        self.jobs_consumer_tag: str = None

        self.active_tasks: Set[asyncio.Task[Any]] = set()
        self.shutdown_requested: bool = False  # prevents double entry
        self.keep_alive: bool = True
        self.hard_timeout_triggered: bool = False
        self.last_supervisors_heartbeat_timestamp: float = None   # timestamp

    # ------------------------- lifecycle -------------------------
    async def start(self) -> None:
        setup_logging()
        if not self.supervisor_id:
            logging.info("[WORKER] No supervisor_id present.")

        logging.info("[WORKER] Starting farm worker...")
        self.connection = await aio_pika.connect_robust(RABBITMQ_URL)

        await self.setup_job_listener()
        await self.setup_control()

        logging.info("[WORKER] Attaching signals")
        loop = asyncio.get_running_loop()
        try:
            loop.add_signal_handler(signal.SIGTERM, self.request_shutdown)
            loop.add_signal_handler(signal.SIGINT, self.request_shutdown)
        except NotImplementedError:
            # Signals may be unavailable (e.g., on Windows or non-main thread)
            pass

        logging.info("[WORKER] Main gather")
        try:
            await asyncio.gather(
                self.heartbeat_loop(),
                self.keep_alive_loop(),
                self.supervisor_watchdog_loop(),
            )
        finally:
            self.request_shutdown()

            if self.control_channel:
                await self.control_channel.close()

            if self.jobs_channel:
                await self.jobs_channel.close()

            if self.connection:
                await self.connection.close()

    async def setup_job_listener(self) -> None:
        self.jobs_channel = await self.connection.channel()
        await self.jobs_channel.set_qos(prefetch_count=CONCURRENCY)
        self.jobs_queue = await self.jobs_channel.declare_queue(JOBS_QUEUE, durable=True)
        self.jobs_consumer_tag = await self.jobs_queue.consume(self.on_job_message)
    
    async def setup_control(self) -> None:
        self.control_channel = await self.connection.channel()
        self.worker_to_supervisor_exchange = await self.control_channel.declare_exchange(WORKER_TO_SUPERVISOR_EXCHANGE, ExchangeType.DIRECT, durable=True, auto_delete=True)

        self.supervisor_to_workers_exchange = await self.control_channel.declare_exchange(SUPERVISOR_TO_WORKERS_EXCHANGE, ExchangeType.FANOUT, durable=True)
        self.worker_queue = await self.control_channel.declare_queue(f"async_farm.control.worker.{self.worker_id}", exclusive=True, auto_delete=True)
        await self.worker_queue.bind(self.supervisor_to_workers_exchange)
        await self.worker_queue.consume(self.on_control_message, no_ack=True)

    def request_shutdown(self, grace_s: Optional[int] = None) -> None:
        logging.info("[WORKER] ENTRY request_shutdown")
        if self.shutdown_requested:
            return
            
        self.shutdown_requested = True

    # ------------------------- consumers -------------------------
    async def on_job_message(self, message: aio_pika.IncomingMessage) -> None:
        if self.shutdown_requested:
            await message.nack(requeue=True)
            return

        task = asyncio.create_task(self.handle_message_with_timeouts(message))
        self.active_tasks.add(task)
        task.add_done_callback(lambda _: self.active_tasks.discard(task))

    async def on_control_message(self, message: aio_pika.IncomingMessage) -> None:
        logging.info(f"[WORKER] received control message")
        payload = decode_message(message.body)
        if not payload:
            return

        logging.info(f"[WORKER] received control message `{payload}`")
        
        if payload.get("type") == "shutdown":
            logging.info("[WORKER] received shutdown message")
            await self.request_shutdown()
        elif payload.get("type") == "heartbeat":
            logging.info("[WORKER] received heartbeat message")
            if self.supervisor_id and payload.get("supervisor_id") == self.supervisor_id:
                self.last_supervisors_heartbeat_timestamp = payload.get("timestamp") or time.time()

    # ------------------------- publishers -------------------------
    async def publish_heartbeat(self) -> None:
        body = json.dumps({
                "type": "heartbeat",
                "supervisor_id": self.supervisor_id,
                "worker_id": self.worker_id,
                "pid": os.getpid(),
                "start_timestamp": self.start_timestamp,
                "active_tasks": len(self.active_tasks),
                "timestamp": time.time(),
            }).encode("utf-8")

        try:
            await self.worker_to_supervisor_exchange.publish(
                Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
                routing_key=f"supervisor.{self.supervisor_id}",
            )
        except Exception as e:
            # Best-effort heartbeat; ignore failures
            logging.info(f"Error publishing heartbeat: {e}")

    async def publish_stuck_task_event(self) -> None:
        if not self.supervisor_id:
            return

        body = json.dumps({
                "type": "stuck_task",
                "worker_id": self.worker_id,
                "pid": os.getpid(),
                "start_timestamp": self.start_timestamp,
                "timestamp": time.time(),
            }).encode("utf-8")

        try:
            await self.worker_to_supervisor_exchange.publish(
                Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
                routing_key=f"supervisor.{self.supervisor_id}",
            )
        except Exception as e:
            # Best-effort heartbeat; ignore failures
            logging.info(f"Error publishing stuck task event: {e}")

    # ------------------------- loops -------------------------
    async def heartbeat_loop(self) -> None:
        while self.keep_alive and self.supervisor_id is not None:
            await self.publish_heartbeat()
            await asyncio.sleep(HEARTBEAT_INTERVAL_S)

    async def keep_alive_loop(self) -> None:
        # Keep the worker alive until shutdown is requested and tasks drained
        while not self.shutdown_requested:
            await asyncio.sleep(0.5)

        if self.jobs_queue and self.jobs_consumer_tag:
            try:
                logging.info(f"[WORKER] Canceling consuming")
                await self.jobs_queue.cancel(self.jobs_consumer_tag)  # Stop accepting new jobs
            except aio_pika.exceptions.ChannelInvalidStateError:
                logging.info(f"[WORKER] Exception canceling queue ChannelInvalidStateError")
                pass

        # Wait for tasks to drain with grace
        # TODO: sync grace_s this with soft limit of a task
        grace_period_s = WORKER_SHUTDOWN_GRACE_S
        logging.info(f"[WORKER] Waiting for tasks {grace_period_s} s...")
        deadline = time.time() + float(grace_period_s)
        while self.active_tasks and time.time() < deadline:
            await asyncio.sleep(0.2)

        self.keep_alive = False

        logging.info("[WORKER] Done")

    async def supervisor_watchdog_loop(self) -> None:
        # Watch for supervisor heartbeat; if supervisor stops sending recent ts, shutdown
        timeout = 3 * max(1, HEARTBEAT_INTERVAL_S)
        while not self.shutdown_requested and self.supervisor_id is not None:
            if not self.last_supervisors_heartbeat_timestamp:
                if self.start_timestamp + timeout < time.time():
                    self.request_shutdown()
            else:
                if self.last_supervisors_heartbeat_timestamp + timeout < time.time():
                    self.request_shutdown()

    # ------------------------- task handling -------------------------
    async def handle_message_with_timeouts(self, message: aio_pika.IncomingMessage) -> None:
        try:
            await self.run_message_with_timeouts(message)
        except Exception:
            guard = AckGuard()
            await ack_once(message, guard)

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
            await ack_once(message, AckGuard())
            return
        func = import_from_path(func_path)

        async def run_callable() -> Any:
            return await func(*args, **kwargs)

        # Implement soft/hard timeouts
        task = asyncio.create_task(run_callable())

        # Per-message header overrides
        headers = (message.headers or {})
        soft_timeout_s = safe_int(headers.get("soft_timeout_s"), SOFT_TIMEOUT_S, 0, 24 * 3600)
        hard_timeout_s = safe_int(headers.get("hard_timeout_s"), HARD_TIMEOUT_S, 1, 48 * 3600)
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
                await ack_once(message, guard)
                await self.publish_stuck_task_event()
                await self.request_shutdown(120)  # 2 minutes
                sys.exit(1)

        soft_t = asyncio.create_task(soft_timeout())
        hard_t = asyncio.create_task(hard_timeout())

        try:
            await task
            await ack_once(message, guard)
        except asyncio.CancelledError:
            # Soft timeout cancellation
            await ack_once(message, guard)
        except Exception:
            # User code raised; ack to avoid poison loop
            await ack_once(message, guard)
        finally:
            soft_t.cancel()
            hard_t.cancel()


def _run() -> None:
    worker = AsyncFarmWorker(supervisor_id=os.getenv("SUPERVISOR_ID"))
    asyncio.run(worker.start())


if __name__ == "__main__":
    _run()


