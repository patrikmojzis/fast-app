import pytest
from bson import ObjectId
from quart import Quart

import fast_app.core.middlewares.model_binding_middleware as model_binding_middleware
from fast_app import Model, Route
from fast_app.utils.routing_utils import register_routes


class Chat(Model):
    title: str


@pytest.fixture(autouse=True)
def clear_binding_plan_cache():
    model_binding_middleware._get_binding_plan.cache_clear()
    yield
    model_binding_middleware._get_binding_plan.cache_clear()


@pytest.mark.asyncio
async def test_binding_plan_cache_does_not_grow_for_reregistered_routes(monkeypatch: pytest.MonkeyPatch):
    chat_id = str(ObjectId())

    async def fake_find_by_id_or_fail(value: str):
        return Chat(_id=ObjectId(value), title="bound")

    async def handler(chat: Chat):
        return chat.title

    monkeypatch.setattr(Chat, "find_by_id_or_fail", fake_find_by_id_or_fail)

    for idx in range(5):
        app = Quart(f"binding_cache_app_{idx}")
        register_routes(app, [Route.get("/chats/<chat_id>", handler)])
        view = next(view for name, view in app.view_functions.items() if name != "static")

        async with app.test_request_context(f"/chats/{chat_id}", method="GET"):
            response = await view(chat_id=chat_id)
            assert await response.get_json() == "bound"

    info = model_binding_middleware._get_binding_plan.cache_info()
    assert info.currsize == 1
    assert info.hits == 4
    assert info.misses == 1
