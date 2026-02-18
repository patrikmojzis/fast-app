import asyncio

import pytest

from fast_app.core import scheduler


class DummyRedis:
    async def ping(self):
        return True
    async def set(self, *args, **kwargs):
        return True


@pytest.mark.asyncio
async def test_scheduler_runs_job(monkeypatch):
    executed = asyncio.Event()

    async def job():
        executed.set()

    async def fake_get_redis():
        return DummyRedis()
    monkeypatch.setattr(scheduler, "_get_redis", fake_get_redis)
    monkeypatch.setattr(scheduler, "queue", lambda func, *a, **k: asyncio.create_task(func()))
    task = asyncio.create_task(scheduler.run_scheduler([{"run_every_s": 1, "function": job}]))
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
    monkeypatch.setattr(scheduler.asyncio, "get_running_loop", lambda: FakeLoop([100.0, 100.25]))
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

