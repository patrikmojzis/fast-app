from __future__ import annotations

import asyncio
from contextvars import ContextVar
from typing import Any, Dict, List, Optional, Set, Tuple, Type, TYPE_CHECKING

from bson import ObjectId

if TYPE_CHECKING:
    from fast_app.contracts.model import Model

_batch_cache_var: ContextVar[Optional[Dict[Tuple[type, str], '_KeyedBatchLoader']]] = ContextVar(
    "model_batch_cache", default=None
)


class _KeyedBatchLoader:
    """Request-scoped batch cache for a single (Model, key_field) pair.

    Accumulates lookups within the same event-loop tick and dispatches
    them as one ``Model.find({key: {$in: [...]}})`` query.  Results are
    cached for the remainder of the request.

    Concurrency model:

    ``_in_flight`` maps each pending/fetching key to a shared Future.
    All callers for the same key — whether they arrive before dispatch,
    during the fetch, or between batches — share that single Future.

    ``_dirty`` tracks keys invalidated by ``prime()`` / ``clear_key()``
    / ``clear_all()`` while a fetch is in progress.  When
    ``_execute_batch`` finishes, dirty keys are not cached and their
    futures are resolved with the primed value (if available) or the
    fetch result (valid at query time) without caching.
    """

    __slots__ = ("_model_cls", "_key_field", "_cache", "_pending",
                 "_scheduled", "_in_flight", "_dirty")

    def __init__(self, model_cls: Type[Model], key_field: str) -> None:
        self._model_cls = model_cls
        self._key_field = key_field
        self._cache: Dict[Any, Optional[Model]] = {}
        self._pending: Dict[Any, List[asyncio.Future]] = {}
        self._scheduled: bool = False
        self._in_flight: Dict[Any, asyncio.Future] = {}
        self._dirty: Set[Any] = set()

    def _normalize_key(self, key: Any) -> Any:
        if self._key_field == "_id" and isinstance(key, str) and ObjectId.is_valid(key):
            return ObjectId(key)
        return key

    async def load(self, key: Any) -> Optional[Model]:
        normalized = self._normalize_key(key)

        if normalized in self._cache:
            return self._cache[normalized]

        if normalized in self._in_flight:
            return await asyncio.shield(self._in_flight[normalized])

        loop = asyncio.get_running_loop()
        future: asyncio.Future[Optional[Model]] = loop.create_future()
        self._in_flight[normalized] = future
        self._pending.setdefault(normalized, []).append(future)

        if not self._scheduled:
            self._scheduled = True
            loop.call_soon(self._schedule_dispatch, loop)

        return await asyncio.shield(future)

    def _schedule_dispatch(self, loop: asyncio.AbstractEventLoop) -> None:
        batch = self._pending
        self._pending = {}
        self._scheduled = False

        if batch:
            loop.create_task(self._execute_batch(batch))

    async def _execute_batch(self, batch: Dict[Any, List[asyncio.Future]]) -> None:
        keys = list(batch.keys())

        try:
            results = await self._model_cls.find({self._key_field: {"$in": keys}})

            result_map: Dict[Any, Model] = {}
            for model in results:
                key_value = getattr(model, self._key_field, None)
                if key_value is not None and key_value not in result_map:
                    result_map[key_value] = model

            for key in keys:
                fetched = result_map.get(key)

                if key in self._dirty:
                    # prime() or clear was called during the fetch.
                    # Use primed value from _cache if available,
                    # otherwise give the waiter the fetch result
                    # (valid at query time) without caching it.
                    self._dirty.discard(key)
                    self._in_flight.pop(key, None)
                    value = self._cache.get(key, fetched)
                    for fut in batch[key]:
                        if not fut.done():
                            fut.set_result(value)
                else:
                    self._cache[key] = fetched
                    self._in_flight.pop(key, None)
                    for fut in batch[key]:
                        if not fut.done():
                            fut.set_result(fetched)

        except Exception as exc:
            for key in batch:
                self._in_flight.pop(key, None)
                if key in self._dirty:
                    # prime() or clear was called during the fetch.
                    # Use primed value if available; otherwise propagate.
                    self._dirty.discard(key)
                    value = self._cache.get(key)
                    for fut in batch[key]:
                        if not fut.done():
                            if value is not None:
                                fut.set_result(value)
                            else:
                                fut.set_exception(exc)
                else:
                    for fut in batch[key]:
                        if not fut.done():
                            fut.set_exception(exc)

    def prime(self, key: Any, value: Optional[Model]) -> None:
        normalized = self._normalize_key(key)
        self._cache[normalized] = value
        if normalized in self._in_flight:
            self._dirty.add(normalized)

    def clear_key(self, key: Any) -> None:
        normalized = self._normalize_key(key)
        self._cache.pop(normalized, None)
        if normalized in self._in_flight:
            self._dirty.add(normalized)

    def clear_all(self) -> None:
        self._cache.clear()
        self._dirty.update(self._in_flight.keys())


