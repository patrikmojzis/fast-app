import asyncio
import functools
import hashlib
import pickle
import os
from typing import Any, Callable, Optional

from fast_app.utils.versioned_cache import get_collection_version, get_value, set_value


def cached_db_retrieval(namespace: Optional[str] = None) -> Callable:
    """
    Decorator for caching the result of a method using the Cache class.
    It builds a cache key based on the method's module, qualified name, and its parameters.

    :param namespace: Model or collection name to use for the cache key.
    :return: Decorated function that checks the cache before executing.
    """
    expire_in_s = int(os.getenv('DB_CACHE_EXPIRE_IN_S', '3'))
    def decorator(func: Callable) -> Callable:  
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            ns = namespace or _infer_namespace(func, args, kwargs)
            version_prefix = _version_prefix(ns)
            key = _make_cache_key(func, args, kwargs, version_prefix)
            raw = get_value(key)
            if raw is not None:
                return pickle.loads(raw)
            result = await func(*args, **kwargs)
            set_value(key, pickle.dumps(result), expire_in_s)
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            ns = namespace or _infer_namespace(func, args, kwargs)
            version_prefix = _version_prefix(ns)
            key = _make_cache_key(func, args, kwargs, version_prefix)
            raw = get_value(key)
            if raw is not None:
                return pickle.loads(raw)
            result = func(*args, **kwargs)
            set_value(key, pickle.dumps(result), expire_in_s)
            return result

        # Choose the async or sync wrapper based on whether the original function 
        # is a coroutine function.
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator

def _make_cache_key(func: Callable, args: tuple, kwargs: dict, version_prefix: str) -> str:
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
    return f"cache:{version_prefix}:{hash_digest}"


def _version_prefix(namespace: Optional[str]) -> str:
    if not namespace:
        return "v0"
    try:
        version = get_collection_version(namespace)
    except Exception:
        version = 0
    return f"v{version}"


def _infer_namespace(func: Callable, args: tuple, kwargs: dict) -> Optional[str]:
    # If first arg is a Model class or instance, derive namespace from collection_name()
    if not args:
        return None

    first = args[0]

    # Case 1: classmethod call on a Model subclass
    if isinstance(first, type) and callable(getattr(first, 'collection_name', None)):
        try:
            return first.collection_name()  # type: ignore[attr-defined]
        except Exception:
            return None

    # Case 2: instance method call on a Model instance
    model_cls = getattr(first, '__class__', None)
    if model_cls and callable(getattr(model_cls, 'collection_name', None)):
        try:
            return model_cls.collection_name()  # type: ignore[attr-defined]
        except Exception:
            return None

    return None