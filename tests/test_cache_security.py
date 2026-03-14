import asyncio

import pytest

from fast_app.core.cache import Cache


class FakeAsyncRedis:
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    async def set(self, key: str, value: bytes) -> None:
        self.store[key] = value

    async def setex(self, key: str, _ttl: int, value: bytes) -> None:
        self.store[key] = value

    async def get(self, key: str) -> bytes | None:
        return self.store.get(key)

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)

    async def exists(self, key: str) -> int:
        return 1 if key in self.store else 0

    async def flushdb(self) -> None:
        self.store.clear()


@pytest.mark.asyncio
async def test_cache_rejects_tampered_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CACHE_SIGNING_KEY", "cache-secret")
    fake = FakeAsyncRedis()
    monkeypatch.setattr("fast_app.core.cache.r", fake)

    await Cache.set("user", {"id": 1})
    assert await Cache.get("user") == {"id": 1}

    fake.store["user"] = b"not-a-valid-signed-payload"
    assert await Cache.get("user", default="fallback") == "fallback"
    assert "user" not in fake.store


@pytest.mark.asyncio
async def test_cache_rejects_corrupted_unsigned_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CACHE_SIGNING_KEY", raising=False)
    fake = FakeAsyncRedis()
    fake.store["user"] = b"not-a-pickle"
    monkeypatch.setattr("fast_app.core.cache.r", fake)

    assert await Cache.get("user", default="fallback") == "fallback"
    assert "user" not in fake.store
