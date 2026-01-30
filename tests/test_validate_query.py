import pytest
from pydantic import BaseModel
from quart import Quart, jsonify

from fast_app import Route, validate_query
from fast_app.utils.routing_utils import register_routes


class QuerySchema(BaseModel):
    page: int = 1
    tags: list[str] = []
    active: bool | None = None


async def read_items():
    params = await validate_query(QuerySchema)
    return jsonify(params.model_dump())


@pytest.mark.asyncio
async def test_validate_query_lists_and_scalars():
    app = Quart(__name__)
    routes = [Route.get('/items', read_items)]
    register_routes(app, routes)
    client = app.test_client()

    # List via repeated keys
    resp = await client.get('/items?tags=a&tags=b')
    assert resp.status_code == 200
    data = await resp.get_json()
    assert data['tags'] == ['a', 'b']

    # List via bracket syntax
    resp = await client.get('/items?tags[]=x&tags[]=y')
    assert resp.status_code == 200
    data = await resp.get_json()
    assert data['tags'] == ['x', 'y']

    # List via CSV
    resp = await client.get('/items?tags=a,b,c')
    assert resp.status_code == 200
    data = await resp.get_json()
    assert data['tags'] == ['a', 'b', 'c']

    # Mixed styles should merge and split
    resp = await client.get('/items?tags=a,b&tags=c&tags[]=d')
    assert resp.status_code == 200
    data = await resp.get_json()
    assert data['tags'] == ['a', 'b', 'c', 'd']

    # Scalar int coercion
    resp = await client.get('/items?page=2')
    assert resp.status_code == 200
    data = await resp.get_json()
    assert data['page'] == 2

    # Repeated scalar keeps first value
    resp = await client.get('/items?page=3&page=4')
    assert resp.status_code == 200
    data = await resp.get_json()
    assert data['page'] == 3

    # Bracket scalar keeps first value
    resp = await client.get('/items?page[]=5&page[]=6')
    assert resp.status_code == 200
    data = await resp.get_json()
    assert data['page'] == 5

    # Boolean coercion: true/false
    resp = await client.get('/items?active=true')
    assert resp.status_code == 200
    data = await resp.get_json()
    assert data['active'] is True

    resp = await client.get('/items?active=false')
    assert resp.status_code == 200
    data = await resp.get_json()
    assert data['active'] is False

    # Boolean coercion: 1 -> True
    resp = await client.get('/items?active=1')
    assert resp.status_code == 200
    data = await resp.get_json()
    assert data['active'] is True


@pytest.mark.asyncio
async def test_validate_query_ignores_unknown_params():
    app = Quart(__name__)
    routes = [Route.get('/items', read_items)]
    register_routes(app, routes)
    client = app.test_client()

    resp = await client.get('/items?tags=a&unknown=1&active=true')
    assert resp.status_code == 200
    data = await resp.get_json()
    assert 'unknown' not in data
    assert data['tags'] == ['a']
    assert data['active'] is True


@pytest.mark.asyncio
async def test_validate_query_invalid_type_raises_422():
    app = Quart(__name__)
    routes = [Route.get('/items', read_items)]
    register_routes(app, routes)
    client = app.test_client()

    resp = await client.get('/items?page=not_an_int')
    assert resp.status_code == 422
    data = await resp.get_json()
    assert data['error_type'] == 'invalid_query'


 
