from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Callable, NotRequired, TypedDict

from redis import asyncio as aioredis

from fast_app.config import REDIS_CRON_DB
from fast_app.core.queue import queue


class CronJobSpec(TypedDict):
    run_every_s: int
    function: Callable[..., Any]
    identifier: NotRequired[str]


_redis: aioredis.Redis | None = None


def _derive_identifier(func: Callable[..., Any]) -> str:
    module = getattr(func, "__module__", "unknown")
    qualname = getattr(func, "__qualname__", getattr(func, "__name__", "fn"))
    return f"{module}:{qualname}"


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is not None:
        return _redis
    _redis = aioredis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=REDIS_CRON_DB,
        decode_responses=True,
    )
    # Ensure connection is healthy before proceeding
    await _redis.ping()
    return _redis


async def run_cron(jobs: list[CronJobSpec]) -> None:
    r = await _get_redis()

    # Normalize jobs with identifiers
    normalized: list[tuple[str, int, Callable[..., Any]]] = []
    for job in jobs:
        identifier = job.get("identifier") or _derive_identifier(job["function"])
        normalized.append((identifier, job["run_every_s"], job["function"]))

    while True:
        # Ensure connection is alive; on failure, recreate it
        try:
            await r.ping()
        except Exception:
            global _redis
            _redis = None
            r = await _get_redis()

        for identifier, run_every_s, func in normalized:
            lock_key = f"cron:lock:{identifier}"
            last_key = f"cron:last:{identifier}"

            try:
                # Acquire a lock once per interval in a distributed-safe manner
                acquired = bool(await r.set(lock_key, "1", ex=run_every_s, nx=True))
            except Exception:
                # Connection issue: retry on next tick
                continue

            if acquired:
                queue(func)
                # Fire-and-forget best-effort timestamp
                try:
                    await r.set(last_key, datetime.now(timezone.utc).isoformat())
                except Exception:
                    pass

        await asyncio.sleep(1)


__all__ = ["CronJobSpec", "run_cron"]


