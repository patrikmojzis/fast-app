import pytest
from quart import Quart, jsonify, g

from fast_app import Route
from fast_validation import Schema
from fast_app.core.validation_rules.exists_validator_rule import ExistsValidatorRule
from fast_app.core.api import validate_query
from fast_app.utils.routing_utils import register_routes


class MockModel:
    @classmethod
    async def exists(cls, query: dict) -> bool:
        # Pretend only ObjectId("6563e5a79999999999999999") exists
        from bson import ObjectId
        val = list(query.values())[0]
        return isinstance(val, ObjectId) and str(val) == "6563e5a79999999999999999"


class QueryWithRules(Schema):
    ref_id: str | None = None

    class Meta:
        rules = [
            Schema.Rule("$.ref_id", [ExistsValidatorRule(model=MockModel, is_object_id=True, allow_null=True)])
        ]


async def read_items():
    params = await validate_query(QueryWithRules)
    return jsonify(params)


@pytest.mark.asyncio
async def test_validate_query_rules():
    app = Quart(__name__)
    routes = [Route.get('/items', read_items)]
    register_routes(app, routes)
    client = app.test_client()

    # Missing is allowed (allow_null)
    resp = await client.get('/items')
    assert resp.status_code == 200

    # Invalid ObjectId rejected
    resp = await client.get('/items?ref_id=bad')
    assert resp.status_code == 422

    # Non-existing ObjectId rejected
    resp = await client.get('/items?ref_id=6563e5a70000000000000000')
    assert resp.status_code == 422

    # Existing OK
    resp = await client.get('/items?ref_id=6563e5a79999999999999999')
    assert resp.status_code == 200


