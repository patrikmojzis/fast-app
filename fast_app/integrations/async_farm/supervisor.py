from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import time
from multiprocessing import Process
from typing import Dict, List, Optional, TypedDict
import sys

import aio_pika
from aio_pika import ExchangeType

from fast_app.utils.async_farm_utils import await_processes_death, decode_message
from fast_app.app_provider import boot


class WorkerState(TypedDict):
    process: Process
    active_tasks: int
    start_timestamp: float
    last_heartbeat_timestamp: Optional[float]


RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
JOBS_QUEUE = os.getenv("ASYNC_FARM_JOBS_QUEUE", "async_farm.jobs")
SUPERVISOR_TO_WORKERS_EXCHANGE = os.getenv("ASYNC_FARM_CONTROL_EXCHANGE", "async_farm.supervisor")
WORKER_TO_SUPERVISOR_EXCHANGE = os.getenv("ASYNC_FARM_WORKER_EXCHANGE", "async_farm.worker")

HEARTBEAT_INTERVAL_S = int(os.getenv("HEARTBEAT_INTERVAL_S", "5"))


def _worker_entry(supervisor_id: str) -> None:
    import asyncio as _asyncio
    import os as _os
    from fast_app.integrations.async_farm.worker import AsyncFarmWorker

    _os.environ["SUPERVISOR_ID"] = supervisor_id
    worker = AsyncFarmWorker(supervisor_id=supervisor_id)
    _asyncio.run(worker.start())

Worker = Dict[str, WorkerState]

