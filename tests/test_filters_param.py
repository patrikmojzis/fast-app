import pytest
from quart import Quart, jsonify

from fast_app import Route, get_mongo_filter_from_query
from fast_app.utils.routing_utils import register_routes


@pytest.mark.asyncio
async def test_get_mongo_filter_from_query_json_and_base64():
    app = Quart(__name__)

    async def handler():
        # allow only these fields and ops for the test
        filt = get_mongo_filter_from_query(
            allowed_fields=["tier", "score", "rep_id", "rating_last_updated", "user"],
            allowed_ops=[
                "$and", "$or", "$eq", "$gte", "$lte", "$in"
            ],
        )
        return jsonify(filt)

    routes = [Route.get('/q', handler)]
    register_routes(app, routes)
    client = app.test_client()

    # Plain JSON
    resp = await client.get('/q?filter={"tier":{"$in":["gold","silver"]},"score":{"$gte":10,"$lte":100}}')
    assert resp.status_code == 200
    data = await resp.get_json()
    assert data == {"tier": {"$in": ["gold", "silver"]}, "score": {"$gte": 10, "$lte": 100}}

    # Base64 URL-safe JSON
    # {"rep_id":{"$eq":"123"}}
    b64 = "eyJyZXBfaWQiOnsiJGVxIjoiMTIzIn19"
    resp = await client.get(f'/q?filter={b64}')
    assert resp.status_code == 200
    data = await resp.get_json()
    assert data == {"rep_id": {"$eq": "123"}}

    # Disallowed operator
    resp = await client.get('/q?filter={"score":{"$where":"return true;"}}')
    assert resp.status_code == 422
    data = await resp.get_json()
    assert data['error_type'] == 'invalid_query'


