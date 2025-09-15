from __future__ import annotations

import asyncio
import contextvars
import os
import pickle
from typing import Any, Callable

import aio_pika
from aio_pika import Message

from fast_app.application import Application
from fast_app.core.context import context
from fast_app.utils.queue_utils import to_dotted_path


RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")


async def _publish_pickled(payload: dict[str, Any], ttl_ms: int, headers: dict[str, Any] | None = None) -> None:
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    try:
        channel = await connection.channel()
        queue_name = os.getenv("ASYNC_FARM_JOBS_QUEUE", "async_farm.jobs")
        await channel.declare_queue(queue_name, durable=True)
        body = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)
        expiration = str(ttl_ms) if ttl_ms > 0 else None
        props = {"headers": headers or {}}
        if expiration is not None:
            props["expiration"] = expiration
        await channel.default_exchange.publish(
            Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT, **props), routing_key=queue_name
        )
    finally:
        await connection.close()


def enqueue_callable(func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Serialize and publish callable execution request.

    - Tries dotted-path import first for safety and small payloads.
    - Falls back to pickling the function if not importable.
    - Preserves context via contextvars.Context and application boot args.
    - Applies per-message TTL via env ASYNC_FARM_TASK_TTL_S.
    """
    ttl_s = int(os.getenv("ASYNC_FARM_TASK_TTL_S", "600"))
    ttl_ms = ttl_s * 1000 if ttl_s > 0 else 0

    # Only support importable dotted path; do not send pickled functions for safety.
    func_path = to_dotted_path(func)

    # Optional compression for large payloads
    MAX_PAYLOAD_BYTES = int(os.getenv("ASYNC_FARM_MAX_PAYLOAD_BYTES", str(256 * 1024)))
    args_pickled = pickle.dumps(args, protocol=pickle.HIGHEST_PROTOCOL)
    kwargs_pickled = pickle.dumps(kwargs, protocol=pickle.HIGHEST_PROTOCOL)
    args_compressed = False
    kwargs_compressed = False
    if len(args_pickled) > 8 * 1024:
        import zlib
        args_pickled = zlib.compress(args_pickled)
        args_compressed = True
    if len(kwargs_pickled) > 8 * 1024:
        import zlib
        kwargs_pickled = zlib.compress(kwargs_pickled)
        kwargs_compressed = True

    # Capture context snapshot (picklable only) and app boot args for worker
    # app = Application()
    # boot_args = app.get_boot_args() if app.is_booted() else {}
    ctx_snapshot = context.snapshot(picklable_only=True, include_defaults=True)

    payload: dict[str, Any] = {
        "func_path": func_path,
        # Pickled args/kwargs (optionally compressed)
        "args_pickled": args_pickled,
        "kwargs_pickled": kwargs_pickled,
        "args_compressed": args_compressed,
        "kwargs_compressed": kwargs_compressed,
        # Context + boot data
        "ctx_snapshot": ctx_snapshot,
        # "boot_args": boot_args,
    }

    est_size = len(pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL))
    if est_size > MAX_PAYLOAD_BYTES:
        raise ValueError(f"AsyncFarm payload too large: {est_size} bytes > MAX_PAYLOAD_BYTES={MAX_PAYLOAD_BYTES}")

    # Optional per-message soft timeout header passthrough if user supplies special kwarg
    headers: dict[str, Any] | None = None
    soft_timeout = kwargs.pop("__soft_timeout_s", None)
    hard_timeout = kwargs.pop("__hard_timeout_s", None)
    if soft_timeout is not None or hard_timeout is not None:
        headers = {}
        if soft_timeout is not None:
            headers["soft_timeout_s"] = int(soft_timeout)
        if hard_timeout is not None:
            headers["hard_timeout_s"] = int(hard_timeout)

    async def publish() -> None:
        await _publish_pickled(payload, ttl_ms, headers=headers)

    loop = asyncio.get_running_loop()
    if loop.is_closed() or getattr(loop, "is_closing", lambda: False)():
        raise RuntimeError("event loop closed or closing")
    loop.create_task(publish())



