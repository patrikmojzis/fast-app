import os
import pytest

from fast_app import Model
from fast_app.database.mongo import clear, get_db


class CachedItem(Model):
    name: str


@pytest.mark.asyncio
async def test_find_returns_updated_data_within_cache_window():
    # Use real Mongo and ensure a clean DB/collection
    os.environ["MONGO_URI"] = "mongodb://localhost:27017"
    os.environ["TEST_ENV"] = "1"
    os.environ["TEST_DB_NAME"] = "fast_app_cache_invalidation_test"
    os.environ["DB_CACHE_EXPIRE_IN_S"] = "3"  # within-window behavior

    await clear()
    db = await get_db()
    await db.drop_collection(CachedItem.collection_name())

    # Create initial document
    item = await CachedItem.create({"name": "v1"})

    # Prime the cache by reading once
    found1 = await CachedItem.find_by_id(item._id)
    assert found1 is not None and found1.name == "v1"

    # Update the document (should bump collection version)
    await item.update({"name": "v2"})

    # Immediately read again within cache window
    found2 = await CachedItem.find_by_id(item._id)
    assert found2 is not None
    assert found2.name == "v2", "Expected cache to be invalidated by version bump after update"


@pytest.mark.asyncio
async def test_two_rapid_sequential_updates_are_observed():
    # Use real Mongo and ensure a clean DB/collection
    os.environ["MONGO_URI"] = "mongodb://localhost:27017"
    os.environ["TEST_ENV"] = "1"
    os.environ["TEST_DB_NAME"] = "fast_app_cache_invalidation_test"
    os.environ["DB_CACHE_EXPIRE_IN_S"] = "3"

    await clear()
    db = await get_db()
    await db.drop_collection(CachedItem.collection_name())

    # Create initial document
    item = await CachedItem.create({"name": "v1"})

    # Prime cache with v1
    found1 = await CachedItem.find_by_id(item._id)
    assert found1 and found1.name == "v1"

    # First update -> v2
    await item.update({"name": "v2"})
    await item.update({"name": "v3"})

    # Immediately read again; should see v3
    final = await CachedItem.find_by_id(item._id)
    assert final and final.name == "v3"


