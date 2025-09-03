import asyncio
import functools
import hashlib
import pickle
from typing import Any, Callable, Optional

from fast_app.utils.database_cache import DatabaseCache


def cached(expire_in_s: Optional[int] = 5) -> Callable:
    """
    Decorator for caching the result of a method using the Cache class.
    It builds a cache key based on the method's module, qualified name, and its parameters.

    :param expire_in_s: Optional expiration time in seconds for the cache entry.
    :return: Decorated function that checks the cache before executing.
    """
    def decorator(func: Callable) -> Callable:  
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            key = _make_cache_key(func, args, kwargs)
            cached_result = DatabaseCache.get(key)
            if cached_result is not None:
                # print(f"Cache hit for {key}")
                return cached_result
            result = await func(*args, **kwargs)
            DatabaseCache.set(key, result, expire_in_s)
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            key = _make_cache_key(func, args, kwargs)
            cached_result = DatabaseCache.get(key)
            if cached_result is not None:
                # print(f"Cache hit for {key}")
                return cached_result
            result = func(*args, **kwargs)
            DatabaseCache.set(key, result, expire_in_s)
            return result

        # Choose the async or sync wrapper based on whether the original function 
        # is a coroutine function.
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator

def _make_cache_key(func: Callable, args: tuple, kwargs: dict) -> str:
    """
    Generates a cache key based on the function's module, qualified name, and its arguments.
    
    :param func: The function being decorated.
    :param args: Positional arguments passed to the function.
    :param kwargs: Keyword arguments passed to the function.
    :return: A string representing the cache key.
    """
    key_data = (func.__module__, func.__qualname__, args, kwargs)
    serialized = pickle.dumps(key_data)
    hash_digest = hashlib.sha256(serialized).hexdigest()
    return f"cache:{hash_digest}"