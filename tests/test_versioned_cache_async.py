import pytest

from fast_app.decorators.db_cache_decorator import cached_db_retrieval
from fast_app.utils import versioned_cache


class BlockingSyncRedis:
    def incr(self, key: str):
        raise AssertionError(f"sync redis incr used for {key}")


class MemoryAsyncRedis:
    def __init__(self) -> None:
        self.store: dict[str, int | bytes] = {}
        self.closed = False

    async def get(self, key: str):
        return self.store.get(key)

    async def incr(self, key: str):
        value = int(self.store.get(key, 0)) + 1
        self.store[key] = value
        return value

    async def set(self, key: str, value: bytes):
        self.store[key] = value

    async def setex(self, key: str, ttl: int, value: bytes):
        self.store[key] = value

    async def delete(self, key: str):
        self.store.pop(key, None)

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
async def test_cached_db_retrieval_async_uses_async_redis(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setattr(versioned_cache, "_redis", BlockingSyncRedis(), raising=True)
    monkeypatch.setattr(versioned_cache, "_aredis", MemoryAsyncRedis(), raising=True)
    monkeypatch.setattr(versioned_cache, "_aredis_loop", None, raising=True)

    calls = {"count": 0}

    @cached_db_retrieval(namespace="items")
    async def load_item(item_id: int) -> dict[str, int]:
        calls["count"] += 1
        return {"item_id": item_id, "calls": calls["count"]}

    first = await load_item(1)
    second = await load_item(1)

    assert first == {"item_id": 1, "calls": 1}
    assert second == first
    assert calls["count"] == 1


def test_cached_db_retrieval_rejects_sync_functions():
    with pytest.raises(TypeError, match="async functions"):
        @cached_db_retrieval(namespace="items")
        def load_item(item_id: int) -> dict[str, int]:
            return {"item_id": item_id}


@pytest.mark.asyncio
async def test_get_value_deletes_corrupted_signed_payload(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    redis = MemoryAsyncRedis()
    redis.store["bad"] = b"not-json"
    monkeypatch.setattr(versioned_cache, "_aredis", redis, raising=True)
    monkeypatch.setattr(versioned_cache, "_aredis_loop", None, raising=True)

    assert await versioned_cache.get_value("bad") is None
    assert "bad" not in redis.store
