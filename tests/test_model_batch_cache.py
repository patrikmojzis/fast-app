from __future__ import annotations

import asyncio
import contextvars
from typing import Any, ClassVar, Optional

import pytest
from bson import ObjectId

from fast_app.contracts.model import Model
from fast_app.core.model_batch_cache import ModelBatchCache, _batch_cache_var
from fast_app.exceptions.model_exceptions import ModelNotFoundException


# ---------------------------------------------------------------------------
# Mock models
# ---------------------------------------------------------------------------

class Parent(Model):
    _find_calls: ClassVar[list[dict[str, Any]]] = []
    _store: ClassVar[dict[ObjectId, dict[str, Any]]] = {}
    name: Optional[str] = None

    @classmethod
    async def find(cls, query: dict[str, Any], **kwargs) -> list[Parent]:
        cls._find_calls.append(query)
        key_field = next(iter(query))
        in_keys = query[key_field].get("$in", [])
        return [cls(**cls._store[k]) for k in in_keys if k in cls._store]

    @classmethod
    async def query_modifier(cls, query, function_name=None, model_name=None):
        return query

    @classmethod
    def reset_store(cls):
        cls._find_calls = []
        cls._store = {}


class Child(Model):
    parent_id: Optional[ObjectId] = None

    @classmethod
    async def query_modifier(cls, query, function_name=None, model_name=None):
        return query


class OtherParent(Model):
    _find_calls: ClassVar[list[dict[str, Any]]] = []
    _store: ClassVar[dict[ObjectId, dict[str, Any]]] = {}
    name: Optional[str] = None

    @classmethod
    async def find(cls, query: dict[str, Any], **kwargs) -> list[OtherParent]:
        cls._find_calls.append(query)
        key_field = next(iter(query))
        in_keys = query[key_field].get("$in", [])
        return [cls(**cls._store[k]) for k in in_keys if k in cls._store]

    @classmethod
    async def query_modifier(cls, query, function_name=None, model_name=None):
        return query

    @classmethod
    def reset_store(cls):
        cls._find_calls = []
        cls._store = {}


class ChildEntry(Model):
    parent_id: Optional[ObjectId] = None
    _find_calls: ClassVar[list[dict[str, Any]]] = []
    _store: ClassVar[dict[ObjectId, dict[str, Any]]] = {}

    @classmethod
    async def find(cls, query: dict[str, Any], **kwargs) -> list[ChildEntry]:
        cls._find_calls.append(query)
        key_field = next(iter(query))
        in_keys = query[key_field].get("$in", [])
        results = []
        for k in in_keys:
            for doc in cls._store.values():
                if doc.get(key_field) == k:
                    results.append(cls(**doc))
        return results

    @classmethod
    async def query_modifier(cls, query, function_name=None, model_name=None):
        return query

    @classmethod
    def reset_store(cls):
        cls._find_calls = []
        cls._store = {}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset():
    ModelBatchCache.reset()
    Parent.reset_store()
    OtherParent.reset_store()
    ChildEntry.reset_store()
    yield
    ModelBatchCache.reset()


# ---------------------------------------------------------------------------
# Batch + cache tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_single_load_returns_model():
    oid = ObjectId()
    Parent._store[oid] = {"_id": oid, "name": "Alice"}

    result = await ModelBatchCache.load(Parent, oid)

    assert result is not None
    assert result._id == oid
    assert result.name == "Alice"
    assert len(Parent._find_calls) == 1


@pytest.mark.asyncio
async def test_concurrent_loads_batch_into_single_query():
    ids = [ObjectId() for _ in range(5)]
    for oid in ids:
        Parent._store[oid] = {"_id": oid, "name": f"user-{oid}"}

    ModelBatchCache.ensure_active()
    results = await asyncio.gather(*(ModelBatchCache.load(Parent, oid) for oid in ids))

    assert len(results) == 5
    assert all(r is not None for r in results)
    assert len(Parent._find_calls) == 1
    assert set(Parent._find_calls[0]["_id"]["$in"]) == set(ids)


