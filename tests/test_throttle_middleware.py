import asyncio
import types

import pytest
from quart import Quart, jsonify

from fast_app import Route
from fast_app.core.middlewares.throttle_middleware import ThrottleMiddleware
from fast_app.utils.routing_utils import register_routes


async def hello():
    return jsonify({"ok": True})


@pytest.mark.asyncio
async def test_throttle_blocks_after_limit(monkeypatch):
    # Monkeypatch Cache to avoid real Redis
    from fast_app.core import cache as cache_module
    import fast_app.core.middlewares.throttle_middleware as throttle_module

    store: dict[str, tuple[int, float]] = {}

    async def fake_set(key: str, value, expire_in_m=None):
        ttl = (expire_in_m or 0) * 60 if expire_in_m else 0
        store[key] = (value, asyncio.get_event_loop().time() + ttl if ttl else 0)

    async def fake_get(key: str, default=None):
        val = store.get(key)
        if not val:
            return default
        value, expires_at = val
        if expires_at and asyncio.get_event_loop().time() > expires_at:
            store.pop(key, None)
            return default
        return value

    async def fake_increment(key: str, amount: int = 1):
        current = await fake_get(key, 0)
        await fake_set(key, int(current) + amount, expire_in_m=1 / 60)
        return int(current) + amount

    class FakeRedis:
        def __init__(self):
            self._store: dict[str, tuple[int, float]] = {}

        async def incr(self, key: str, amount: int = 1):
            value, expires_at = self._store.get(key, (0, 0))
            now = asyncio.get_event_loop().time()
            if expires_at and now > expires_at:
                value, expires_at = 0, 0
            value += amount
            self._store[key] = (value, expires_at)
            return value

        async def expire(self, key: str, ttl_seconds: int):
            value, _ = self._store.get(key, (0, 0))
            self._store[key] = (value, asyncio.get_event_loop().time() + ttl_seconds)

    fake_redis = FakeRedis()
    monkeypatch.setattr(cache_module, "r", fake_redis, raising=True)
    monkeypatch.setattr(throttle_module, "r", fake_redis, raising=True)

    app = Quart(__name__)
    routes = [
        Route.get(
            "/hello",
            hello,
            middlewares=[ThrottleMiddleware(limit=2, window_seconds=1)],
        )
    ]
    register_routes(app, routes)
    client = app.test_client()

    # Two requests allowed
    r1 = await client.get("/hello")
    assert r1.status_code == 200
    r2 = await client.get("/hello")
    assert r2.status_code == 200

    # Third request within window should be throttled
    r3 = await client.get("/hello")
    assert r3.status_code == 429


