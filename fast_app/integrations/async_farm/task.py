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
from typing import Any, Callable, Optional, Set, Awaitable, List, Dict
import inspect
import contextvars
import builtins

import aio_pika
from aio_pika import ExchangeType, Message

from fast_app.utils.queue_utils import import_from_path
from fast_app.core.context import context
from fast_app.utils.serialisation import safe_int
from fast_app.utils.logging import setup_logging
from fast_app.utils.async_farm_utils import decode_message, AckGuard
import zlib


# ---------------------- scoped capture plumbing ----------------------
# Context set during task execution; copied into threads by asyncio.to_thread
_CURRENT_TASK_ID: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("fast_app_current_task_id", default=None)
_CURRENT_TASK_CAPTURE: contextvars.ContextVar[Optional[Callable[[str, str, Optional[Dict[str, Any]]], None]]] = contextvars.ContextVar("fast_app_current_task_capture", default=None)

_PRINT_HOOK_INSTALLED: bool = False
_ORIG_PRINT = builtins.print


def _install_print_hook() -> None:
    global _PRINT_HOOK_INSTALLED
    if _PRINT_HOOK_INSTALLED:
        return

    def _wrapped_print(*args: Any, **kwargs: Any) -> None:
        capture = _CURRENT_TASK_CAPTURE.get()
        if capture is not None:
            file_obj = kwargs.get("file", sys.stdout)
            stream_name = "stderr" if file_obj is sys.stderr else "stdout"
            try:
                text = " ".join(str(a) for a in args)
            except Exception:
                text = " ".join(repr(a) for a in args)
            try:
                capture(stream_name, text, None)
            except Exception:
                pass
        _ORIG_PRINT(*args, **kwargs)

    builtins.print = _wrapped_print  # type: ignore[assignment]
    _PRINT_HOOK_INSTALLED = True


_LOG_HANDLER_INSTALLED: bool = False


class _TaskCaptureLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
        capture = _CURRENT_TASK_CAPTURE.get()
        if capture is None:
            return
        try:
            msg = self.format(record)
        except Exception:
            try:
                msg = record.getMessage()
            except Exception:
                msg = str(record)
        try:
            capture(
                "log",
                msg,
                {
                    "level": record.levelname,
                    "logger": record.name,
                },
            )
        except Exception:
            pass


def _install_log_handler() -> None:
    global _LOG_HANDLER_INSTALLED
    if _LOG_HANDLER_INSTALLED:
        return
    handler = _TaskCaptureLogHandler()
    handler.setLevel(logging.NOTSET)
    # Keep formatting lightweight; rely on logger formatting if set
    root = logging.getLogger()
    root.addHandler(handler)
    _LOG_HANDLER_INSTALLED = True

