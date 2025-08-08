import os
import pickle
from typing import Optional

import redis

from fast_app.config import REDIS_DATABASE_CACHE_DB

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=REDIS_DATABASE_CACHE_DB
)

class DatabaseCache:
    @classmethod
    def set(cls, key: str, value: any, expire_in_s: Optional[int] = None):
        """
        Set a value in the cache.
        :param key: The cache key.
        :param value: The value to store.
        :param expire_in_m: Expiration time in minutes (optional).
        """
        serialized_value = pickle.dumps(value)
        if expire_in_s is not None:
            r.setex(key, expire_in_s, serialized_value)
        else:
            r.set(key, serialized_value)

    @classmethod
    def get(cls, key: str, default=None):
        """
        Get a value from the cache.
        :param key: The cache key.
        :param default: Default value if key doesn't exist.
        :return: The cached value or default.
        """
        value = r.get(key)
        if value is None:
            return default
        return pickle.loads(value)

    @classmethod
    def flush(cls):
        """
        Flush the entire cache.
        """
        r.flushdb()
