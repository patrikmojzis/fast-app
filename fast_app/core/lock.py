from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator

from redis import asyncio as aioredis

_RELEASE_LOCK_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
""".strip()


@dataclass(slots=True)
class RedisDistributedLock:
    """Distributed lock backed by Redis `SET ... NX EX` and token-checked release."""

    redis: aioredis.Redis
    key: str
    ttl_s: int
    token: str = field(default_factory=lambda: str(uuid.uuid4()))
    acquired: bool = False

    async def acquire(self) -> bool:
        if self.ttl_s < 1:
            raise ValueError("ttl_s must be >= 1.")

        self.acquired = bool(
            await self.redis.set(self.key, self.token, ex=self.ttl_s, nx=True)
        )
        return self.acquired

    async def release(self) -> bool:
        if not self.acquired:
            return False

        released = bool(
            await self.redis.eval(_RELEASE_LOCK_LUA, 1, self.key, self.token)
        )
        self.acquired = False
        return released

    async def __aenter__(self) -> RedisDistributedLock:
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.acquired:
            await self.release()


def _resolve_redis_lock_url() -> str:
    redis_url = (
        os.getenv("REDIS_LOCK_URL")
        or os.getenv("REDIS_SCHEDULER_URL")
        or os.getenv("REDIS_CACHE_URL")
    )
    if redis_url is None:
        raise RuntimeError(
            "Redis lock URL is not configured. Set REDIS_LOCK_URL, "
            "REDIS_SCHEDULER_URL, or REDIS_CACHE_URL, or pass redis_url."
        )
    return redis_url


@asynccontextmanager
async def redis_lock(
    key: str,
    *,
    ttl_s: int,
    redis_client: aioredis.Redis | None = None,
    redis_url: str | None = None,
    decode_responses: bool = True,
) -> AsyncIterator[RedisDistributedLock]:
    """
    Create a Redis distributed lock with optional managed Redis client lifecycle.

    If no `redis_url` is provided, it uses:
    REDIS_LOCK_URL -> REDIS_SCHEDULER_URL -> REDIS_CACHE_URL
    """
    if redis_client is not None and redis_url is not None:
        raise ValueError("Provide only one of redis_client or redis_url.")

    owns_client = redis_client is None
    client = redis_client
    if client is None:
        resolved_redis_url = redis_url or _resolve_redis_lock_url()
        client = aioredis.Redis.from_url(
            resolved_redis_url,
            decode_responses=decode_responses,
        )

    lock = RedisDistributedLock(redis=client, key=key, ttl_s=ttl_s)
    try:
        await lock.acquire()
        yield lock
    finally:
        try:
            if lock.acquired:
                await lock.release()
        finally:
            if owns_client:
                await client.aclose()


__all__ = ["RedisDistributedLock", "redis_lock"]