@pytest.mark.asyncio
async def test_cache_hit_avoids_second_query():
    oid = ObjectId()
    Parent._store[oid] = {"_id": oid, "name": "Bob"}

    first = await ModelBatchCache.load(Parent, oid)
    second = await ModelBatchCache.load(Parent, oid)

    assert first is not None
    assert second is first
    assert len(Parent._find_calls) == 1


@pytest.mark.asyncio
async def test_none_cached_for_missing_keys():
    oid = ObjectId()

    first = await ModelBatchCache.load(Parent, oid)
    second = await ModelBatchCache.load(Parent, oid)

    assert first is None
    assert second is None
    assert len(Parent._find_calls) == 1


@pytest.mark.asyncio
async def test_duplicate_keys_in_batch_coalesce():
    oid = ObjectId()
    Parent._store[oid] = {"_id": oid, "name": "Carol"}

    ModelBatchCache.ensure_active()
    results = await asyncio.gather(
        ModelBatchCache.load(Parent, oid),
        ModelBatchCache.load(Parent, oid),
        ModelBatchCache.load(Parent, oid),
    )

    assert all(r is not None and r._id == oid for r in results)
    assert len(Parent._find_calls) == 1
    assert Parent._find_calls[0]["_id"]["$in"] == [oid]


@pytest.mark.asyncio
async def test_load_none_key_returns_none():
    result = await ModelBatchCache.load(Parent, None)
    assert result is None
    assert len(Parent._find_calls) == 0


# ---------------------------------------------------------------------------
# Public API tests
# ---------------------------------------------------------------------------

def test_lazy_init_no_overhead():
    assert _batch_cache_var.get(None) is None


@pytest.mark.asyncio
async def test_reset_clears_all():
    oid = ObjectId()
    Parent._store[oid] = {"_id": oid, "name": "Dan"}

    await ModelBatchCache.load(Parent, oid)
    assert len(Parent._find_calls) == 1

    ModelBatchCache.reset()

    await ModelBatchCache.load(Parent, oid)
    assert len(Parent._find_calls) == 2


@pytest.mark.asyncio
async def test_clear_specific_model():
    oid_p = ObjectId()
    oid_o = ObjectId()
    Parent._store[oid_p] = {"_id": oid_p, "name": "P"}
    OtherParent._store[oid_o] = {"_id": oid_o, "name": "O"}

    await ModelBatchCache.load(Parent, oid_p)
    await ModelBatchCache.load(OtherParent, oid_o)

    ModelBatchCache.clear(Parent)

    await ModelBatchCache.load(Parent, oid_p)
    assert len(Parent._find_calls) == 2

    await ModelBatchCache.load(OtherParent, oid_o)
    assert len(OtherParent._find_calls) == 1


@pytest.mark.asyncio
async def test_clear_specific_key():
    oid1 = ObjectId()
    oid2 = ObjectId()
    Parent._store[oid1] = {"_id": oid1, "name": "A"}
    Parent._store[oid2] = {"_id": oid2, "name": "B"}

    ModelBatchCache.ensure_active()
    await asyncio.gather(
        ModelBatchCache.load(Parent, oid1),
        ModelBatchCache.load(Parent, oid2),
    )
    assert len(Parent._find_calls) == 1

    ModelBatchCache.clear(Parent, oid1)

    await ModelBatchCache.load(Parent, oid1)
    assert len(Parent._find_calls) == 2

    # oid2 still cached
    await ModelBatchCache.load(Parent, oid2)
    assert len(Parent._find_calls) == 2


@pytest.mark.asyncio
async def test_prime_populates_cache():
    oid = ObjectId()
    instance = Parent(_id=oid, name="Primed")
    ModelBatchCache.prime(Parent, oid, instance)

    result = await ModelBatchCache.load(Parent, oid)

    assert result is instance
    assert len(Parent._find_calls) == 0


