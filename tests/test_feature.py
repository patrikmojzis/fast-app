import os
import pytest
from quart import Quart, jsonify, g
from fast_validation import Schema

from fast_app import Route, Middleware, Model, validate_request
from fast_app.utils.routing_utils import register_routes
# database helpers
from fast_app.database.mongo import clear, get_db
from bson import ObjectId


class Item(Model):
    name: str


class ItemSchema(Schema):
    name: str


class CustomMiddleware(Middleware):
    async def handle(self, next_handler, *args, **kwargs):
        g.custom_ran = True
        return await next_handler(*args, **kwargs)


async def create_item():
    await validate_request(ItemSchema)
    item = await Item.create(g.validated)
    return jsonify({"id": str(item._id), "name": item.name, "mw": g.custom_ran})


async def ping():
    return "pong"


@pytest.mark.asyncio
async def test_routing_middleware_model_flow():
    os.environ["MONGO_URI"] = "mongodb://localhost:27017"
    os.environ["TEST_ENV"] = "1"
    os.environ["TEST_DB_NAME"] = "fast_app_feature_test"

    await clear()
    db = await get_db()
    await db.drop_collection("item")

    app = Quart(__name__)

    routes = [
        Route.get("/ping", ping),
        Route.group(
            "/api",
            [Route.post("/items", create_item, middlewares=[CustomMiddleware])],
        ),
    ]
    register_routes(app, routes)

    client = app.test_client()

    resp = await client.get("/ping")
    assert await resp.get_data(as_text=True) == "pong"

    resp = await client.post("/api/items", json={})
    assert resp.status_code == 422
    data = await resp.get_json()
    assert data["error_type"] == "invalid_request"

    resp = await client.post("/api/items", json={"name": "test"})
    assert resp.status_code == 200
    data = await resp.get_json()
    assert data["name"] == "test"
    assert data["mw"] is True

    saved = await db["item"].find_one({"_id": ObjectId(data["id"])})
    assert saved and saved["name"] == "test"
