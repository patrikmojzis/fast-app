from __future__ import annotations

from collections import namedtuple
from functools import wraps
from inspect import unwrap
from threading import Lock
from typing import Callable, Generic, TypeVar
from weakref import WeakKeyDictionary

T = TypeVar("T")
_CacheInfo = namedtuple("CacheInfo", "hits misses maxsize currsize")
_CACHE_MISS = object()


class WeakCallableResultCache(Generic[T]):
    """Cache derived metadata for callables without extending their lifetime.

    The cache keys are weak references, so entries disappear when the underlying
    callable is no longer referenced elsewhere. By default keys are normalized
    with `inspect.unwrap()` so middleware wrappers share cache entries with the
    original handler they wrap.
    """

    def __init__(
        self,
        loader: Callable[[Callable[..., object]], T],
        *,
        unwrap_callables: bool = True,
    ) -> None:
        self._loader = loader
        self._unwrap_callables = unwrap_callables
        self._cache: WeakKeyDictionary[Callable[..., object], T] = WeakKeyDictionary()
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    def resolve(self, target: Callable[..., object]) -> T:
        try:
            cache_key = unwrap(target) if self._unwrap_callables else target
            with self._lock:
                cached = self._cache.get(cache_key, _CACHE_MISS)
                if cached is not _CACHE_MISS:
                    self._hits += 1
                    return cached
                self._misses += 1
        except TypeError:
            return self._loader(target)

        value = self._loader(cache_key)
        with self._lock:
            self._cache[cache_key] = value
        return value

    def cache_clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def cache_info(self) -> _CacheInfo:
        with self._lock:
            return _CacheInfo(self._hits, self._misses, None, len(self._cache))


def weak_callable_cache(*, unwrap_callables: bool = True):
    """Decorator that attaches weak callable-based caching to metadata loaders."""

    def decorator(
        loader: Callable[[Callable[..., object]], T],
    ) -> Callable[[Callable[..., object]], T]:
        cache = WeakCallableResultCache(loader, unwrap_callables=unwrap_callables)

        @wraps(loader)
        def cached(target: Callable[..., object]) -> T:
            return cache.resolve(target)

        cached.cache_clear = cache.cache_clear  # type: ignore[attr-defined]
        cached.cache_info = cache.cache_info  # type: ignore[attr-defined]
        return cached

    return decorator


__all__ = ["WeakCallableResultCache", "weak_callable_cache"]
