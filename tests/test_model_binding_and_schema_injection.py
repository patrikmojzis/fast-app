import os
import pytest
from quart import Quart, jsonify

from fast_app import Route, Model, Schema
from fast_app.utils.routing_utils import register_routes
from fast_app.database.mongo import clear, get_db


class Chat(Model):
    title: str


class ChatRequestSchema(Schema):
    message: str | None = None
    count: int | None = None


async def message_with_post_model(chat: Chat, data: ChatRequestSchema):
    # Return bound model id and validated data fields
    return jsonify({
        "chat_id": str(chat.id),
        "data": data.model_dump()
    })

async def message_with_patch_model(chat: Chat, data: ChatRequestSchema):
    # Return bound model id and validated data fields
    return jsonify({
        "chat_id": str(chat.id),
        "data": data.model_dump(exclude_unset=True)
    })


async def message_with_id_only(chat_id: str):
    # Should not trigger model binding if only str expected
    return jsonify({"chat_id": chat_id})


@pytest.mark.asyncio
async def test_model_binding_and_schema_injection():
    os.environ["MONGO_URI"] = "mongodb://localhost:27017"
    os.environ["TEST_ENV"] = "1"
    os.environ["TEST_DB_NAME"] = "fast_app_model_binding_test"

    await clear()
    db = await get_db()
    await db.drop_collection("chat")

    # Seed a chat
    chat = await Chat.create({"title": "hello"})

    app = Quart(__name__)
    routes = [
        Route.post("/chats/<chat_id>/message", message_with_post_model),
        Route.post("/chats/<chat_id>/echo", message_with_id_only),
        Route.patch("/chats/<chat_id>/message", message_with_patch_model),
    ]
    register_routes(app, routes)
    client = app.test_client()

    # POST with full body should validate and inject schema; bind model via chat_id param
    resp = await client.post(f"/chats/{chat.id}/message", json={"message": "hi", "count": 2})
    assert resp.status_code == 200
    data = await resp.get_json()
    assert data["chat_id"] == str(chat.id)
    assert data["data"] == {"message": "hi", "count": 2}

    # POST with id-only handler should not bind or hit DB beyond normal routing
    resp2 = await client.post(f"/chats/{chat.id}/echo", json={})
    assert resp2.status_code == 200
    data2 = await resp2.get_json()
    assert data2["chat_id"] == str(chat.id)

    # PATCH should treat schema as partial and not include unset keys
    resp3 = await client.patch(f"/chats/{chat.id}/message", json={"message": "partial"})
    assert resp3.status_code == 200
    data3 = await resp3.get_json()
    assert data3["chat_id"] == str(chat.id)
    assert data3["data"] == {"message": "partial"}


