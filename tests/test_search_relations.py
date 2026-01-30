import os
from typing import Optional

import pytest
from bson import ObjectId

from fast_app import Model
from fast_app.database.mongo import clear, get_db


class Lead(Model):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class Order(Model):
    lead_id: Optional[ObjectId] = None
    title: Optional[str] = None

    search_fields = ["title"]
    search_relations = [
        {"field": "lead_id", "model": "Lead", "search_fields": ["name", "email", "phone"]}
    ]


@pytest.mark.asyncio
async def test_search_relations_finds_orders_by_related_lead():
    os.environ["MONGO_URI"] = "mongodb://localhost:27017"
    os.environ["TEST_ENV"] = "1"
    os.environ["TEST_DB_NAME"] = "fast_app_search_relations_test"

    await clear()
    db = await get_db()
    await db.drop_collection("lead")
    await db.drop_collection("order")

    lead_alice = await Lead.create({"name": "Alice", "email": "alice@example.com", "phone": "123"})
    lead_bob = await Lead.create({"name": "Bob", "email": "bob@example.com"})

    await Order.create({"lead_id": lead_alice._id, "title": "Alpha"})
    await Order.create({"lead_id": lead_bob._id, "title": "Beta"})

    result = await Order.search("Alice", limit=10, skip=0)

    assert result["meta"]["total"] == 1
    assert len(result["data"]) == 1
    assert result["data"][0].lead_id == lead_alice._id
