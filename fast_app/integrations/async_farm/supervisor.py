from __future__ import annotations

import asyncio
import json
import os
import signal
import time
from multiprocessing import Process
from typing import Dict, List, Optional, TypedDict

import aio_pika
from aio_pika import ExchangeType

from fast_app.utils.async_farm_utils import await_processes_death


class WorkerState(TypedDict):
    process: Process
    active_tasks: int
    ts: float


RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
JOBS_QUEUE = os.getenv("ASYNC_FARM_JOBS_QUEUE", "async_farm.jobs")
CONTROL_EXCHANGE = os.getenv("ASYNC_FARM_CONTROL_EXCHANGE", "async_farm.control")
HEARTBEAT_INTERVAL_S = int(os.getenv("HEARTBEAT_INTERVAL_S", "5"))


def _worker_entry(manager_id: str) -> None:
    import asyncio as _asyncio
    import os as _os
    from fast_app.integrations.async_farm.worker import AsyncFarmWorker

    _os.environ["MANAGER_ID"] = manager_id
    worker = AsyncFarmWorker(manager_id=manager_id)
    _asyncio.run(worker.start())


class AsyncFarmSupervisor:
    def __init__(self) -> None:
        # Scaling params
        self.min_workers = int(os.getenv("MIN_WORKERS", "2"))
        self.max_workers = int(os.getenv("MAX_WORKERS", "10"))
        self.scale_check_interval = float(os.getenv("SCALE_CHECK_INTERVAL_S", "1"))
        self.scale_up_batch_size = int(os.getenv("SCALE_UP_BATCH_SIZE", "2"))
        self.scale_down_batch_size = int(os.getenv("SCALE_DOWN_BATCH_SIZE", "1"))
        self.prefetch_per_worker = int(os.getenv("PREFETCH_PER_WORKER", "10"))
        self.shutdown_grace_s = int(os.getenv("WORKER_SHUTDOWN_GRACE_S", "15"))

        # State
        self.manager_id = f"manager_{os.getpid()}_{int(time.time())}"
        self.workers: Dict[str, WorkerState] = {}  # associated workers
        self.pending_processes: List[Process] = []  # just spawned workers
        self.shutdown_requested = False

        # Connections
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.channel: Optional[aio_pika.RobustChannel] = None
        self.jobs_queue: Optional[aio_pika.Queue] = None
        self.control_exchange: Optional[aio_pika.Exchange] = None
        self.supervisor_queue: Optional[aio_pika.Queue] = None

    # ---------------- lifecycle ----------------
    async def start(self) -> None:
        print(f"🚜 Starting farm manager {self.manager_id}...")
        self.connection = await aio_pika.connect_robust(RABBITMQ_URL)
        self.channel = await self.connection.channel()

        # Passive declare to get message count
        self.jobs_queue = await self.channel.declare_queue(JOBS_QUEUE, durable=True)

        # Control exchange + queues
        self.control_exchange = await self.channel.declare_exchange(CONTROL_EXCHANGE, ExchangeType.DIRECT, durable=True)
        self.supervisor_queue = await self.channel.declare_queue(
            f"async_farm.control.supervisor.{self.manager_id}", exclusive=True, auto_delete=True
        )
        await self.supervisor_queue.bind(self.control_exchange, routing_key=f"supervisor.{self.manager_id}")

        # Signals
        loop = asyncio.get_running_loop()
        try:
            loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(self.shutdown()))
            loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(self.shutdown()))
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
                self.heartbeat_consumer(),
                self.scaling_loop(),
                self.supervisor_heartbeat_loop(),
            )
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        if self.shutdown_requested:
            return

        print("🛑 Farm shutdown requested...")
        self.shutdown_requested = True

        # Ask workers to shutdown gracefully
        worker_count = len(list(self.workers.keys()))
        if worker_count > 0:
            print(f"🧑‍🌾 Asking {worker_count} workers to shutdown gracefully...")
            for wid in list(self.workers.keys()):
                await self.send_shutdown(wid, self.shutdown_grace_s)

        # Close connections after all workers are terminated
        # print("🔌 Closing farm connections...")
        # await self.close_connections()
        # Line 117: Supervisor sends shutdown messages to workers via RabbitMQ
        # Line 121: Supervisor immediately closes its RabbitMQ connections ❌
        # Line 127: Supervisor waits for workers to finish, but they're stuck because:
        # Workers can't send final heartbeats (connection closed)
        # Workers' supervisor_watchdog_loop gets stuck waiting for supervisor heartbeats
        # Workers' drain_loop can't close connections properly

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
        await self.close_connections()

    async def close_connections(self) -> None:
        try:
            if self.channel:
                await self.channel.close()
        finally:
            if self.connection:
                await self.connection.close()

    async def _redeclare_supervisor_queue(self) -> None:
        """Redeclare the supervisor queue after it was auto-deleted."""
        if self.channel is None or self.control_exchange is None:
            return
        try:
            self.supervisor_queue = await self.channel.declare_queue(
                f"async_farm.control.supervisor.{self.manager_id}", exclusive=True, auto_delete=True
            )
            await self.supervisor_queue.bind(self.control_exchange, routing_key=f"supervisor.{self.manager_id}")
        except Exception:
            print("Redeclare supervisor queue failed")
            # Best-effort redeclaration; if it fails, the next iteration will try again
            pass

    # ---------------- processes ----------------
    async def spawn_worker(self) -> Process:
        worker_num = len(self.workers) + len(self.pending_processes)
        p = Process(target=_worker_entry, args=(self.manager_id,), name=f"AsyncFarmWorker-{worker_num}")
        p.start()
        print(f"🧑‍🌾 Spawned worker #{worker_num} (PID: {p.pid})")
        self.pending_processes.append(p)
        return p

    async def send_shutdown(self, worker_id: str, grace_s: int) -> None:
        assert self.control_exchange is not None
        payload = json.dumps({"type": "shutdown", "grace_s": grace_s}).encode("utf-8")
        try:
            await self.control_exchange.publish(
                aio_pika.Message(body=payload), routing_key=f"worker.{worker_id}"
            )
        except Exception:
            # Best-effort control message; avoid crashing supervisor on transient broker errors
            pass

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

    # ---------------- monitoring ----------------
    async def heartbeat_consumer(self) -> None:
        assert self.supervisor_queue is not None
        while not self.shutdown_requested:
            try:
                async with self.supervisor_queue.iterator() as it:
                    while not self.shutdown_requested:
                        try:
                            message = await asyncio.wait_for(it.__anext__(), timeout=1.0)
                        except asyncio.TimeoutError:
                            continue
                        except StopAsyncIteration:
                            # Iterator closed by broker/connection; recreate on next loop
                            break
                        try:
                            payload = json.loads(message.body.decode("utf-8"))
                            msg_type = payload.get("type")

                            if msg_type == "heartbeat":
                                wid = payload.get("worker_id")
                                pid_val = int(payload.get("pid", 0))
                                # Associate pending process by PID if needed
                                proc: Optional[Process] = self.workers.get(wid, {}).get("process") if wid in self.workers else None
                                if proc is None:
                                    for p in list(self.pending_processes):
                                        if p.pid == pid_val:
                                            proc = p
                                            try:
                                                self.pending_processes.remove(p)
                                            except ValueError:
                                                pass
                                            break
                                # If no local process, ignore (we don't adopt remote workers)
                                if proc is not None:
                                    state: WorkerState = {
                                        "process": proc,
                                        "active_tasks": int(payload.get("active_tasks", 0)),
                                        "ts": float(payload.get("ts", time.time())),
                                    }
                                    self.workers[wid] = state

                            elif msg_type == "stuck_task":
                                # shutdown will be initiated by worker
                                pass
                        finally:
                            try:
                                await message.ack()
                            except Exception:
                                # Best-effort ack on transient channel issues
                                pass
            except StopAsyncIteration:
                print("💓 Heartbeat stream ended; reconnecting...")
                # Redeclare the queue since it was auto-deleted when iterator closed
                await self._redeclare_supervisor_queue()
                await asyncio.sleep(0.5)
                continue
            except Exception as e:
                # Transient error (connection hiccup etc.) — retry
                print(e)
                print("💓 Heartbeat consumer error; retrying shortly...", e)
                # Redeclare the queue in case it was deleted
                await self._redeclare_supervisor_queue()
                await asyncio.sleep(1.0)

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
                    await self.send_shutdown(wid, self.shutdown_grace_s)

            await asyncio.sleep(self.scale_check_interval)


    async def supervisor_heartbeat_loop(self) -> None:
        assert self.control_exchange is not None
        routing_key = f"supervisor_heartbeat.{self.manager_id}"
        while not self.shutdown_requested:
            try:
                payload = json.dumps({
                    "type": "supervisor_heartbeat",
                    "manager_id": self.manager_id,
                    "ts": time.time(),
                }).encode("utf-8")
                await self.control_exchange.publish(
                    aio_pika.Message(body=payload), routing_key=routing_key
                )
            except Exception:
                # Best-effort supervisor heartbeat; avoid crashing supervisor on transient broker errors
                pass
            await asyncio.sleep(HEARTBEAT_INTERVAL_S)

def run_supervisor() -> None:
    sup = AsyncFarmSupervisor()
    asyncio.run(sup.start())


if __name__ == "__main__":
    run_supervisor()


