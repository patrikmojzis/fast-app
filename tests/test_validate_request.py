import pytest
from quart import Quart, jsonify, g
from pydantic import BaseModel

from fast_app import Route, validate_request
from fast_app.utils.routing_utils import register_routes


class ItemSchema(BaseModel):
    name: str


async def create_item():
    await validate_request(ItemSchema)
    return jsonify(g.validated)


@pytest.mark.asyncio
async def test_validate_request_success_and_failure():
    app = Quart(__name__)
    routes = [Route.post('/items', create_item)]
    register_routes(app, routes)
    client = app.test_client()

    # Missing name should raise 422
    resp = await client.post('/items', json={})
    assert resp.status_code == 422
    data = await resp.get_json()
    assert data['error_type'] == 'invalid_request'

    # Correct payload should return validated data
    resp = await client.post('/items', json={'name': 'test'})
    assert resp.status_code == 200
    assert await resp.get_json() == {'name': 'test'}