# ---------------------------------------------------------------------------
# Model integration tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_by_id_uses_batch_cache():
    ids = [ObjectId() for _ in range(3)]
    for oid in ids:
        Parent._store[oid] = {"_id": oid, "name": f"u-{oid}"}

    ModelBatchCache.ensure_active()
    results = await asyncio.gather(*(Parent.find_by_id(oid) for oid in ids))

    assert len(results) == 3
    assert all(r is not None for r in results)
    assert len(Parent._find_calls) == 1


@pytest.mark.asyncio
async def test_belongs_to_batches():
    parent_ids = [ObjectId() for _ in range(3)]
    for pid in parent_ids:
        Parent._store[pid] = {"_id": pid, "name": f"parent-{pid}"}

    children = [Child(parent_id=pid) for pid in parent_ids]

    ModelBatchCache.ensure_active()
    results = await asyncio.gather(*(c.belongs_to(Parent) for c in children))

    assert len(results) == 3
    assert all(r is not None for r in results)
    assert len(Parent._find_calls) == 1


@pytest.mark.asyncio
async def test_has_one_batches():
    parent_ids = [ObjectId() for _ in range(3)]
    for pid in parent_ids:
        child_oid = ObjectId()
        ChildEntry._store[child_oid] = {"_id": child_oid, "parent_id": pid}

    parents = [Parent(_id=pid) for pid in parent_ids]

    ModelBatchCache.ensure_active()
    results = await asyncio.gather(*(p.has_one(ChildEntry, child_key="parent_id") for p in parents))

    assert len(results) == 3
    assert all(r is not None for r in results)
    assert len(ChildEntry._find_calls) == 1


@pytest.mark.asyncio
async def test_find_by_id_or_fail_raises():
    missing_id = ObjectId()

    with pytest.raises(ModelNotFoundException):
        await Parent.find_by_id_or_fail(missing_id)


# ---------------------------------------------------------------------------
# Isolation tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_separate_contexts_isolated():
    oid = ObjectId()
    Parent._store[oid] = {"_id": oid, "name": "isolated"}

    async def run_in_context():
        await ModelBatchCache.load(Parent, oid)

    ctx1 = contextvars.copy_context()
    ctx2 = contextvars.copy_context()

    await asyncio.get_running_loop().run_in_executor(None, lambda: ctx1.run(asyncio.run, run_in_context()))
    await asyncio.get_running_loop().run_in_executor(None, lambda: ctx2.run(asyncio.run, run_in_context()))

    assert len(Parent._find_calls) == 2


@pytest.mark.asyncio
async def test_string_objectid_normalization():
    oid = ObjectId()
    Parent._store[oid] = {"_id": oid, "name": "norm"}

    r1 = await ModelBatchCache.load(Parent, str(oid))
    r2 = await ModelBatchCache.load(Parent, oid)

    assert r1 is not None
    assert r2 is r1
    assert len(Parent._find_calls) == 1


@pytest.mark.asyncio
async def test_ensure_active_enables_cross_task_batching():
    ids = [ObjectId() for _ in range(3)]
    for oid in ids:
        Parent._store[oid] = {"_id": oid, "name": f"x-{oid}"}

    # Without ensure_active — no batching
    ModelBatchCache.reset()
    Parent._find_calls = []
    await asyncio.gather(*(ModelBatchCache.load(Parent, oid) for oid in ids))
    assert len(Parent._find_calls) == 3

    # With ensure_active — batched
    ModelBatchCache.reset()
    Parent._find_calls = []
    ModelBatchCache.ensure_active()
    await asyncio.gather(*(ModelBatchCache.load(Parent, oid) for oid in ids))
    assert len(Parent._find_calls) == 1


# ---------------------------------------------------------------------------
# Prime/clear vs in-flight race tests
# ---------------------------------------------------------------------------

