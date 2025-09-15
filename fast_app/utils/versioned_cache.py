import os
from typing import Optional

import redis

from fast_app.config import REDIS_DATABASE_CACHE_DB


_redis = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=REDIS_DATABASE_CACHE_DB,
)


def _version_key_for_collection(collection_name: str) -> str:
    return f"db:ver:{collection_name}"


def get_collection_version(collection_name: str) -> int:
    value = _redis.get(_version_key_for_collection(collection_name))
    return int(value) if value is not None else 0


def bump_collection_version(collection_name: str) -> int:
    return int(_redis.incr(_version_key_for_collection(collection_name)))


def set_value(key: str, value: bytes, expire_in_s: Optional[int] = None) -> None:
    if expire_in_s is not None:
        _redis.setex(key, expire_in_s, value)
    else:
        _redis.set(key, value)


def get_value(key: str) -> Optional[bytes]:
    return _redis.get(key)


