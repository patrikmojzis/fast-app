import pytest
from quart import Quart, jsonify, g
from pydantic import BaseModel

from fast_app import Route, validate_request
from fast_app.core import Schema
from fast_app.core.validation_rules.exists_validator_rule import ExistsValidatorRule
from fast_app.utils.routing_utils import register_routes


class MockModel:
    @classmethod
    async def exists(cls, query: dict) -> bool:
        # Pretend only ObjectId("6563e5a79999999999999999") exists
        from bson import ObjectId
        val = list(query.values())[0]
        return isinstance(val, ObjectId) and str(val) == "6563e5a79999999999999999"


class CreateSchema(Schema):
    ref_id: str

    class Meta:
        rules = [
            Schema.Rule("$.ref_id", [ExistsValidatorRule(model=MockModel, is_object_id=True)])
        ]


async def create_item():
    await validate_request(CreateSchema)
    return jsonify(g.validated)


@pytest.mark.asyncio
async def test_rule_validation_invalid_and_valid():
    app = Quart(__name__)
    routes = [Route.post('/items', create_item)]
    register_routes(app, routes)
    client = app.test_client()

    # Invalid ObjectId
    resp = await client.post('/items', json={"ref_id": "not_an_object_id"})
    assert resp.status_code == 422
    data = await resp.get_json()
    assert data['error_type'] == 'invalid_request'

    # Non-existing ObjectId
    resp = await client.post('/items', json={"ref_id": "6563e5a70000000000000000"})
    assert resp.status_code == 422

    # Existing ObjectId passes
    resp = await client.post('/items', json={"ref_id": "6563e5a79999999999999999"})
    assert resp.status_code == 200
    data = await resp.get_json()
    assert data['ref_id'] == "6563e5a79999999999999999"


