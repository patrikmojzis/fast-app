import asyncio
import inspect
import os
import pickle
from typing import Any, Awaitable, Callable, Optional, Union

import redis.asyncio as redis

from fast_app.config import REDIS_CACHE_DB

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=REDIS_CACHE_DB
)

class Cache:
    @classmethod
    async def set(cls, key: str, value: Any, expire_in_m: Optional[int] = None):
        """
        Set a value in the cache.
        :param key: The cache key.
        :param value: The value to store.
        :param expire_in_m: Expiration time in minutes (optional).
        """
        serialized_value = pickle.dumps(value)
        if expire_in_m is not None:
            await r.setex(key, int(round(expire_in_m * 60)), serialized_value)
        else:
            await r.set(key, serialized_value)

    @classmethod
    async def get(cls, key: str, default=None):
        """
        Get a value from the cache.
        :param key: The cache key.
        :param default: Default value if key doesn't exist.
        :return: The cached value or default.
        """
        value = await r.get(key)
        if value is None:
            return default
        return pickle.loads(value)

    @classmethod
    async def delete(cls, key: str):
        """
        Delete a value from the cache.
        :param key: The cache key to delete.
        """
        await r.delete(key)

    @classmethod
    async def exists(cls, key: str) -> bool:
        """
        Check if a key exists in the cache.
        :param key: The cache key to check.
        :return: True if the key exists, False otherwise.
        """
        return await r.exists(key) > 0

    @classmethod
    async def increment(cls, key: str, amount: int = 1):
        """
        Increment a numeric value in the cache.
        :param key: The cache key.
        :param amount: The amount to increment by.
        :return: The new value.
        """
        return await r.incr(key, amount)

    @classmethod
    async def decrement(cls, key: str, amount: int = 1):
        """
        Decrement a numeric value in the cache.
        :param key: The cache key.
        :param amount: The amount to decrement by.
        :return: The new value.
        """
        return await r.decr(key, amount)

    @classmethod
    async def remember(cls, key: str, callback: Union[Callable[[], Any], Callable[[], Awaitable[Any]]], expire_in_m: Optional[int] = None):
        """
        Get an item from the cache, or store the default value.
        :param key: The cache key.
        :param expire_in_m: Expiration time in minutes.
        :param callback: Function (sync or async) that returns the default value.
        :return: The cached value.
        """
        value = await cls.get(key)
        if value is None:
            if inspect.iscoroutinefunction(callback):
                value = await callback()
            else:
                value = callback()
            await cls.set(key, value, expire_in_m)
        return value

    @classmethod
    async def flush(cls):
        """
        Flush the entire cache.
        """
        await r.flushdb()
