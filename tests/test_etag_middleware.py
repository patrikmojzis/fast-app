import pytest
from quart import Quart, jsonify

from fast_app import Route
from fast_app.core.middlewares.etag_middleware import EtagMiddleware
from fast_app.utils.routing_utils import register_routes


async def data():
    return jsonify({"a": 1})


@pytest.mark.asyncio
async def test_etag_middleware_sets_and_respects_header():
    app = Quart(__name__)
    routes = [Route.get('/data', data, middlewares=[EtagMiddleware])]
    register_routes(app, routes)
    client = app.test_client()

    resp = await client.get('/data')
    assert resp.status_code == 200
    etag = resp.headers.get('ETag')
    assert etag

    # Second request with ETag should return 304
    resp2 = await client.get('/data', headers={'If-None-Match': etag})
    assert resp2.status_code == 304
