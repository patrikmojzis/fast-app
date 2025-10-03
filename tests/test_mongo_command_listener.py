import os
import pytest

from fast_app.database.mongo import clear, get_db
from fast_app.utils.versioned_cache import get_collection_version


@pytest.mark.asyncio
async def test_command_listener_bumps_version_on_insert():
    os.environ["MONGO_URI"] = "mongodb://localhost:27017"
    os.environ["TEST_ENV"] = "1"
    os.environ["TEST_DB_NAME"] = "fast_app_listener_test"

    await clear()
    db = await get_db()

    collection = "listener_test_items"

    # Ensure clean collection
    await db.drop_collection(collection)

    before = get_collection_version(collection)

    # Perform a raw insert using Motor to trigger CommandListener
    await db[collection].insert_one({"a": 1})

    after = get_collection_version(collection)

    assert after == before + 1


