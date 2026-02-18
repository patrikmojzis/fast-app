from __future__ import annotations

import asyncio
import os
from typing import Any, Callable, NotRequired, TypedDict

from redis import asyncio as aioredis

from fast_app.core.queue import queue
from fast_app.utils.datetime_utils import now


class SchedulerJobSpec(TypedDict):
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
    _redis = aioredis.Redis.from_url(
        os.getenv("REDIS_SCHEDULER_URL", "redis://localhost:6379/12"),
        decode_responses=True
    )
    # Ensure connection is healthy before proceeding
    await _redis.ping()
    return _redis


async def run_scheduler(jobs: list[SchedulerJobSpec]) -> None:
    r = await _get_redis()
    loop = asyncio.get_running_loop()
    tick_interval_s = 1.0
    next_tick = loop.time()

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
            lock_key = f"scheduler:lock:{identifier}"
            last_key = f"scheduler:last:{identifier}"

            try:
                # Acquire a lock once per interval in a distributed-safe manner
                acquired = bool(await r.set(lock_key, "1", ex=run_every_s, nx=True))
            except Exception:
                # Connection issue: retry on next tick
                continue

            if acquired:
                await queue(func)
                # Fire-and-forget best-effort timestamp
                try:
                    await r.set(last_key, now().isoformat())
                except Exception:
                    pass

        next_tick += tick_interval_s
        sleep_for = next_tick - loop.time()
        if sleep_for <= 0:
            # Catch up to the next future tick so delays do not accumulate over time.
            missed_ticks = int((-sleep_for) // tick_interval_s) + 1
            next_tick += missed_ticks * tick_interval_s
            sleep_for = max(0.0, next_tick - loop.time())

        await asyncio.sleep(sleep_for)


__all__ = ["SchedulerJobSpec", "run_scheduler"]


