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
from typing import Any, Callable, Optional, Set, Awaitable
import inspect
import os
import time

import aio_pika
from aio_pika import ExchangeType, Message

from fast_app.utils.queue_utils import import_from_path, boot_if_needed
from fast_app.core.context import context
from fast_app.utils.serialisation import safe_int
from fast_app.utils.logging import setup_logging
from fast_app.utils.async_farm_utils import decode_message, AckGuard
import zlib

SOFT_TIMEOUT_S = int(os.getenv("SOFT_TIMEOUT_S", "30"))
HARD_TIMEOUT_S = int(os.getenv("HARD_TIMEOUT_S", "60"))

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
        self.func_path = self.payload.get("func_path")
        self.func: Optional[Callable[..., Any]] = self._parse_func_path()
        self.args, self.kwargs = self._parse_args_and_kwargs()
        self.context_snapshot = self.payload.get("ctx_snapshot")

        headers = (message.headers or {})
        self.soft_timeout_s = safe_int(headers.get("soft_timeout_s"), SOFT_TIMEOUT_S, 0, 24 * 3600)
        self.hard_timeout_s = safe_int(headers.get("hard_timeout_s"), HARD_TIMEOUT_S, 1, 48 * 3600)
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
        self.task_id: str = f"{os.getpid()}_{int(time.time() * 1_000_000)}"
        self.started_at: Optional[float] = None

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
                if self.on_soft_timeout:
                    await self.on_soft_timeout(self)
                logging.warning(f"[WORKER TASK] Soft timeout reached for {self.func_path} ({self.soft_timeout_s}s)")
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
                logging.warning(f"[WORKER TASK] Hard timeout reached for {self.func_path} ({self.hard_timeout_s}s)")
                await self.ack_guard.ack()
                if self.on_hard_timeout:
                    await self.on_hard_timeout(self)

        self.soft_t = asyncio.create_task(soft_timeout())
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
            res = task.result()
            if self.on_success:
                await self.on_success(self, res)
            logging.debug(f"[WORKER TASK] Task succeeded for {self.func_path}")
        except Exception as e:
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
            logging.warning(f"[WORKER TASK] No function to execute for {self.func_path}")
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
            if inspect.iscoroutinefunction(func):
                return await func(*self.args, **self.kwargs)
            # Execute sync callables off the event loop
            return await asyncio.to_thread(func, *self.args, **self.kwargs)

        if self.started_at is None:
            self.started_at = time.time()
        self.asyncio_task = asyncio.create_task(run_callable())
        self._start_timeouts()
        # add_done_callback expects a sync callable; wrap to schedule the async handler
        self.asyncio_task.add_done_callback(lambda t: asyncio.create_task(self._on_asyncio_task_done(t)))

    async def cancel(self) -> None:
        if self.asyncio_task and not self.asyncio_task.done():
            self.asyncio_task.cancel()