import asyncio
import os
import pickle
from typing import Any

import pytest

from fast_app.integrations.async_farm import publisher
from fast_app.integrations.async_farm.publisher import enqueue_callable
from fast_app.utils.signed_payloads import loads_signed_bytes


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
async def test_enqueue_callable_signs_job_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    exchange = DummyExchange()

    async def fake_connect_robust(*args: Any, **kwargs: Any) -> DummyConnection:
        return DummyConnection(exchange)

    monkeypatch.setattr(publisher.aio_pika, "connect_robust", fake_connect_robust)

    await enqueue_callable(sample, 41)

    assert len(exchange.published) == 1
    message, routing_key = exchange.published[0]
    assert routing_key == "async_farm.jobs"

    raw_payload = loads_signed_bytes(
        message.body,
        purpose="async_farm",
        env_var="ASYNC_FARM_SIGNING_KEY",
    )
    payload = pickle.loads(raw_payload)

    assert payload["func_path"] == "tests.test_async_farm_publisher.sample"
    assert pickle.loads(payload["args_pickled"]) == (41,)