class Task:
    def __init__(self, 
    message: aio_pika.IncomingMessage, *,
    on_soft_timeout: Optional[Callable[[Task], Awaitable[None]]] = None,
    on_hard_timeout: Optional[Callable[[Task], Awaitable[None]]] = None,
    on_success: Optional[Callable[[Task, Any], Awaitable[None]]] = None,
    on_failure: Optional[Callable[[Task, Exception], Awaitable[None]]] = None,
    on_done: Optional[Callable[[Task], Awaitable[None]]] = None,
    ):
        self.ack_guard = AckGuard(message)
        self.message = message
        self.payload = pickle.loads(message.body)
        self.task_id: str = str(getattr(message, "delivery_tag", f"{os.getpid()}-{int(time.time()*1000)}"))
        self.func_path = self.payload.get("func_path")
        self.func: Optional[Callable[..., Any]] = self._parse_func_path()
        self.args, self.kwargs = self._parse_args_and_kwargs()
        self.context_snapshot = self.payload.get("ctx_snapshot")

        headers = (message.headers or {})
        self.soft_timeout_s = headers.get("soft_timeout_s")
        self.hard_timeout_s = headers.get("hard_timeout_s")
        if self.soft_timeout_s is not None and self.hard_timeout_s is not None:
            if self.hard_timeout_s <= self.soft_timeout_s:
                self.hard_timeout_s = self.soft_timeout_s + 1

        self.asyncio_task: Optional[asyncio.Task[Any]] = None
        self.soft_t: Optional[asyncio.Task[Any]] = None
        self.hard_t: Optional[asyncio.Task[Any]] = None

        self.on_soft_timeout = on_soft_timeout
        self.on_hard_timeout = on_hard_timeout
        self.on_success = on_success
        self.on_failure = on_failure
        self.on_done = on_done

        # In-memory capture buffer (bounded)
        self._captured: List[Dict[str, Any]] = []
        self._captured_max_entries: int = 500

        # Execution metadata
        self.started_at: Optional[float] = None
        self.ended_at: Optional[float] = None
        self.status: str = "pending"  # pending | running | success | failure | soft_timeout | hard_timeout

    # ---------------------- capture helpers ----------------------
    def _append_capture(self, kind: str, text: str, meta: Optional[Dict[str, Any]]) -> None:
        entry = {
            "ts": time.time(),
            "kind": kind,  # stdout | stderr | log
            "text": text,
        }
        if meta:
            entry.update(meta)
        self._captured.append(entry)
        if len(self._captured) > self._captured_max_entries:
            # Drop oldest to keep memory bounded
            self._captured = self._captured[-self._captured_max_entries :]

    def get_captured_text(self, max_chars: int = 1024000) -> str:
        parts: List[str] = []
        for e in self._captured:
            ts = time.strftime("%H:%M:%S", time.localtime(float(e.get("ts", time.time()))))
            if e.get("kind") == "log":
                level = e.get("level", "INFO")
                logger_name = e.get("logger", "")
                parts.append(f"[{ts}] {level:<7} {logger_name}: {e.get('text','')}")
            else:
                parts.append(f"[{ts}] {e.get('kind')}: {e.get('text','')}")
        text = "\n".join(parts)
        if len(text) > max_chars:
            return text[-max_chars:]
        return text

    def to_snapshot(self, *, include_logs: bool = True, max_chars: int = 1024000) -> Dict[str, Any]:
        started_at = self.started_at
        ended_at = self.ended_at
        duration_s: Optional[float] = None
        try:
            if started_at is not None and ended_at is not None:
                duration_s = max(0.0, float(ended_at) - float(started_at))
            elif started_at is not None and ended_at is None:
                duration_s = max(0.0, float(time.time()) - float(started_at))
        except Exception:
            duration_s = None

        snap: Dict[str, Any] = {
            "id": self.task_id,
            "func_path": self.func_path,
            "status": self.status,
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_s": duration_s,
        }
        if include_logs:
            try:
                snap["logs"] = self.get_captured_text(max_chars=max_chars)
            except Exception:
                snap["logs"] = ""
        return snap

    def _parse_func_path(self) -> Optional[Callable[..., Any]]:
        func_path = self.payload.get("func_path")
        if not func_path:
            return None

        try:
            func: Callable[..., Any] = import_from_path(func_path)
        except Exception:
            return None
        
        return func

    def _parse_args_and_kwargs(self) -> tuple[Any, Any]:
        args_pickled = None
        kwargs_pickled = None
        if self.payload.get("args_compressed"):
            args_pickled = zlib.decompress(self.payload.get("args_pickled"))
        elif self.payload.get("args_pickled"):
            args_pickled = self.payload.get("args_pickled")
        
        if self.payload.get("kwargs_compressed"):
            kwargs_pickled = zlib.decompress(self.payload.get("kwargs_pickled"))
        elif self.payload.get("kwargs_pickled"):
            kwargs_pickled = self.payload.get("kwargs_pickled")
        
        args = pickle.loads(args_pickled) if args_pickled else ()
        kwargs = pickle.loads(kwargs_pickled) if kwargs_pickled else {}
        return args, kwargs

    def _start_timeouts(self):
        async def soft_timeout() -> None:
            if self.soft_timeout_s <= 0:
                return
            for _ in range(self.soft_timeout_s):
                if self.asyncio_task and self.asyncio_task.done():
                    return
                await asyncio.sleep(1)

            if self.asyncio_task and not self.asyncio_task.done():
                self.status = "soft_timeout"
                if self.on_soft_timeout:
                    await self.on_soft_timeout(self)
                logging.error(f"[WORKER TASK] Soft timeout reached for {self.func_path} ({self.soft_timeout_s}s)")
                # Cancel the asyncio Task wrapper; actual work may still be running in a thread
                # Hard-timeout watchdog remains responsible for finalization
                self.asyncio_task.cancel()

        async def hard_timeout() -> None:
            if self.hard_timeout_s <= 0:
                return
            for _ in range(self.hard_timeout_s):
                if self.asyncio_task and self.asyncio_task.done():
                    return
                await asyncio.sleep(1)

            if self.asyncio_task and not self.asyncio_task.done():
                logging.error(f"[WORKER TASK] Hard timeout reached for {self.func_path} ({self.hard_timeout_s}s)")
                await self.ack_guard.ack()
                self.status = "hard_timeout"
                if self.on_hard_timeout:
                    await self.on_hard_timeout(self)

        if self.soft_timeout_s:
            self.soft_t = asyncio.create_task(soft_timeout())

        if self.hard_timeout_s:
            self.hard_t = asyncio.create_task(hard_timeout())

    async def _on_asyncio_task_done(self, task: asyncio.Task[Any]) -> None:
        if self.soft_t:
            self.soft_t.cancel()
        if self.hard_t:
            self.hard_t.cancel()
        await self.ack_guard.ack()

        if self.on_done:
            await self.on_done(self)

        try:
            self.ended_at = time.time()
            res = task.result()
            self.status = "success"
            if self.on_success:
                await self.on_success(self, res)
            logging.debug(f"[WORKER TASK] Task succeeded for {self.func_path}")
        except Exception as e:
            self.ended_at = self.ended_at or time.time()
            self.status = "failure"
            logging.exception(f"[WORKER TASK] Task failed for {self.func_path}", exc_info=e)
            if self.on_failure:
                await self.on_failure(self, e)

    def add_success_callback(self, callback: Callable[[Task, Any], Awaitable[None]]) -> None:
        self.on_success = callback

    def add_failure_callback(self, callback: Callable[[Task, Exception], Awaitable[None]]) -> None:
        self.on_failure = callback

    def add_soft_timeout_callback(self, callback: Callable[[Task], Awaitable[None]]) -> None:
        self.on_soft_timeout = callback

    def add_hard_timeout_callback(self, callback: Callable[[Task], Awaitable[None]]) -> None:
        self.on_hard_timeout = callback

    def add_done_callback(self, callback: Callable[[Task], Awaitable[None]]) -> None:
        self.on_done = callback

    async def run(self):
        if not self.func:
            logging.error(f"[WORKER TASK] No function to execute for {self.func_path}")
            # Nothing to execute; still finalize bookkeeping so worker can drop the task
            await self.ack_guard.ack()
            if self.on_done:
                await self.on_done(self)
            return

        async def run_callable() -> Any:
            logging.debug(f"[WORKER TASK] Running {self.func_path} with args {self.args} and kwargs {self.kwargs}")
            if self.context_snapshot:
                context.install(self.context_snapshot)
            func = self.func
            assert func is not None
            # Install capture plumbing once per process
            _install_print_hook()
            _install_log_handler()

            # Set task-scoped context for both async path and threads spawned via asyncio.to_thread
            tok_id = _CURRENT_TASK_ID.set(self.task_id)
            tok_cap = _CURRENT_TASK_CAPTURE.set(lambda kind, text, meta: self._append_capture(kind, text, meta))
            try:
                if inspect.iscoroutinefunction(func):
                    return await func(*self.args, **self.kwargs)
                # Execute sync callables off the event loop, with contextvars propagated
                return await asyncio.to_thread(func, *self.args, **self.kwargs)
            finally:
                try:
                    _CURRENT_TASK_CAPTURE.reset(tok_cap)
                except Exception:
                    pass
                try:
                    _CURRENT_TASK_ID.reset(tok_id)
                except Exception:
                    pass

        self.asyncio_task = asyncio.create_task(run_callable())
        self.started_at = time.time()
        self.status = "running"
        self._start_timeouts()
        # add_done_callback expects a sync callable; wrap to schedule the async handler
        self.asyncio_task.add_done_callback(lambda t: asyncio.create_task(self._on_asyncio_task_done(t)))

    async def cancel(self) -> None:
        if self.asyncio_task and not self.asyncio_task.done():
            self.asyncio_task.cancel()