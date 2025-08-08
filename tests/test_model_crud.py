import os
import pytest

from fast_app import Model
from fast_app.database.mongo import clear, get_db


class Product(Model):
    name: str


@pytest.mark.asyncio
async def test_model_create_and_find():
    os.environ["MONGO_URI"] = "mongodb://localhost:27017"
    os.environ["TEST_ENV"] = "1"
    os.environ["TEST_DB_NAME"] = "fast_app_model_test"

    await clear()
    db = await get_db()
    await db.drop_collection("product")

    created = await Product.create({"name": "abc"})
    assert created.name == "abc"

    found = await Product.find_one({"_id": created._id})
    assert found and found.name == "abc"
