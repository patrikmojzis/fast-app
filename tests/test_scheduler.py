import asyncio
from datetime import datetime, timezone

import pytest

from fast_app.core import scheduler


class DummyRedis:
    async def ping(self):
        return True

    async def set(self, *args, **kwargs):
        return True


class MemoryRedis:
    def __init__(self):
        self.keys: set[str] = set()

    async def ping(self):
        return True

    async def set(self, key, *args, **kwargs):
        if kwargs.get("nx"):
            if key in self.keys:
                return False
            self.keys.add(key)
            return True
        self.keys.add(key)
        return True


@pytest.mark.asyncio
async def test_scheduler_runs_job(monkeypatch):
    executed = asyncio.Event()

    async def job():
        executed.set()

    async def fake_get_redis():
        return DummyRedis()

    monkeypatch.setattr(scheduler, "_get_redis", fake_get_redis)
    monkeypatch.setattr(
        scheduler, "queue", lambda func, *a, **k: asyncio.create_task(func())
    )
    task = asyncio.create_task(
        scheduler.run_scheduler([{"run_every_s": 1, "function": job}])
    )
    await asyncio.sleep(0.1)
    assert executed.is_set()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


class FakeLoop:
    def __init__(self, times):
        self._times = iter(times)

    def time(self):
        return next(self._times)


@pytest.mark.asyncio
async def test_scheduler_sleep_uses_monotonic_deadline(monkeypatch):
    sleep_calls = []

    async def fake_get_redis():
        return DummyRedis()

    async def fake_sleep(delay):
        sleep_calls.append(delay)
        raise asyncio.CancelledError

    monkeypatch.setattr(scheduler, "_get_redis", fake_get_redis)
    monkeypatch.setattr(
        scheduler.asyncio, "get_running_loop", lambda: FakeLoop([100.0, 100.25])
    )
    monkeypatch.setattr(scheduler.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await scheduler.run_scheduler([])

    assert sleep_calls == [pytest.approx(0.75, abs=0.0001)]


@pytest.mark.asyncio
async def test_scheduler_sleep_catches_up_when_behind(monkeypatch):
    sleep_calls = []

    async def fake_get_redis():
        return DummyRedis()

    async def fake_sleep(delay):
        sleep_calls.append(delay)
        raise asyncio.CancelledError

    monkeypatch.setattr(scheduler, "_get_redis", fake_get_redis)
    monkeypatch.setattr(
        scheduler.asyncio,
        "get_running_loop",
        lambda: FakeLoop([100.0, 105.2, 106.1]),
    )
    monkeypatch.setattr(scheduler.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await scheduler.run_scheduler([])

    assert sleep_calls == [0.0]


def test_parse_human_duration_to_seconds():
    assert scheduler._parse_human_duration_to_seconds("60s") == 60
    assert scheduler._parse_human_duration_to_seconds("61h") == 61 * 60 * 60
    assert scheduler._parse_human_duration_to_seconds("1h30m") == 5400
    assert scheduler._parse_human_duration_to_seconds("2m 15s") == 135
    assert scheduler._parse_human_duration_to_seconds("1000ms") == 1


def test_parse_human_duration_rejects_sub_second():
    with pytest.raises(ValueError, match="at least 1 second"):
        scheduler._parse_human_duration_to_seconds("60ms")

    with pytest.raises(ValueError, match="whole seconds"):
        scheduler._parse_human_duration_to_seconds("1500ms")


def test_cron_matches_weekend_midnight_in_timezone():
    cron = scheduler._parse_cron_schedule("0 0 * * sat,sun", "Europe/Prague")

    # 2026-02-20 23:00 UTC == 2026-02-21 00:00 Europe/Prague (Saturday)
    weekend_match, _ = scheduler._cron_matches(
        cron,
        datetime(2026, 2, 20, 23, 0, tzinfo=timezone.utc),
    )
    assert weekend_match is True

    # 2026-02-19 23:00 UTC == 2026-02-20 00:00 Europe/Prague (Friday)
    weekday_match, _ = scheduler._cron_matches(
        cron,
        datetime(2026, 2, 19, 23, 0, tzinfo=timezone.utc),
    )
    assert weekday_match is False


@pytest.mark.asyncio
async def test_scheduler_cron_runs_once_per_slot(monkeypatch):
    queued = []
    redis = MemoryRedis()
    now_values = iter(
        [
            datetime(2026, 2, 18, 10, 0, 1, tzinfo=timezone.utc),
            datetime(2026, 2, 18, 10, 0, 1, tzinfo=timezone.utc),
            datetime(2026, 2, 18, 10, 0, 30, tzinfo=timezone.utc),
            datetime(2026, 2, 18, 10, 1, 0, tzinfo=timezone.utc),
            datetime(2026, 2, 18, 10, 1, 0, tzinfo=timezone.utc),
        ]
    )
    sleep_count = 0

    async def fake_get_redis():
        return redis

    async def fake_queue(func, *args, **kwargs):
        queued.append(func)

    def fake_now(tz=None):
        return next(now_values)

    async def fake_sleep(delay):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count >= 3:
            raise asyncio.CancelledError

    async def job():
        return None

    monkeypatch.setattr(scheduler, "_get_redis", fake_get_redis)
    monkeypatch.setattr(scheduler, "queue", fake_queue)
    monkeypatch.setattr(scheduler, "now", fake_now)
    monkeypatch.setattr(scheduler.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await scheduler.run_scheduler([{"cron": "* * * * *", "function": job}])

    assert len(queued) == 2
