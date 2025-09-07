from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import time
from multiprocessing import Process
from typing import Dict, List, Optional, TypedDict

import aio_pika
from aio_pika import ExchangeType

from fast_app.utils.async_farm_utils import await_processes_death, decode_message


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
        self.supervisor_id = f"manager_{os.getpid()}_{int(time.time())}"
        self.workers: Dict[str, WorkerState] = {}  # associated workers
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
    async def start(self) -> None:
        print(f"🚜 Starting farm manager {self.supervisor_id}...")
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
        await self.supervisor_queue.bind(self.supervisor_to_workers_exchange, routing_key=f"supervisor.{self.supervisor_id}")
        await self.supervisor_queue.consume(self.on_control_message, no_ack=True)
 
    def request_shutdown(self) -> None:
        if self.shutdown_requested:
            return

        print("🛑 Farm shutdown requested...")
        self.shutdown_requested = True

    async def handle_workers_heartbeat(self, payload: dict) -> None:
        if worker_id := payload.get("worker_id"):
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

        print(f"[MANAGER] received message `{payload}`")
        
        if payload.get("type") == "heartbeat":
            print("[MANAGER] received heartbeat control message")
            await self.handle_workers_heartbeat(payload)

    # ---------------- publishers ----------------
    async def publish_shutdown(self, grace_s: int = 0) -> None:
        payload = json.dumps({
            "type": "shutdown",
            "grace_s": grace_s
            }).encode("utf-8")

        try:
            await self.supervisor_to_workers_exchange.publish(
                aio_pika.Message(body=payload), routing_key=""
            )
        except Exception:
            print("cannot publish shutdown")
            # Best-effort control message; avoid crashing supervisor on transient broker errors
            pass

    async def publish_heartbeat(self) -> None:
        payload = json.dumps({
            "type": "heartbeat",
            "supervisor_id": self.supervisor_id,
            "timestamp": time.time(),
        }).encode("utf-8")

        try:
            await self.supervisor_to_workers_exchange.publish(
                aio_pika.Message(body=payload), routing_key=""
            )
        except Exception:
            print("cannot publish heartbeat")
            # Best-effort supervisor heartbeat; avoid crashing supervisor on transient broker errors
            pass

    # ---------------- processes ----------------
    async def spawn_worker(self) -> Process:
        worker_num = len(self.workers) + len(self.pending_processes)
        p = Process(target=_worker_entry, args=(self.supervisor_id,), name=f"AsyncFarmWorker-{worker_num}")
        p.start()
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
            # Queue depth (refresh passive declare)
            try:
                await self.jobs_queue.declare(passive=True)
                message_count = int(getattr(self.jobs_queue.declaration_result, "message_count", 0))
            except Exception:
                # Skip this tick on broker hiccup
                await asyncio.sleep(self.scale_check_interval)
                continue

            # Decide scale up/down
            current_workers = len(self.get_alive_processes())
            capacity = current_workers * max(1, self.prefetch_per_worker)

            if message_count > capacity and current_workers < self.max_workers:
                to_add = min(self.scale_up_batch_size, self.max_workers - current_workers)
                print(f"📈 Queue backlog detected ({message_count} jobs > {capacity} capacity), scaling up {to_add} workers...")
                for _ in range(to_add):
                    await self.spawn_worker()

            elif message_count <= max(0, (current_workers - 1) * self.prefetch_per_worker) and current_workers > self.min_workers:
                # choose idle workers (active_tasks == 0) with recent heartbeat (<= 3 * HEARTBEAT interval)
                now_ts = time.time()
                recent_threshold_ts = now_ts - 3 * max(1, HEARTBEAT_INTERVAL_S)
                idle_now: List[str] = [
                    wid for wid, st in self.workers.items()
                    if int(st.get("active_tasks", 0)) == 0 and float(st.get("ts", 0)) >= recent_threshold_ts
                ]
                remove_count = min(self.scale_down_batch_size, current_workers - self.min_workers, len(idle_now))
                if remove_count > 0:
                    print(f"📉 Queue is light ({message_count} jobs), scaling down {remove_count} idle workers...")
                for wid in idle_now[:remove_count]:
                    await self.publish_shutdown(wid, self.shutdown_grace_s)

            await asyncio.sleep(self.scale_check_interval)

    async def heartbeat_loop(self) -> None:
        while not self.shutdown_requested:
            await self.publish_heartbeat()
            await asyncio.sleep(HEARTBEAT_INTERVAL_S)

    async def monitor_workers_heartbeat_loop(self) -> None:
        while not self.request_shutdown:
            for worker_id, state in self.workers.values():
                pass
                # TODO: implement this

def run_supervisor() -> None:
    sup = AsyncFarmSupervisor()
    asyncio.run(sup.start())


if __name__ == "__main__":
    run_supervisor()


