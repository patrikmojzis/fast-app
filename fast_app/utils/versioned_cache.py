import asyncio
import os
from typing import Optional

import redis
import redis.asyncio as aioredis

from fast_app.utils.signed_payloads import SignedPayloadError, dumps_signed_bytes, loads_signed_bytes


_redis_url = os.getenv("REDIS_DATABASE_CACHE_URL", "redis://localhost:6379/13")
_redis = redis.Redis.from_url(_redis_url)
_aredis: aioredis.Redis | None = None
_aredis_loop: asyncio.AbstractEventLoop | None = None


def _version_key_for_collection(collection_name: str) -> str:
    return f"db:ver:{collection_name}"


def _sign_value(value: bytes) -> bytes:
    return dumps_signed_bytes(
        value,
        purpose="db_cache",
        env_var="DB_CACHE_SIGNING_KEY",
    )


def _load_value(raw: bytes) -> bytes:
    return loads_signed_bytes(
        raw,
        purpose="db_cache",
        env_var="DB_CACHE_SIGNING_KEY",
    )


async def _get_async_redis() -> aioredis.Redis:
    global _aredis, _aredis_loop

    if _aredis is not None and _aredis_loop is None:
        return _aredis

    current_loop = asyncio.get_running_loop()
    if _aredis is not None and _aredis_loop is current_loop:
        return _aredis

    if _aredis is not None:
        try:
            await _aredis.aclose()
        except Exception:
            pass

    _aredis = aioredis.Redis.from_url(_redis_url)
    _aredis_loop = current_loop
    return _aredis


async def get_collection_version(collection_name: str) -> int:
    redis_client = await _get_async_redis()
    value = await redis_client.get(_version_key_for_collection(collection_name))
    return int(value) if value is not None else 0


def bump_collection_version(collection_name: str) -> int:
    return int(_redis.incr(_version_key_for_collection(collection_name)))


async def bump_collection_version_async(collection_name: str) -> int:
    redis_client = await _get_async_redis()
    return int(await redis_client.incr(_version_key_for_collection(collection_name)))


async def set_value(key: str, value: bytes, expire_in_s: Optional[int] = None) -> None:
    redis_client = await _get_async_redis()
    signed_value = _sign_value(value)
    if expire_in_s is not None:
        await redis_client.setex(key, expire_in_s, signed_value)
    else:
        await redis_client.set(key, signed_value)


async def get_value(key: str) -> Optional[bytes]:
    redis_client = await _get_async_redis()
    raw = await redis_client.get(key)
    if raw is None:
        return None
    try:
        return _load_value(raw)
    except SignedPayloadError:
        await redis_client.delete(key)
        return None
