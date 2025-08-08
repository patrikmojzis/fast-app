import pytest
from quart import Quart

from fast_app import get_client_ip


@pytest.mark.asyncio
async def test_get_client_ip_from_header():
    app = Quart(__name__)

    @app.route('/ip')
    async def ip_route():
        return get_client_ip()

    client = app.test_client()
    headers = {"X-Forwarded-For": "1.2.3.4"}
    resp = await client.get('/ip', headers=headers)
    assert await resp.get_data(as_text=True) == "1.2.3.4"


@pytest.mark.asyncio
async def test_get_client_ip_default_remote_addr():
    app = Quart(__name__)

    @app.route('/ip')
    async def ip_route():
        return get_client_ip()

    client = app.test_client()
    resp = await client.get('/ip')
    assert await resp.get_data(as_text=True) in {"127.0.0.1", "<local>"}
