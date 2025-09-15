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
from fast_app.utils.async_farm_utils import decode_message, AckGuard
from fast_app.app_provider import boot
from fast_app.integrations.async_farm.task import Task


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

        self.tasks: Set[Task] = set()
        self.shutdown_requested: bool = False  # prevents double entry
        self.keep_alive: bool = True
        self.hard_timeout_triggered: bool = False
        self.last_supervisors_heartbeat_timestamp: float = None   # timestamp

    # ------------------------- lifecycle -------------------------
    async def start(self) -> None:
        boot()
        if not self.supervisor_id:
            logging.warning("[WORKER] No supervisor_id present.")

        logging.debug("[WORKER] Starting farm worker...")
        self.connection = await aio_pika.connect_robust(RABBITMQ_URL)

        await self.setup_job_listener()
        await self.setup_control()

        loop = asyncio.get_running_loop()
        try:
            loop.add_signal_handler(signal.SIGTERM, self.request_shutdown)
            loop.add_signal_handler(signal.SIGINT, self.request_shutdown)
        except NotImplementedError:
            # Signals may be unavailable (e.g., on Windows or non-main thread)
            pass

        try:
            await asyncio.gather(
                self.heartbeat_loop(),
                self.keep_alive_loop(),
                self.supervisor_watchdog_loop(),
            )
        finally:
            logging.info("[WORKER] SHUTDOWN: Entry finally block")
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

    def request_shutdown(self) -> None:
        logging.info("[WORKER] ENTRY request_shutdown")
        if self.shutdown_requested:
            return
            
        self.shutdown_requested = True

    # ------------------------- consumers -------------------------
    async def on_job_message(self, message: aio_pika.IncomingMessage) -> None:
        if self.shutdown_requested:
            await message.nack(requeue=True)
            return

        task = Task(message)

        self.tasks.add(task)
        async def _on_done(_: Task) -> None:
            self.tasks.discard(task)

        task.add_done_callback(_on_done)
        task.add_hard_timeout_callback(lambda t: self.on_task_hard_timeout(t))

        await task.run()

    async def on_control_message(self, message: aio_pika.IncomingMessage) -> None:
        payload = decode_message(message.body)
        if not payload:
            logging.warning(f"[WORKER] Received control message with no payload.")
            return

        logging.debug(f"[WORKER] Received control message `{payload}`")
        
        if payload.get("type") == "shutdown":
            logging.info("[WORKER] SHUTDOWN: Command received")
            self.request_shutdown()
        elif payload.get("type") == "heartbeat":
            logging.debug("[WORKER] Supervisor heartbeat message")
            if self.supervisor_id and payload.get("supervisor_id") == self.supervisor_id:
                self.last_supervisors_heartbeat_timestamp = payload.get("timestamp") or time.time()

    # ------------------------- publishers -------------------------
    async def publish_to_supervisor(self, body: dict) -> None:
        if not self.supervisor_id:
            return

        body = json.dumps(body).encode("utf-8")
        try:
            await self.worker_to_supervisor_exchange.publish(
                Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
                routing_key=f"supervisor.{self.supervisor_id}",
            )
        except Exception as e:
            # Best-effort heartbeat; ignore failures
            logging.error(f"Error publishing to supervisor: {e}")

    async def publish_heartbeat(self) -> None:
        await self.publish_to_supervisor({
                "type": "heartbeat",
                "supervisor_id": self.supervisor_id,
                "worker_id": self.worker_id,
                "pid": os.getpid(),
                "start_timestamp": self.start_timestamp,
                "active_tasks": len(self.tasks),
                "timestamp": time.time(),
            })

    async def publish_stuck_task_event(self, task: Task) -> None:
        await self.publish_to_supervisor({
                "type": "stuck_task",
                "worker_id": self.worker_id,
                "pid": os.getpid(),
                "start_timestamp": self.start_timestamp,
                "timestamp": time.time(),
                "task": {
                    "func_path": task.func_path,
                }
            })

    async def publish_soft_timeout_task_event(self, task: Task) -> None:
        await self.publish_to_supervisor({
            "type": "soft_timeout_task",
            "worker_id": self.worker_id,
            "pid": os.getpid(),
            "start_timestamp": self.start_timestamp,
            "timestamp": time.time(),
            "task": {
                "func_path": task.func_path,
            }
        })

    async def publish_success_task_event(self, task: Task, result: Any) -> None:
        await self.publish_to_supervisor({
            "type": "success_task",
            "worker_id": self.worker_id,
            "pid": os.getpid(),
            "start_timestamp": self.start_timestamp,
            "timestamp": time.time(),
            "task": {
                "func_path": task.func_path,
            }
        })

    async def publish_failure_task_event(self, task: Task, exception: Exception) -> None:
        await self.publish_to_supervisor({
            "type": "failure_task",
            "worker_id": self.worker_id,
            "pid": os.getpid(),
            "start_timestamp": self.start_timestamp,
            "timestamp": time.time(),
            "task": {
                "func_path": task.func_path,
            }
        })

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
                logging.debug(f"[WORKER] Canceling consuming...")
                await self.jobs_queue.cancel(self.jobs_consumer_tag)  # Stop accepting new jobs
            except aio_pika.exceptions.ChannelInvalidStateError:
                logging.warning(f"[WORKER] Exception canceling queue ChannelInvalidStateError")
                pass

        # Wait for tasks to drain with grace
        grace_period_s = max(task.soft_timeout_s for task in self.tasks) if self.tasks else WORKER_SHUTDOWN_GRACE_S
        logging.debug(f"[WORKER] Waiting for tasks {grace_period_s} s...")
        deadline = time.time() + float(grace_period_s)
        while self.tasks and time.time() < deadline:
            await asyncio.sleep(0.2)

        self.keep_alive = False

        logging.debug("[WORKER] Done")

    async def supervisor_watchdog_loop(self) -> None:
        # Watch for supervisor heartbeat; if supervisor stops sending recent ts, shutdown
        timeout = 7 * max(1, HEARTBEAT_INTERVAL_S)
        while not self.shutdown_requested and self.supervisor_id is not None:
            if not self.last_supervisors_heartbeat_timestamp:
                if self.start_timestamp + timeout < time.time():
                    logging.info("[WORKER] SHUTDOWN: No supervisor heartbeat received & start_timestamp + timeout < time.time()")
                    self.request_shutdown()
            else:
                if self.last_supervisors_heartbeat_timestamp + timeout < time.time():
                    logging.info("[WORKER] SHUTDOWN: Supervisor skipped heartbeat for too long")
                    self.request_shutdown()
            # Yield to event loop to avoid busy loop starving IO
            await asyncio.sleep(HEARTBEAT_INTERVAL_S)

    # ------------------------- task callbacks -------------------------
    async def on_task_hard_timeout(self, task: Task) -> None:
        self.hard_timeout_triggered = True
        await self.publish_stuck_task_event(task)
        logging.info("[WORKER] SHUTDOWN: Hard timeout triggered")
        self.request_shutdown() 
        await asyncio.sleep(120)  # 2 minutes
        sys.exit(1) # force quit 

    async def on_task_soft_timeout(self, task: Task) -> None:
        await self.publish_soft_timeout_task_event(task)

    async def on_task_success(self, task: Task, result: Any) -> None:
        await self.publish_success_task_event(task, result)

    async def on_task_failure(self, task: Task, exception: Exception) -> None:
        await self.publish_failure_task_event(task, exception)
    

def _run() -> None:
    worker = AsyncFarmWorker(supervisor_id=os.getenv("SUPERVISOR_ID"))
    asyncio.run(worker.start())


if __name__ == "__main__":
    _run()