class AsyncFarmSupervisor:
    def __init__(self) -> None:
        # Scaling params
        self.min_workers = int(os.getenv("MIN_WORKERS", "1"))
        self.max_workers = int(os.getenv("MAX_WORKERS", "10"))
        self.scale_check_interval = float(os.getenv("SCALE_CHECK_INTERVAL_S", "1"))
        self.scale_up_batch_size = int(os.getenv("SCALE_UP_BATCH_SIZE", "2"))
        self.scale_down_batch_size = int(os.getenv("SCALE_DOWN_BATCH_SIZE", "1"))
        self.prefetch_per_worker = int(os.getenv("PREFETCH_PER_WORKER", "10"))
        self.shutdown_grace_s = int(os.getenv("WORKER_SHUTDOWN_GRACE_S", "15"))

        # State
        self.supervisor_id = f"supervisor_{os.getpid()}_{int(time.time())}"
        self.workers: Worker = {}  # associated workers
        self.pending_processes: List[Process] = []  # just spawned workers
        self.shutdown_requested = False

        # Connections
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.channel: Optional[aio_pika.RobustChannel] = None
        self.supervisor_to_workers_exchange: Optional[aio_pika.RobustExchange] = None
        self.worker_to_supervisor_exchange: Optional[aio_pika.RobustExchange] = None
        self.jobs_queue: Optional[aio_pika.RobustQueue] = None
        self.supervisor_queue: Optional[aio_pika.RobustQueue] = None

    # ---------------- lifecycle ----------------
    async def run(self) -> None:
        boot()
        print(f"🚜 Starting farm supervisor {self.supervisor_id}...")
        self.connection = await aio_pika.connect_robust(RABBITMQ_URL)
        
        await self.setup_connections()

        # Signals
        loop = asyncio.get_running_loop()
        try:
            loop.add_signal_handler(signal.SIGTERM, self.request_shutdown)
            loop.add_signal_handler(signal.SIGINT, self.request_shutdown)
        except NotImplementedError:
            # Signals may be unavailable (e.g., on Windows or non-main thread)
            pass

        try:
            # Spawn baseline workers
            print(f"👥 Spawning {self.min_workers} baseline workers...")
            for _ in range(self.min_workers):
                await self.spawn_worker()

            print(f"❤️ Starting heartbeat check every {HEARTBEAT_INTERVAL_S} seconds...")
            print(f"📊 Starting scaling loop every {self.scale_check_interval} seconds...")
            # Start consumers
            await asyncio.gather(
                self.heartbeat_loop(),
                self.scaling_loop(),
                self.keep_alive_loop(),
                self.monitor_workers_heartbeat_loop()
            )
        finally:
            self.request_shutdown()

            if self.channel:
                await self.channel.close()

            if self.connection:
                await self.connection.close()

    async def setup_connections(self) -> None:
        self.channel = await self.connection.channel()

        self.jobs_queue = await self.channel.declare_queue(JOBS_QUEUE, durable=True)

        self.supervisor_to_workers_exchange = await self.channel.declare_exchange(SUPERVISOR_TO_WORKERS_EXCHANGE, ExchangeType.FANOUT, durable=True)

        self.worker_to_supervisor_exchange = await self.channel.declare_exchange(WORKER_TO_SUPERVISOR_EXCHANGE, ExchangeType.DIRECT, durable=True, auto_delete=True)
        self.supervisor_queue = await self.channel.declare_queue(f"async_farm.control.supervisor.{self.supervisor_id}", exclusive=True, auto_delete=True)
        await self.supervisor_queue.bind(self.worker_to_supervisor_exchange, routing_key=f"supervisor.{self.supervisor_id}")
        await self.supervisor_queue.consume(self.on_control_message, no_ack=True)
 
    def request_shutdown(self) -> None:
        if self.shutdown_requested:
            return

        print("🛑 Farm supervisor shutdown requested...")
        self.shutdown_requested = True

    async def handle_workers_heartbeat(self, payload: dict) -> None:
        if worker_id := payload.get("worker_id"):
            # print(f"❤️ Worker {worker_id} heartbeat received", end="\r", flush=True)

            if self.workers.get(worker_id):
                self.workers.get(worker_id)["last_heartbeat_timestamp"] = payload.get("timestamp") or time.time()
                self.workers.get(worker_id)["active_tasks"] = payload.get("active_tasks")
            
            else:
                pid_val = int(payload.get("pid", 0))
                for p in list(self.pending_processes):
                    if p.pid == pid_val:

                        try:
                            self.pending_processes.remove(p)
                        except ValueError:
                            print("Err removing process")
                            pass

                        self.workers[worker_id] = {
                            "process": p,
                            "active_tasks": payload.get("active_tasks", 0),
                            "last_heartbeat_timestamp": payload.get("timestamp") or time.time(),
                            "start_timestamp": payload.get("start_timestamp")
                        } 
                        break
    
    # ---------------- consumers ----------------
    async def on_control_message(self, message: aio_pika.IncomingMessage) -> None:
        payload = decode_message(message.body)
        if not payload:
            return

        # print(f"[SUPERVISOR] received message `{payload}`")
        
        if payload.get("type") == "heartbeat":
            # print("[SUPERVISOR] received heartbeat control message")
            await self.handle_workers_heartbeat(payload)

    # ---------------- publishers ----------------
    async def publish_to_workers(self, payload: dict) -> None:
        payload = json.dumps(payload).encode("utf-8")
        try:
            await self.supervisor_to_workers_exchange.publish(
                aio_pika.Message(body=payload), 
                routing_key=""
                )
        except Exception as e:
            print("[SUPERVISOR] Cannot publish to workers", e)
            # Best-effort control message; avoid crashing supervisor on transient broker errors
            pass

    async def publish_shutdown(self, grace_s: int = 0) -> None:
        await self.publish_to_workers({
            "type": "shutdown",
            "grace_s": grace_s
            })

    async def publish_heartbeat(self) -> None:
        await self.publish_to_workers({
            "type": "heartbeat",
            "supervisor_id": self.supervisor_id,
            "timestamp": time.time(),
        })

    # ---------------- processes ----------------
    async def spawn_worker(self) -> Process:
        worker_num = len(self.workers) + len(self.pending_processes)
        p = Process(target=_worker_entry, args=(self.supervisor_id,), name=f"AsyncFarmWorker-{worker_num}")

        # Textual captures stdout/stderr with objects that don't have a valid fileno().
        # When using the 'spawn' start method (default on macOS), multiprocessing will
        # attempt to pass fds_to_keep including those of stdout/stderr, which raises
        # `ValueError: bad value(s) in fds_to_keep)`. Temporarily restore real stdio
        # during process start to avoid that issue.
        old_stdout, old_stderr = sys.stdout, sys.stderr
        try:
            sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__
            p.start()
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr
        print(f"🧑‍🌾 Spawned worker #{worker_num} (PID: {p.pid})")
        self.pending_processes.append(p)
        return p

    def get_alive_processes(self) -> List[Process]:
        # Refresh pending processes
        pending_alive: List[Process] = []
        for p in self.pending_processes:
            if p.is_alive():
                pending_alive.append(p)
        self.pending_processes = pending_alive

        # Refresh associated workers
        alive_associated: List[Process] = []
        for wid, st in list(self.workers.items()):
            proc = st.get("process")
            if proc is None or not proc.is_alive():
                self.workers.pop(wid, None)
            else:
                alive_associated.append(proc)

        return [*self.pending_processes, *alive_associated]

    async def terminate_worker(self, worker_id: str) -> None:
        state = self.workers.pop(worker_id, None)
        if not state:
            return
        proc = state.get("process")
        print(f"🗑️ Terminating worker {worker_id} (PID: {getattr(proc, 'pid', '-')})...")
        if proc and proc.is_alive():
            proc.terminate()
            try:
                await await_processes_death([proc], self.shutdown_grace_s)
            except Exception:
                pass
        if proc and proc.is_alive():
            proc.kill()
        # Ensure not tracked as pending
        if proc is not None:
            self.pending_processes = [p for p in self.pending_processes if p.pid != proc.pid]

    # ---------------- loops ----------------
    async def keep_alive_loop(self) -> None:
        while self.shutdown_requested == False:
            await asyncio.sleep(0.5)

        # Ask workers to shutdown gracefully
        print("Processing shutdown")
        worker_count = len(list(self.workers.keys()))
        if worker_count > 0:
            print(f"🧑‍🌾 Asking {worker_count} workers to shutdown gracefully...")
            await self.publish_shutdown(self.shutdown_grace_s)
                
        # Wait grace shutdown
        procs = self.get_alive_processes()
        if procs:
            print(f"⏳ Waiting {self.shutdown_grace_s}s for {len(procs)} workers to finish...")
            await await_processes_death(procs, self.shutdown_grace_s)

        # Send terminate to processes
        procs = self.get_alive_processes()
        if procs:
            print(f"🧑‍🌾🔚 Terminating {len(procs)} remaining workers...")
            [p.terminate() for p in procs if p.is_alive()]

        procs = self.get_alive_processes()
        if procs:
            await await_processes_death(procs, self.shutdown_grace_s)

        # Force kill any remaining
        procs = self.get_alive_processes()
        if procs:
            print(f"🧑‍🌾🔫 Force killing {len(procs)} stubborn workers...")
            [p.kill() for p in procs if p.is_alive()]

        # Close connections after all workers are terminated
        print("🔌 Closing farm connections...")

    async def scaling_loop(self) -> None:
        assert self.jobs_queue is not None
        while not self.shutdown_requested:
            # Queue depth (refresh declare)
            try:
                await self.jobs_queue.declare()
                message_count = int(getattr(self.jobs_queue.declaration_result, "message_count", 0))
            except Exception as e:
                # Skip this tick on broker hiccup
                print("❌ Skip this tick on broker hiccup", e)
                await asyncio.sleep(self.scale_check_interval)
                continue

            # Compute current capacity and reconcile min/max
            alive_count = len(self.get_alive_processes())
            associated_count = len(self.workers)
            capacity = alive_count * max(1, self.prefetch_per_worker)

            # Ensure at least min_workers are present (including pending)
            if alive_count < self.min_workers:
                to_spawn = min(self.min_workers - alive_count, max(0, self.max_workers - alive_count))
                if to_spawn > 0:
                    print(f"🧑‍🌾 Ensuring min workers: spawning {to_spawn} (alive {alive_count} < min {self.min_workers})")
                    for _ in range(to_spawn):
                        await self.spawn_worker()
                await asyncio.sleep(self.scale_check_interval)
                continue

            # Scale up if backlog exceeds capacity (simple heuristic)
            if message_count > capacity and alive_count < self.max_workers:
                to_add = min(self.scale_up_batch_size, self.max_workers - alive_count)
                if to_add > 0:
                    print(f"📈 Queue backlog detected ({message_count} jobs > {capacity} capacity), scaling up {to_add} workers...")
                    for _ in range(to_add):
                        await self.spawn_worker()

            # Scale down when light and above min; prefer idle workers
            elif message_count <= max(0, (alive_count - 1) * self.prefetch_per_worker) and associated_count > self.min_workers:
                idle_now: List[str] = [
                    wid for wid, st in self.workers.items()
                    if int(st.get("active_tasks", 0)) == 0
                ]
                removable = min(self.scale_down_batch_size, max(0, associated_count - self.min_workers), len(idle_now))
                if removable > 0:
                    print(f"📉 Queue is light ({message_count} jobs), scaling down {removable} idle workers...")
                    for wid in idle_now[:removable]:
                        await self.terminate_worker(wid)

            await asyncio.sleep(self.scale_check_interval)

    async def heartbeat_loop(self) -> None:
        while not self.shutdown_requested:
            await self.publish_heartbeat()
            await asyncio.sleep(HEARTBEAT_INTERVAL_S)

    async def monitor_workers_heartbeat_loop(self) -> None:
        timeout_s = 7 * max(1, HEARTBEAT_INTERVAL_S)
        while not self.shutdown_requested:
            now_ts = time.time()
            stale_worker_ids: List[str] = []

            for worker_id, state in list(self.workers.items()):
                last_ts = state.get("last_heartbeat_timestamp")
                if last_ts is None or float(last_ts) + timeout_s < now_ts:
                    stale_worker_ids.append(worker_id)

            for worker_id in stale_worker_ids:
                print(f"⚠️ Worker {worker_id} missed {timeout_s}s of heartbeats; terminating...")
                await self.terminate_worker(worker_id)

            await asyncio.sleep(HEARTBEAT_INTERVAL_S)


