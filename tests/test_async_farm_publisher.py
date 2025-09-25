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



