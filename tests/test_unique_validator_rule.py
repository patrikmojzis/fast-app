import pytest
from bson import ObjectId
from fast_validation import Schema
from quart import Quart, jsonify, g

from fast_app import Route, Model, validate_request
from fast_app.core.validation_rules.unique_validator_rule import UniqueValidatorRule
from fast_app.utils.routing_utils import register_routes


class _MockUniqueModel:
    records = [
        {"_id": ObjectId("6563e5a79999999999999991"), "variable_symbol": "111"},
        {"_id": ObjectId("6563e5a79999999999999992"), "variable_symbol": "222"},
    ]

    @classmethod
    async def exists(cls, query: dict) -> bool:
        for record in cls.records:
            if _record_matches_query(record, query):
                return True
        return False


class TelegramChat(Model):
    telegram_chat_id: str

    @classmethod
    async def exists(cls, query: dict) -> bool:
        for record in [
            {"_id": ObjectId("6563e5a79999999999999993"), "telegram_chat_id": "chat-1"},
        ]:
            if _record_matches_query(record, query):
                return True
        return False


def _record_matches_query(record: dict, query: dict) -> bool:
    for key, expected in query.items():
        actual = record.get(key)
        if isinstance(expected, dict) and "$ne" in expected:
            if actual == expected["$ne"]:
                return False
            continue
        if actual != expected:
            return False
    return True


class CreateSchema(Schema):
    variable_symbol: str

    class Meta:
        rules = [
            Schema.Rule("$.variable_symbol", [UniqueValidatorRule(model=_MockUniqueModel)]),
        ]


class InferSchema(Schema):
    telegram_chat_id: str

    class Meta:
        rules = [
            Schema.Rule("$.telegram_chat_id", [UniqueValidatorRule()]),
        ]


class PatchSchema(Schema):
    variable_symbol: str | None = None

    class Meta:
        rules = [
            Schema.Rule("$.variable_symbol", [UniqueValidatorRule(model=_MockUniqueModel)]),
        ]


async def create_item():
    await validate_request(CreateSchema)
    return jsonify(g.validated)


async def create_item_infer():
    await validate_request(InferSchema)
    return jsonify(g.validated)


async def patch_item(item_id: str):
    await validate_request(PatchSchema, partial=True)
    return jsonify({"item_id": item_id, "data": g.validated})


@pytest.mark.asyncio
async def test_unique_rule_for_post():
    app = Quart(__name__)
    routes = [Route.post("/items", create_item)]
    register_routes(app, routes)
    client = app.test_client()

    resp = await client.post("/items", json={"variable_symbol": "111"})
    assert resp.status_code == 422

    resp = await client.post("/items", json={"variable_symbol": "333"})
    assert resp.status_code == 200
    data = await resp.get_json()
    assert data["variable_symbol"] == "333"


@pytest.mark.asyncio
async def test_unique_rule_model_inference():
    app = Quart(__name__)
    routes = [Route.post("/telegram", create_item_infer)]
    register_routes(app, routes)
    client = app.test_client()

    resp = await client.post("/telegram", json={"telegram_chat_id": "chat-1"})
    assert resp.status_code == 422

    resp = await client.post("/telegram", json={"telegram_chat_id": "chat-2"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_unique_rule_patch_excludes_current_record():
    app = Quart(__name__)
    routes = [Route.patch("/items/<item_id>", patch_item)]
    register_routes(app, routes)
    client = app.test_client()

    current_id = "6563e5a79999999999999991"

    # Same value as current record should pass on PATCH.
    resp = await client.patch(f"/items/{current_id}", json={"variable_symbol": "111"})
    assert resp.status_code == 200
    body = await resp.get_json()
    assert body["data"] == {"variable_symbol": "111"}

    # Value owned by another record should fail.
    resp = await client.patch(f"/items/{current_id}", json={"variable_symbol": "222"})
    assert resp.status_code == 422

    # Missing field should be ignored in partial validation.
    resp = await client.patch(f"/items/{current_id}", json={})
    assert resp.status_code == 200
    body = await resp.get_json()
    assert body["data"] == {}
