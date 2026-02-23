from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, NotRequired, Required, TypedDict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from redis import asyncio as aioredis

from fast_app.core.queue import queue
from fast_app.utils.datetime_utils import now


class SchedulerJobSpec(TypedDict, total=False):
    function: Required[Callable[..., Any]]
    run_every_s: int
    run_every: str
    cron: str
    timezone: str
    identifier: NotRequired[str]


_redis: aioredis.Redis | None = None
_DURATION_PART_RE = re.compile(r"(\d+)\s*(ms|s|m|h|d|w)", re.IGNORECASE)
_MONTH_ALIASES = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_DOW_ALIASES = {
    "sun": 0,
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
}


@dataclass(frozen=True)
class _CronField:
    values: frozenset[int]
    is_wildcard: bool


@dataclass(frozen=True)
class _CronSchedule:
    expression: str
    timezone: ZoneInfo
    minute: _CronField
    hour: _CronField
    day_of_month: _CronField
    month: _CronField
    day_of_week: _CronField


@dataclass(frozen=True)
class _SchedulerJob:
    identifier: str
    function: Callable[..., Any]
    interval_s: int | None = None
    cron: _CronSchedule | None = None


def _derive_identifier(func: Callable[..., Any]) -> str:
    module = getattr(func, "__module__", "unknown")
    qualname = getattr(func, "__qualname__", getattr(func, "__name__", "fn"))
    return f"{module}:{qualname}"


def _parse_human_duration_to_seconds(run_every: str) -> int:
    text = run_every.strip()
    if not text:
        raise ValueError("run_every cannot be empty.")

    total_ms = 0
    pos = 0
    for match in _DURATION_PART_RE.finditer(text):
        if match.start() != pos and text[pos : match.start()].strip():
            raise ValueError(f"Invalid run_every segment: '{text[pos:match.start()]}'")
        value = int(match.group(1))
        unit = match.group(2).lower()
        factor = {
            "ms": 1,
            "s": 1000,
            "m": 60_000,
            "h": 3_600_000,
            "d": 86_400_000,
            "w": 604_800_000,
        }[unit]
        total_ms += value * factor
        pos = match.end()

    if pos < len(text) and text[pos:].strip():
        raise ValueError(f"Invalid run_every segment: '{text[pos:]}'")

    if total_ms < 1000:
        raise ValueError("run_every must be at least 1 second.")

    if total_ms % 1000 != 0:
        raise ValueError("run_every must resolve to whole seconds.")

    return total_ms // 1000


def _parse_cron_value(
    token: str,
    *,
    min_value: int,
    max_value: int,
    aliases: dict[str, int] | None = None,
    allow_7_as_sunday: bool = False,
) -> int:
    key = token.lower()
    value = aliases.get(key) if aliases else None
    if value is None:
        try:
            value = int(token)
        except ValueError as exc:
            raise ValueError(f"Invalid cron token '{token}'") from exc

    if allow_7_as_sunday and value == 7:
        value = 0

    if not min_value <= value <= max_value:
        raise ValueError(f"Cron token '{token}' out of range {min_value}-{max_value}")

    return value


def _parse_cron_field(
    expression: str,
    *,
    min_value: int,
    max_value: int,
    aliases: dict[str, int] | None = None,
    allow_7_as_sunday: bool = False,
) -> _CronField:
    text = expression.strip()
    if not text:
        raise ValueError("Empty cron field.")

    if text == "*":
        return _CronField(
            values=frozenset(range(min_value, max_value + 1)),
            is_wildcard=True,
        )

    values: set[int] = set()
    for part in text.split(","):
        token = part.strip()
        if not token:
            raise ValueError(f"Invalid cron field '{expression}'")

        step = 1
        base = token
        if "/" in token:
            base, step_token = token.split("/", 1)
            step = int(step_token)
            if step <= 0:
                raise ValueError(f"Invalid cron step '{token}'")

        if base == "*":
            start, end = min_value, max_value
        elif "-" in base:
            start_token, end_token = base.split("-", 1)
            start = _parse_cron_value(
                start_token,
                min_value=min_value,
                max_value=max_value,
                aliases=aliases,
                allow_7_as_sunday=allow_7_as_sunday,
            )
            end = _parse_cron_value(
                end_token,
                min_value=min_value,
                max_value=max_value,
                aliases=aliases,
                allow_7_as_sunday=allow_7_as_sunday,
            )
            if start > end:
                raise ValueError(f"Invalid cron range '{token}'")
        else:
            start = _parse_cron_value(
                base,
                min_value=min_value,
                max_value=max_value,
                aliases=aliases,
                allow_7_as_sunday=allow_7_as_sunday,
            )
            end = max_value if "/" in token else start

        for value in range(start, end + 1, step):
            if allow_7_as_sunday and value == 7:
                values.add(0)
            else:
                values.add(value)

    return _CronField(values=frozenset(values), is_wildcard=False)


