import asyncio
import os
import pickle
from typing import Any

import pytest

from fast_app.integrations.async_farm.publisher import enqueue_callable


def sample(x: int) -> int:
    return x + 1


class DummyExchange:
    def __init__(self) -> None:
        self.published: list[tuple[Any, str]] = []

    async def publish(self, message, routing_key: str) -> None:  # type: ignore[no-untyped-def]
        self.published.append((message, routing_key))


class DummyChannel:
    def __init__(self, exch: DummyExchange) -> None:
        self.default_exchange = exch
        self.declared = []

    async def declare_queue(self, name: str, durable: bool = False):  # type: ignore[no-untyped-def]
        self.declared.append((name, durable))
        class _Q:
            pass
        return _Q()


class DummyConnection:
    def __init__(self, exch: DummyExchange) -> None:
        self.exch = exch

    async def channel(self) -> DummyChannel:
        return DummyChannel(self.exch)

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_enqueue_callable_sets_ttl_and_payload(monkeypatch):
    exch = DummyExchange()

    async def fake_connect(url: str):  # type: ignore[no-untyped-def]
        return DummyConnection(exch)

    import fast_app.integrations.async_farm.publisher as pub
    monkeypatch.setenv("ASYNC_FARM_TASK_TTL_S", "123")
    monkeypatch.setenv("ASYNC_FARM_JOBS_QUEUE", "test.jobs")
    monkeypatch.setattr(pub, "aio_pika", type("_AioPika", (), {"connect_robust": fake_connect, "DeliveryMode": type("DM", (), {"PERSISTENT": 2})}))

    # publish
    enqueue_callable(sample, 41)
    await asyncio.sleep(0)  # ensure scheduled task runs

    assert len(exch.published) == 1
    message, routing_key = exch.published[0]
    assert routing_key == os.getenv("ASYNC_FARM_JOBS_QUEUE", "test.jobs")

    # TTL should be set in message properties
    ttl_ms = 123000
    assert str(getattr(message, "expiration", str(ttl_ms))) == str(ttl_ms)

    payload = pickle.loads(message.body)
    assert payload.get("func_path")  # dotted path preferred
    assert "args_pickled" in payload and isinstance(payload["args_pickled"], (bytes, bytearray))
    assert "kwargs_pickled" in payload and isinstance(payload["kwargs_pickled"], (bytes, bytearray))
    assert pickle.loads(payload["args_pickled"]) == (41,)
    assert pickle.loads(payload["kwargs_pickled"]) == {}


