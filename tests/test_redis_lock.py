import pytest

from fast_app.core.lock import RedisDistributedLock, redis_lock


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.closed = False

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    async def eval(self, script: str, numkeys: int, key: str, token: str):
        if self.store.get(key) == token:
            del self.store[key]
            return 1
        return 0

    async def aclose(self):
        self.closed = True


class _FromURLSpy:
    def __init__(self, redis_instance: FakeRedis) -> None:
        self.redis_instance = redis_instance
        self.urls: list[str] = []

    def __call__(self, cls, url, decode_responses=True):
        self.urls.append(url)
        return self.redis_instance


@pytest.mark.asyncio
async def test_redis_distributed_lock_acquire_and_release():
    redis = FakeRedis()
    lock = RedisDistributedLock(redis=redis, key="lock:test", ttl_s=10)

    assert await lock.acquire() is True
    assert lock.acquired is True
    assert "lock:test" in redis.store

    assert await lock.release() is True
    assert lock.acquired is False
    assert "lock:test" not in redis.store


@pytest.mark.asyncio
async def test_redis_distributed_lock_when_already_locked():
    redis = FakeRedis()
    redis.store["lock:test"] = "existing-token"
    lock = RedisDistributedLock(redis=redis, key="lock:test", ttl_s=10)

    assert await lock.acquire() is False
    assert lock.acquired is False
    assert await lock.release() is False


@pytest.mark.asyncio
async def test_redis_distributed_lock_context_manager_releases():
    redis = FakeRedis()

    async with RedisDistributedLock(redis=redis, key="lock:test", ttl_s=10) as lock:
        assert lock.acquired is True
        assert "lock:test" in redis.store

    assert "lock:test" not in redis.store


@pytest.mark.asyncio
async def test_redis_lock_raises_when_no_url_can_be_resolved(monkeypatch):
    created = FakeRedis()

    from fast_app.core import lock as lock_module

    monkeypatch.delenv("REDIS_LOCK_URL", raising=False)
    monkeypatch.delenv("REDIS_SCHEDULER_URL", raising=False)
    monkeypatch.delenv("REDIS_CACHE_URL", raising=False)

    spy = _FromURLSpy(created)
    monkeypatch.setattr(lock_module.aioredis.Redis, "from_url", classmethod(spy))

    with pytest.raises(RuntimeError, match="Redis lock URL is not configured"):
        async with redis_lock("lock:test", ttl_s=10):
            pass

    assert spy.urls == []


@pytest.mark.asyncio
async def test_redis_lock_rejects_client_and_url_together():
    redis = FakeRedis()
    with pytest.raises(ValueError, match="Provide only one of redis_client or redis_url."):
        async with redis_lock(
            "lock:test",
            ttl_s=10,
            redis_client=redis,
            redis_url="redis://localhost:6379/1",
        ):
            pass


@pytest.mark.asyncio
async def test_redis_lock_auto_closes_owned_client(monkeypatch):
    created = FakeRedis()

    from fast_app.core import lock as lock_module

    monkeypatch.setattr(
        lock_module.aioredis.Redis,
        "from_url",
        classmethod(lambda cls, url, decode_responses=True: created),
    )

    async with redis_lock("lock:test", ttl_s=10, redis_url="redis://localhost:6379/1"):
        pass

    assert created.closed is True


@pytest.mark.asyncio
async def test_redis_lock_uses_fallback_priority(monkeypatch):
    created = FakeRedis()

    from fast_app.core import lock as lock_module

    monkeypatch.setenv("REDIS_CACHE_URL", "redis://localhost:6379/15")
    monkeypatch.setenv("REDIS_SCHEDULER_URL", "redis://localhost:6379/12")
    monkeypatch.setenv("REDIS_LOCK_URL", "redis://localhost:6379/11")

    spy = _FromURLSpy(created)
    monkeypatch.setattr(lock_module.aioredis.Redis, "from_url", classmethod(spy))

    async with redis_lock("lock:test", ttl_s=10):
        pass

    assert spy.urls == ["redis://localhost:6379/11"]

    monkeypatch.delenv("REDIS_LOCK_URL")
    async with redis_lock("lock:test", ttl_s=10):
        pass
    assert spy.urls[-1] == "redis://localhost:6379/12"

    monkeypatch.delenv("REDIS_SCHEDULER_URL")
    async with redis_lock("lock:test", ttl_s=10):
        pass
    assert spy.urls[-1] == "redis://localhost:6379/15"