def _parse_cron_schedule(expression: str, timezone_name: str) -> _CronSchedule:
    parts = expression.split()
    if len(parts) != 5:
        raise ValueError(
            "cron must have exactly 5 fields: minute hour day month weekday"
        )

    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone '{timezone_name}'") from exc

    minute = _parse_cron_field(parts[0], min_value=0, max_value=59)
    hour = _parse_cron_field(parts[1], min_value=0, max_value=23)
    day_of_month = _parse_cron_field(parts[2], min_value=1, max_value=31)
    month = _parse_cron_field(
        parts[3],
        min_value=1,
        max_value=12,
        aliases=_MONTH_ALIASES,
    )
    day_of_week = _parse_cron_field(
        parts[4],
        min_value=0,
        max_value=6,
        aliases=_DOW_ALIASES,
        allow_7_as_sunday=True,
    )

    return _CronSchedule(
        expression=expression,
        timezone=tz,
        minute=minute,
        hour=hour,
        day_of_month=day_of_month,
        month=month,
        day_of_week=day_of_week,
    )


def _cron_matches(
    schedule: _CronSchedule, current_utc: datetime
) -> tuple[bool, datetime]:
    localized = current_utc.astimezone(schedule.timezone).replace(
        second=0, microsecond=0
    )
    cron_dow = (localized.weekday() + 1) % 7  # Sunday=0

    if localized.minute not in schedule.minute.values:
        return False, localized
    if localized.hour not in schedule.hour.values:
        return False, localized
    if localized.month not in schedule.month.values:
        return False, localized

    dom_match = localized.day in schedule.day_of_month.values
    dow_match = cron_dow in schedule.day_of_week.values

    if schedule.day_of_month.is_wildcard and schedule.day_of_week.is_wildcard:
        day_match = True
    elif schedule.day_of_month.is_wildcard:
        day_match = dow_match
    elif schedule.day_of_week.is_wildcard:
        day_match = dom_match
    else:
        # Cron semantics: when both fields are restricted, either can match.
        day_match = dom_match or dow_match

    return day_match, localized


def _normalize_jobs(jobs: list[SchedulerJobSpec]) -> list[_SchedulerJob]:
    normalized: list[_SchedulerJob] = []

    for job in jobs:
        identifier = job.get("identifier") or _derive_identifier(job["function"])
        has_run_every_s = "run_every_s" in job
        has_run_every = "run_every" in job
        has_cron = "cron" in job
        schedule_fields = sum([has_run_every_s, has_run_every, has_cron])

        if schedule_fields != 1:
            raise ValueError(
                f"Scheduler job '{identifier}' must define exactly one of: "
                "run_every_s, run_every, cron."
            )

        if has_cron:
            timezone_name = job.get("timezone", "UTC")
            cron = _parse_cron_schedule(job["cron"], timezone_name)
            normalized.append(
                _SchedulerJob(
                    identifier=identifier,
                    function=job["function"],
                    cron=cron,
                )
            )
            continue

        interval_s: int
        if has_run_every:
            interval_s = _parse_human_duration_to_seconds(job["run_every"])
        else:
            interval_s = int(job["run_every_s"])

        if interval_s < 1:
            raise ValueError(
                f"Scheduler job '{identifier}' interval must be >= 1 second."
            )

        normalized.append(
            _SchedulerJob(
                identifier=identifier,
                function=job["function"],
                interval_s=interval_s,
            )
        )

    return normalized


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is not None:
        return _redis
    _redis = aioredis.Redis.from_url(
        os.getenv("REDIS_SCHEDULER_URL", "redis://localhost:6379/12"),
        decode_responses=True,
    )
    # Ensure connection is healthy before proceeding
    await _redis.ping()
    return _redis


async def run_scheduler(jobs: list[SchedulerJobSpec]) -> None:
    r = await _get_redis()
    loop = asyncio.get_running_loop()
    tick_interval_s = 1.0
    next_tick = loop.time()
    normalized = _normalize_jobs(jobs)

    while True:
        # Ensure connection is alive; on failure, recreate it
        try:
            await r.ping()
        except Exception:
            global _redis
            _redis = None
            r = await _get_redis()

        current_utc = now(timezone.utc)
        for job in normalized:
            identifier = job.identifier
            func = job.function
            last_key = f"scheduler:last:{identifier}"
            lock_key: str
            lock_ttl_s: int

            if job.cron is not None:
                should_run, slot_local_dt = _cron_matches(job.cron, current_utc)
                if not should_run:
                    continue

                lock_key = (
                    f"scheduler:lock:{identifier}:cron:"
                    f"{slot_local_dt.strftime('%Y%m%d%H%M')}:{slot_local_dt.strftime('%z')}"
                )
                lock_ttl_s = 120
            else:
                interval_s = job.interval_s
                if interval_s is None:
                    continue
                lock_key = f"scheduler:lock:{identifier}"
                lock_ttl_s = interval_s

            try:
                # Acquire lock in a distributed-safe manner (interval or cron slot).
                acquired = bool(await r.set(lock_key, "1", ex=lock_ttl_s, nx=True))
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