class ModelBatchCache:
    """Request-scoped batch cache for Model lookups.

    Batches concurrent ``find_by_id`` / ``belongs_to`` / ``has_one``
    calls into single ``$in`` queries via ``Model.find()``.  Results
    are cached for the remainder of the request.

    **Important:** Call ``ensure_active()`` in the parent context (before
    ``asyncio.gather``) so that child tasks inherit the shared store.
    ``Resource.dump()`` and the built-in middleware do this automatically.
    """

    @staticmethod
    def ensure_active() -> None:
        """Ensure the batch cache store exists in the current context.

        Must be called from the parent context **before** spawning child
        tasks (e.g. via ``asyncio.gather``).  Child tasks then inherit
        the same store reference and share loaders.

        **Lifecycle:** Inside HTTP requests the built-in middleware calls
        ``ensure_active()`` on entry and ``reset()`` on exit.  Outside
        HTTP (CLI, background jobs, tests) the caller owns the lifecycle
        — call ``reset()`` when the logical scope ends to avoid stale
        cache hits across independent operations.
        """
        if _batch_cache_var.get(None) is None:
            _batch_cache_var.set({})

    @staticmethod
    def _get_store() -> Dict[Tuple[type, str], _KeyedBatchLoader]:
        store = _batch_cache_var.get(None)
        if store is None:
            store = {}
            _batch_cache_var.set(store)
        return store

    @staticmethod
    def _get_loader(model_cls: Type[Model], key_field: str = "_id") -> _KeyedBatchLoader:
        store = ModelBatchCache._get_store()
        cache_key = (model_cls, key_field)
        if cache_key not in store:
            store[cache_key] = _KeyedBatchLoader(model_cls, key_field)
        return store[cache_key]

    @staticmethod
    async def load(model_cls: Type[Model], key: Any, key_field: str = "_id") -> Optional[Model]:
        """Load a model instance, batching with concurrent callers."""
        if key is None:
            return None
        loader = ModelBatchCache._get_loader(model_cls, key_field)
        return await loader.load(key)

    @staticmethod
    def prime(model_cls: Type[Model], key: Any, value: Optional[Model], key_field: str = "_id") -> None:
        """Pre-populate the cache (e.g. after create / update)."""
        if key is None:
            return
        loader = ModelBatchCache._get_loader(model_cls, key_field)
        loader.prime(key, value)

    @staticmethod
    def clear(model_cls: Optional[Type[Model]] = None, key: Any = None, key_field: str = "_id") -> None:
        """Clear cached entries.

        - ``clear()``                — clear everything
        - ``clear(User)``            — clear all User loaders
        - ``clear(User, some_id)``   — clear one entry
        """
        store = _batch_cache_var.get(None)
        if store is None:
            return

        if model_cls is None:
            for loader in store.values():
                loader.clear_all()
            return

        if key is not None:
            cache_key = (model_cls, key_field)
            loader = store.get(cache_key)
            if loader is not None:
                loader.clear_key(key)
            return

        for k in store:
            if k[0] is model_cls:
                store[k].clear_all()

    @staticmethod
    def reset() -> None:
        """Fully reset the batch cache for the current context."""
        _batch_cache_var.set(None)
