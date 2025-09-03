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


