import asyncio
import pickle
from typing import Any

import pytest

from fast_app.integrations.async_farm.worker import AsyncFarmWorker


def inc(x: int) -> int:
    return x + 1


async def hang() -> None:
    await asyncio.sleep(10)


class DummyMessage:
    def __init__(self, body: bytes):
        self.body = body
        self.acked = False
        self.nacked = False

    async def ack(self) -> None:
        self.acked = True

    async def nack(self, requeue: bool = False) -> None:  # noqa: ARG002
        self.nacked = True


async def _run_worker_task(func: Any, *args: Any, **kwargs: Any) -> DummyMessage:
    w = AsyncFarmWorker()
    payload = {
        "ctx": None,
        "boot_args": {},
        "func_path": None,
        "func_pickled": pickle.dumps(func),
        "args": args,
        "kwargs": kwargs,
    }
    msg = DummyMessage(pickle.dumps(payload))
    await w.run_message_with_timeouts(msg)  # type: ignore[attr-defined]
    return msg


@pytest.mark.asyncio
async def test_worker_executes_sync_and_acks():
    msg = await _run_worker_task(inc, 1)
    assert msg.acked is True


@pytest.mark.asyncio
async def test_worker_soft_timeout_cancels_and_acks(monkeypatch):
    import fast_app.integrations.async_farm.worker as worker_mod
    monkeypatch.setattr(worker_mod, "SOFT_TIMEOUT_S", 0)
    monkeypatch.setattr(worker_mod, "HARD_TIMEOUT_S", 1)

    msg = await _run_worker_task(hang)
    assert msg.acked is True


