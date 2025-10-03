from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from typing import Optional, TYPE_CHECKING, Dict, List, Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Static, DataTable, Log
from textual.containers import Vertical
from textual.widgets.data_table import RowKey

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
        Binding("r", "reboot", "Reboot", show=True),
        Binding("t", "toggle_view", "Tasks", show=True),
    ]

    def __init__(self, supervisor: 'AsyncFarmSupervisor') -> None:
        super().__init__()
        self.supervisor = supervisor
        self._metrics: Optional[Static] = None
        self._table: Optional[DataTable] = None
        self._supervisor_task: Optional[asyncio.Task[None]] = None
        self._log_view: Optional[Log] = None
        self._log_heading: Optional[Static] = None
        self._view_mode: str = "workers"  # workers | tasks
        self._current_tasks: List[Dict[str, Any]] = []
        # Map DataTable row keys to indices in _current_tasks
        self._rowkey_to_index: Dict[object, int] = {}
        self._refresh_timer: Optional[Any] = None

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Header(show_clock=True)
        with Vertical():
            self._metrics = Static()
            yield self._metrics
            self._table = DataTable(zebra_stripes=True, cursor_type="row")
            # Split remaining vertical space evenly between table and log when visible
            try:
                self._table.styles.height = "1fr"  # type: ignore[attr-defined]
            except Exception:
                pass
            self._table.add_columns("Worker", "PID", "Active", "Completed", "Uptime")
            yield self._table
            self._log_heading = Static("📜 Task Logs", classes="")
            # Hidden by default in workers view; shown in tasks view
            self._log_heading.display = False
            yield self._log_heading
            self._log_view = Log(highlight=True, auto_scroll=True)
            try:
                self._log_view.styles.height = "1fr"  # type: ignore[attr-defined]
            except Exception:
                pass
            # Hidden by default in workers view; shown in tasks view
            self._log_view.display = False
            yield self._log_view
        yield Footer()

    async def on_mount(self) -> None:  # type: ignore[override]
        # Start supervisor in background within the same event loop
        if self._supervisor_task is None:
            self._supervisor_task = asyncio.create_task(self.supervisor.run())

        self._start_refresh()
        await self._update_view()

    def _start_refresh(self) -> None:
        if self._refresh_timer is None:
            self._refresh_timer = self.set_interval(1.0, self._update_view)

    def _stop_refresh(self) -> None:
        try:
            if self._refresh_timer is not None:
                self._refresh_timer.cancel()
        except Exception:
            pass
        self._refresh_timer = None

    async def _update_view(self) -> None:
        sup = self.supervisor
        now = time.time()

        # If supervisor stopped (error or graceful), exit TUI
        if self._supervisor_task and self._supervisor_task.done():
            self.exit()
            return

        if self._view_mode == "workers":
            # Hide log view in workers mode
            if self._log_view:
                self._log_view.display = False
            if self._log_heading:
                self._log_heading.display = False
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
                self._table.clear(columns=True)
                self._table.add_columns("Worker", "PID", "Active", "Completed", "Uptime")
                for worker_id, state in sup.workers.items():
                    pid = getattr(state.get("process"), "pid", "-")
                    active = int(state.get("active_tasks", 0))
                    completed = f"{state.get('task_success_count', 0)}/{state.get('task_failure_count', 0)}"
                    last_hb = state.get("last_heartbeat_timestamp") or 0.0
                    start_ts = float(state.get("start_timestamp") or now)
                    uptime = _format_seconds_delta(now - start_ts)
                    icon = "🟢" if last_hb and now - float(last_hb) <= 3 * max(1, self.supervisor.heartbeat_interval_s) else "🟠"
                    self._table.add_row(f"{icon} {worker_id}", str(pid), str(active), completed, uptime)
            if self._log_view:
                self._log_view.clear()
        else:
            # When in tasks view we keep the snapshot static (no periodic refresh)
            # Do nothing here; rendering occurs on toggle into tasks view or on explicit refresh
            return

    def _format_ts(self, ts: Any) -> str:
        try:
            f = float(ts)
        except Exception:
            return "-"
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f))

    async def _render_tasks_snapshot(self) -> None:
        sup = self.supervisor
        tasks: List[Dict[str, Any]] = []
        try:
            for worker_id, lst in getattr(sup, "tasks_snapshots", {}).items():
                for t in lst:
                    item = dict(t)
                    item["worker_id"] = worker_id
                    tasks.append(item)
        except Exception:
            tasks = []

        # Sort by started_at desc
        try:
            tasks.sort(key=lambda x: float(x.get("started_at") or 0.0), reverse=True)
        except Exception:
            pass

        total_tasks = len(tasks)
        if self._metrics:
            self._metrics.update(f"🗂️ Tasks snapshot: {total_tasks} tasks (press 't' to go back)")

        if self._table:
            self._table.clear(columns=True)
            self._table.add_columns("Func", "Status", "Worker", "Duration", "StartedAt", "EndedAt")
            self._rowkey_to_index = {}
            for i, t in enumerate(tasks):
                wid = t.get("worker_id") or "-"
                status = t.get("status") or "-"
                func = t.get("func_path") or "-"
                dur = t.get("duration_s")
                started_at = t.get("started_at")
                ended_at = t.get("ended_at")
                dur_txt = _format_seconds_delta(float(dur)) if isinstance(dur, (int, float)) else "-"
                started_txt = self._format_ts(started_at) if started_at else "-"
                ended_txt = (self._format_ts(ended_at) if ended_at else ("running" if status == "running" else "-"))
                row_key = self._table.add_row(str(func), str(status), str(wid), dur_txt, started_txt, ended_txt)
                self._rowkey_to_index[row_key] = i

        self._current_tasks = tasks

    async def _update_log_view_from_selection(self, row_key: RowKey) -> None:
        if self._view_mode != "tasks" or not self._table or not self._log_view:
            return

        idx = self._rowkey_to_index.get(row_key)
        logs = ""
        if idx is not None and 0 <= idx < len(self._current_tasks):
            try:
                logs = str(self._current_tasks[idx].get("logs") or "")
            except Exception:
                logs = ""
        self._log_view.clear()
        if logs:
            self._log_view.write(logs)

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

    async def action_toggle_view(self) -> None:
        self._view_mode = "tasks" if self._view_mode == "workers" else "workers"
        if self._view_mode == "tasks":
            # Stop auto refresh and render a static snapshot
            self._stop_refresh()
            if self._metrics:
                self._metrics.update(f"🗂️ Loading tasks snapshot...")
            try:
                await self.supervisor.request_tasks_snapshot()
                await asyncio.sleep(1)
            except Exception:
                pass
            if self._log_view:
                self._log_view.display = True
            if self._log_heading:
                self._log_heading.display = True
            await self._render_tasks_snapshot()
        else:
            # Resume workers view refresh
            if self._log_view:
                self._log_view.display = False
            if self._log_heading:
                self._log_heading.display = False
            self._start_refresh()
            await self._update_view()

    async def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:  # type: ignore[override]
        if self._view_mode != "tasks":
            return
        await self._update_log_view_from_selection(event.row_key)

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


