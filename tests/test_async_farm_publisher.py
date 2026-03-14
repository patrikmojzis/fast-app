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
        self.close_calls = 0

    async def declare_queue(self, name: str, durable: bool = False):  # type: ignore[no-untyped-def]
        self.declared.append((name, durable))

        class _Q:
            pass

        return _Q()

    async def close(self) -> None:
        self.close_calls += 1


class DummyConnection:
    def __init__(self, exch: DummyExchange) -> None:
        self.exch = exch
        self.close_calls = 0
        self.channels: list[DummyChannel] = []

    async def channel(self) -> DummyChannel:
        channel = DummyChannel(self.exch)
        self.channels.append(channel)
        return channel

    async def close(self) -> None:
        self.close_calls += 1


@pytest.mark.asyncio
async def test_enqueue_callable_signs_job_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    await publisher._close_publisher_pools()
    exchange = DummyExchange()
    connections: list[DummyConnection] = []
    connect_calls = 0

    async def fake_connect_robust(*args: Any, **kwargs: Any) -> DummyConnection:
        nonlocal connect_calls
        connect_calls += 1
        connection = DummyConnection(exchange)
        connections.append(connection)
        return connection

    monkeypatch.setattr(publisher.aio_pika, "connect_robust", fake_connect_robust)

    try:
        await enqueue_callable(sample, 41)
        await enqueue_callable(sample, 42)

        assert connect_calls == 1
        assert len(connections) == 1
        assert connections[0].close_calls == 0
        assert len(exchange.published) == 2
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
    finally:
        await publisher._close_publisher_pools()


@pytest.mark.asyncio
async def test_close_publisher_pools_recreates_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    await publisher._close_publisher_pools()
    exchange = DummyExchange()
    connections: list[DummyConnection] = []
    connect_calls = 0

    async def fake_connect_robust(*args: Any, **kwargs: Any) -> DummyConnection:
        nonlocal connect_calls
        connect_calls += 1
        connection = DummyConnection(exchange)
        connections.append(connection)
        return connection

    monkeypatch.setattr(publisher.aio_pika, "connect_robust", fake_connect_robust)

    try:
        await enqueue_callable(sample, 41)

        assert connect_calls == 1
        assert len(connections) == 1
        assert len(connections[0].channels) == 1

        await publisher._close_publisher_pools()

        assert connections[0].close_calls == 1
        assert connections[0].channels[0].close_calls == 1

        await enqueue_callable(sample, 42)

        assert connect_calls == 2
        assert len(connections) == 2
        assert connections[1] is not connections[0]
        assert connections[1].close_calls == 0
        assert len(exchange.published) == 2
    finally:
        await publisher._close_publisher_pools()