class SlowParent(Model):
    _find_calls: ClassVar[list] = []
    _store: ClassVar[dict[ObjectId, dict[str, Any]]] = {}
    name: Optional[str] = None

    @classmethod
    async def find(cls, query: dict[str, Any], **kwargs) -> list[SlowParent]:
        cls._find_calls.append(query)
        await asyncio.sleep(0.05)
        key_field = next(iter(query))
        in_keys = query[key_field].get("$in", [])
        return [cls(**cls._store[k]) for k in in_keys if k in cls._store]

    @classmethod
    async def query_modifier(cls, query, function_name=None, model_name=None):
        return query

    @classmethod
    def reset_store(cls):
        cls._find_calls = []
        cls._store = {}


@pytest.fixture
def _reset_slow():
    SlowParent.reset_store()
    yield
    SlowParent.reset_store()


@pytest.mark.asyncio
async def test_prime_wins_over_in_flight(_reset_slow):
    """prime() during an in-flight fetch should not be overwritten by the
    stale fetch result."""
    oid = ObjectId()
    SlowParent._store[oid] = {"_id": oid, "name": "stale"}
    fresh = SlowParent(_id=oid, name="fresh")

    ModelBatchCache.ensure_active()
    load_task = asyncio.ensure_future(ModelBatchCache.load(SlowParent, oid))
    await asyncio.sleep(0.01)
    ModelBatchCache.prime(SlowParent, oid, fresh)
    result = await load_task

    # The prime value should win — the stale fetch is discarded
    final = await ModelBatchCache.load(SlowParent, oid)
    assert final is fresh


@pytest.mark.asyncio
async def test_clear_key_wins_over_in_flight(_reset_slow):
    """clear_key() during an in-flight fetch should not let the stale
    fetch result be cached."""
    oid = ObjectId()
    SlowParent._store[oid] = {"_id": oid, "name": "stale"}

    ModelBatchCache.ensure_active()
    load_task = asyncio.ensure_future(ModelBatchCache.load(SlowParent, oid))
    await asyncio.sleep(0.01)
    ModelBatchCache.clear(SlowParent, oid)
    await load_task

    # After clear, the cache should be empty — next load re-fetches
    SlowParent._store[oid] = {"_id": oid, "name": "updated"}
    result = await ModelBatchCache.load(SlowParent, oid)
    assert result.name == "updated"
    assert len(SlowParent._find_calls) == 2


@pytest.mark.asyncio
async def test_clear_all_invalidates_in_flight_batch(_reset_slow):
    """clear(cls) + prime() during an in-flight fetch: the in-flight
    waiter must see the primed value, not the stale fetch result."""
    oid = ObjectId()
    SlowParent._store[oid] = {"_id": oid, "name": "stale"}
    fresh = SlowParent(_id=oid, name="fresh")

    ModelBatchCache.ensure_active()
    load_task = asyncio.ensure_future(ModelBatchCache.load(SlowParent, oid))
    await asyncio.sleep(0.01)
    # Simulate what _update() does: clear(cls) + prime(cls, id, self)
    ModelBatchCache.clear(SlowParent)
    ModelBatchCache.prime(SlowParent, oid, fresh)

    # The in-flight waiter must get the primed value
    result = await load_task
    assert result is fresh

    # Subsequent load also returns the primed value
    final = await ModelBatchCache.load(SlowParent, oid)
    assert final is fresh
    assert len(SlowParent._find_calls) == 1


@pytest.mark.asyncio
async def test_clear_key_does_not_false_miss_in_flight(_reset_slow):
    """clear_key() during an in-flight fetch should NOT give the waiter
    None for a row that exists.  The waiter should get the fetch result
    (valid at query time), but the result should not be cached."""
    oid = ObjectId()
    SlowParent._store[oid] = {"_id": oid, "name": "exists"}

    ModelBatchCache.ensure_active()
    load_task = asyncio.ensure_future(ModelBatchCache.load(SlowParent, oid))
    await asyncio.sleep(0.01)
    ModelBatchCache.clear(SlowParent, oid)
    result = await load_task

    # The waiter should NOT get None — the row exists
    assert result is not None
    assert result.name == "exists"


