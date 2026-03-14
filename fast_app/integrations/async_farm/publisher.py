from __future__ import annotations

import asyncio
import os
import pickle
from typing import Any, Callable

import aio_pika
from aio_pika import Message
from aio_pika.pool import Pool

from fast_app.core.context import context
from fast_app.utils.queue_utils import to_dotted_path
from fast_app.utils.signed_payloads import dumps_signed_bytes


RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
SOFT_TIMEOUT_S = os.getenv("SOFT_TIMEOUT_S")
HARD_TIMEOUT_S = os.getenv("HARD_TIMEOUT_S")
_connection_pool: Pool | None = None
_channel_pool: Pool | None = None
_pool_loop: asyncio.AbstractEventLoop | None = None
_pool_init_lock: asyncio.Lock | None = None


async def _create_connection() -> aio_pika.abc.AbstractRobustConnection:
    return await aio_pika.connect_robust(RABBITMQ_URL)


async def _create_channel() -> aio_pika.abc.AbstractRobustChannel:
    connection_pool, _ = await _ensure_pools()
    async with connection_pool.acquire() as connection:
        channel = await connection.channel()
        queue_name = os.getenv("ASYNC_FARM_JOBS_QUEUE", "async_farm.jobs")
        await channel.declare_queue(queue_name, durable=True)
        setattr(channel, "_fast_app_queue_name", queue_name)
        return channel


async def _close_publisher_pools() -> None:
    global _channel_pool, _connection_pool, _pool_loop

    channel_pool = _channel_pool
    connection_pool = _connection_pool
    _channel_pool = None
    _connection_pool = None
    _pool_loop = None

    if channel_pool is not None and not channel_pool.is_closed:
        await channel_pool.close()

    if connection_pool is not None and not connection_pool.is_closed:
        await connection_pool.close()


async def _ensure_pools() -> tuple[Pool, Pool]:
    global _channel_pool, _connection_pool, _pool_init_lock, _pool_loop

    loop = asyncio.get_running_loop()
    if _pool_init_lock is None or _pool_loop is not loop:
        _pool_init_lock = asyncio.Lock()

    async with _pool_init_lock:
        if (
            (_pool_loop is not None and _pool_loop is not loop)
            or (_connection_pool is not None and _connection_pool.is_closed)
            or (_channel_pool is not None and _channel_pool.is_closed)
        ):
            await _close_publisher_pools()

        if _connection_pool is None:
            _connection_pool = Pool(_create_connection, max_size=1)

        if _channel_pool is None:
            _channel_pool = Pool(_create_channel, max_size=10)

        _pool_loop = loop
        return _connection_pool, _channel_pool


async def _publish_pickled(payload: dict[str, Any], ttl_ms: int, headers: dict[str, Any] | None = None) -> None:
    _, channel_pool = await _ensure_pools()

    async with channel_pool.acquire() as channel:
        queue_name = getattr(channel, "_fast_app_queue_name", os.getenv("ASYNC_FARM_JOBS_QUEUE", "async_farm.jobs"))
        body = dumps_signed_bytes(
            pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL),
            purpose="async_farm",
            env_var="ASYNC_FARM_SIGNING_KEY",
        )
        expiration = ttl_ms if ttl_ms > 0 else None
        props = {"headers": headers or {}}
        if expiration is not None:
            props["expiration"] = expiration
        await channel.default_exchange.publish(
            Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT, **props), routing_key=queue_name
        )


async def enqueue_callable(func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
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
    soft_timeout = kwargs.pop("__soft_timeout_s", None) or (int(SOFT_TIMEOUT_S) if SOFT_TIMEOUT_S else None)
    hard_timeout = kwargs.pop("__hard_timeout_s", None) or (int(HARD_TIMEOUT_S) if HARD_TIMEOUT_S else None)
    if soft_timeout is not None or hard_timeout is not None:
        headers = {}
        if soft_timeout is not None:
            headers["soft_timeout_s"] = int(soft_timeout)
        if hard_timeout is not None:
            headers["hard_timeout_s"] = int(hard_timeout)

    await _publish_pickled(payload, ttl_ms, headers=headers)

