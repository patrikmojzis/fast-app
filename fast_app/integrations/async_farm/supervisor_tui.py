from __future__ import annotations

import asyncio
import os
import sys
import time
from typing import Optional, TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Static, DataTable
from textual.containers import Vertical

if TYPE_CHECKING:
    from fast_app.integrations.async_farm.supervisor import AsyncFarmSupervisor


def _format_seconds_delta(seconds: float) -> str:
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


class SupervisorTUI(App):  # type: ignore[misc]
    CSS_PATH = None
    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("+", "inc_min", "Min+", show=True),
        Binding("-", "dec_min", "Min-", show=True),
        Binding("]", "inc_max", "Max+", show=True),
        Binding("[", "dec_max", "Max-", show=True),
        Binding("x", "shutdown", "Shutdown", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("R", "reboot", "Reboot", show=True),
    ]

    def __init__(self, supervisor: 'AsyncFarmSupervisor') -> None:
        super().__init__()
        self.supervisor = supervisor
        self._metrics: Optional[Static] = None
        self._table: Optional[DataTable] = None
        self._supervisor_task: Optional[asyncio.Task[None]] = None

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Header(show_clock=True)
        with Vertical():
            self._metrics = Static()
            yield self._metrics
            self._table = DataTable(zebra_stripes=True)
            self._table.add_columns("Worker", "PID", "Active", "Last HB", "Uptime")
            yield self._table
        yield Footer()

    async def on_mount(self) -> None:  # type: ignore[override]
        # Start supervisor in background within the same event loop
        if self._supervisor_task is None:
            self._supervisor_task = asyncio.create_task(self.supervisor.run())

        self.set_interval(1.0, self._update_view)
        await self._update_view()

    async def _update_view(self) -> None:
        sup = self.supervisor
        now = time.time()

        # If supervisor stopped (error or graceful), exit TUI
        if self._supervisor_task and self._supervisor_task.done():
            self.exit()
            return

        # Queue depth/capacity
        message_count = 0
        try:
            if sup.jobs_queue is not None:
                await sup.jobs_queue.declare(passive=True)
                message_count = int(getattr(sup.jobs_queue.declaration_result, "message_count", 0))
        except Exception:
            pass

        worker_count = len(sup.workers)
        pending = len(sup.pending_processes)
        capacity = worker_count * max(1, sup.prefetch_per_worker)

        status_text = "🛑" if sup.shutdown_requested else "🟢"
        metrics_text = (
            f"{status_text} | "
            f"🧑‍🌾 Workers: {worker_count} (pending: {pending})  "
            f"⚙️ Min/Max: {sup.min_workers}/{sup.max_workers}  "
            f"📦 Queue: {message_count}  "
            f"🚀 Capacity: {capacity}  "
        )
        if self._metrics:
            self._metrics.update(metrics_text)

        if self._table:
            self._table.clear()
            for worker_id, state in sup.workers.items():
                pid = getattr(state.get("process"), "pid", "-")
                active = int(state.get("active_tasks", 0))
                last_hb = state.get("last_heartbeat_timestamp") or 0.0
                last_hb_ago = _format_seconds_delta(now - float(last_hb)) if last_hb else "-"
                start_ts = float(state.get("start_timestamp") or now)
                uptime = _format_seconds_delta(now - start_ts)
                icon = "🟢" if last_hb and now - float(last_hb) <= 3 * max(1, self.supervisor.scale_check_interval) else "🟠"
                self._table.add_row(f"{icon} {worker_id}", str(pid), str(active), last_hb_ago, uptime)


    async def action_refresh(self) -> None:
        await self._update_view()

    async def action_quit(self) -> None:  # type: ignore[override]
        await self._shutdown_supervisor_and_exit()

    async def action_inc_min(self) -> None:
        sup = self.supervisor
        sup.min_workers = min(sup.min_workers + 1, max(sup.min_workers + 1, sup.max_workers))
        await self._update_view()

    async def action_dec_min(self) -> None:
        sup = self.supervisor
        sup.min_workers = max(0, sup.min_workers - 1)
        if sup.max_workers < sup.min_workers:
            sup.max_workers = sup.min_workers
        await self._update_view()

    async def action_inc_max(self) -> None:
        sup = self.supervisor
        sup.max_workers = max(sup.max_workers + 1, sup.min_workers)
        await self._update_view()

    async def action_dec_max(self) -> None:
        sup = self.supervisor
        sup.max_workers = max(sup.min_workers, sup.max_workers - 1)
        await self._update_view()

    async def action_shutdown(self) -> None:
        # Broadcast graceful shutdown to workers
        try:
            await self.supervisor.publish_shutdown(self.supervisor.shutdown_grace_s)
        except Exception:
            pass
        await self._update_view()

    async def action_reboot(self) -> None:
        # Gracefully stop supervisor, then re-exec the current CLI with same args
        await self._shutdown_supervisor(wait=True)
        self._reexec_current_process()

    async def _shutdown_supervisor_and_exit(self) -> None:
        # Request graceful shutdown and wait for supervisor to finish
        try:
            await self._shutdown_supervisor(wait=True)
        except Exception:
            pass
        # Exit TUI after supervisor stops (or on best effort)
        self.exit()

    async def _shutdown_supervisor(self, wait: bool = True) -> None:
        # Request graceful shutdown and optionally wait for completion
        self.supervisor.request_shutdown()
        if wait and self._supervisor_task is not None:
            try:
                await self._supervisor_task
            except Exception:
                pass

    def _reexec_current_process(self) -> None:
        # Replace current process with a fresh interpreter running the CLI with same args
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        env = os.environ.copy()
        argv = [sys.executable, "-m", "fast_app.cli", *sys.argv[1:]]
        os.execvpe(sys.executable, argv, env)