@pytest.mark.asyncio
async def test_clear_and_prime_before_dispatch_runs(_reset_slow):
    """If clear(cls) + prime() happen BEFORE _schedule_dispatch fires
    (i.e. between load() and call_soon callback), the waiter must still
    see the primed value."""
    oid = ObjectId()
    SlowParent._store[oid] = {"_id": oid, "name": "stale"}
    fresh = SlowParent(_id=oid, name="fresh")

    ModelBatchCache.ensure_active()

    # Start load — key goes to _pending, call_soon is scheduled but
    # hasn't fired yet (we don't yield control).
    load_coro = ModelBatchCache.load(SlowParent, oid)
    load_task = asyncio.ensure_future(load_coro)

    # Invalidate BEFORE the call_soon callback runs.
    ModelBatchCache.clear(SlowParent)
    ModelBatchCache.prime(SlowParent, oid, fresh)

    result = await load_task

    # Waiter must see primed value
    assert result is fresh

    # Subsequent load also returns primed value
    final = await ModelBatchCache.load(SlowParent, oid)
    assert final is fresh


@pytest.mark.asyncio
async def test_staggered_same_key_dedup(_reset_slow):
    """A second caller for the same key arriving after the first batch
    is dispatched but before it finishes should join the in-flight
    future, not start a second fetch."""
    oid = ObjectId()
    SlowParent._store[oid] = {"_id": oid, "name": "dedup"}

    ModelBatchCache.ensure_active()

    async def load_after_delay():
        # Arrive after the first batch is dispatched (call_soon fired)
        # but before the slow find() completes.
        await asyncio.sleep(0.01)
        return await ModelBatchCache.load(SlowParent, oid)

    r1, r2 = await asyncio.gather(
        ModelBatchCache.load(SlowParent, oid),
        load_after_delay(),
    )

    assert r1 is not None
    assert r2 is not None
    assert r1._id == oid
    # Only one find() call — second caller joined the in-flight future
    assert len(SlowParent._find_calls) == 1


# ---------------------------------------------------------------------------
# Error + prime interaction test
# ---------------------------------------------------------------------------

class SlowFailingModel(Model):
    _find_calls: ClassVar[list] = []
    name: Optional[str] = None

    @classmethod
    async def find(cls, query: dict[str, Any], **kwargs) -> list[SlowFailingModel]:
        cls._find_calls.append(query)
        await asyncio.sleep(0.05)
        raise RuntimeError("db boom")

    @classmethod
    async def query_modifier(cls, query, function_name=None, model_name=None):
        return query


@pytest.mark.asyncio
async def test_prime_wins_even_when_batch_errors():
    """If prime() is called while a batch is in flight and that batch
    later raises, the primed value should be returned to the waiter
    instead of the exception."""
    oid = ObjectId()
    fresh = SlowFailingModel(_id=oid, name="fresh")
    SlowFailingModel._find_calls = []

    ModelBatchCache.ensure_active()
    load_task = asyncio.ensure_future(ModelBatchCache.load(SlowFailingModel, oid))
    await asyncio.sleep(0.01)
    ModelBatchCache.prime(SlowFailingModel, oid, fresh)
    result = await load_task

    # Waiter should get the primed value, not RuntimeError
    assert result is fresh


# ---------------------------------------------------------------------------
# Cancellation isolation test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancelling_one_waiter_does_not_cancel_others(_reset_slow):
    """Cancelling one task awaiting a shared in-flight lookup must not
    affect other waiters for the same key."""
    oid = ObjectId()
    SlowParent._store[oid] = {"_id": oid, "name": "shared"}

    ModelBatchCache.ensure_active()

    task1 = asyncio.ensure_future(ModelBatchCache.load(SlowParent, oid))
    task2 = asyncio.ensure_future(ModelBatchCache.load(SlowParent, oid))

    await asyncio.sleep(0.01)
    task1.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task1

    # task2 should still succeed
    result = await task2
    assert result is not None
    assert result.name == "shared"

    # Cache should be populated — subsequent load is a hit
    SlowParent._find_calls.clear()
    cached = await ModelBatchCache.load(SlowParent, oid)
    assert cached is not None
    assert len(SlowParent._find_calls) == 0
