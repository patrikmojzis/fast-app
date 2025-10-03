import pytest
from quart import Quart, jsonify, g

from fast_app import Route
from fast_app.core.middlewares import AuthorizeMiddleware
from fast_app.utils.routing_utils import register_routes


@pytest.mark.asyncio
async def test_authorize_middleware_class_ability_invokes_authorize():
    app = Quart(__name__)

    class Post:
        pass

    calls = {"authorized": False, "ability": None}

    @app.before_request
    async def inject_user():
        class DummyUser:
            async def authorize(self, ability, target):
                assert ability == "create"
                assert target is Post
                calls["authorized"] = True
                calls["ability"] = ability

        g.user = DummyUser()

    async def handler():
        return jsonify({"ok": True})

    routes = [Route.get('/class', handler, middlewares=[AuthorizeMiddleware("create", Post)])]
    register_routes(app, routes)
    client = app.test_client()

    resp = await client.get('/class')
    assert resp.status_code == 200
    assert calls["authorized"] is True
    assert calls["ability"] == "create"



