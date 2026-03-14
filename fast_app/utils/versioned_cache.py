import os
from typing import Optional

import redis

from fast_app.utils.signed_payloads import SignedPayloadError, dumps_signed_bytes, loads_signed_bytes


_redis = redis.Redis.from_url(os.getenv("REDIS_DATABASE_CACHE_URL", "redis://localhost:6379/13"))


def _version_key_for_collection(collection_name: str) -> str:
    return f"db:ver:{collection_name}"


def get_collection_version(collection_name: str) -> int:
    value = _redis.get(_version_key_for_collection(collection_name))
    return int(value) if value is not None else 0


def bump_collection_version(collection_name: str) -> int:
    return int(_redis.incr(_version_key_for_collection(collection_name)))


def set_value(key: str, value: bytes, expire_in_s: Optional[int] = None) -> None:
    signed_value = dumps_signed_bytes(
        value,
        purpose="db_cache",
        env_var="DB_CACHE_SIGNING_KEY",
    )
    if expire_in_s is not None:
        _redis.setex(key, expire_in_s, signed_value)
    else:
        _redis.set(key, signed_value)


def get_value(key: str) -> Optional[bytes]:
    raw = _redis.get(key)
    if raw is None:
        return None
    try:
        return loads_signed_bytes(
            raw,
            purpose="db_cache",
            env_var="DB_CACHE_SIGNING_KEY",
        )
    except SignedPayloadError:
        _redis.delete(key)
        return None

