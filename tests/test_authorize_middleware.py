import pytest
from quart import Quart, jsonify, g

from fast_app import Route
from fast_app.core.middlewares import AuthorizeMiddleware
from fast_app.utils.routing_utils import register_routes
from fast_app.exceptions.http_exceptions import ForbiddenException


@pytest.mark.asyncio
async def test_authorize_middleware_callable_allows():
    app = Quart(__name__)

    # Put a user with authorize(can-callable) in g before handler runs
    @app.before_request
    async def inject_user():
        class DummyUser:
            async def authorize(self, target, ability=None):
                # target is a callable that returns True
                if callable(target):
                    assert ability is None
                    allowed = await target(self)
                    if not allowed:
                        raise ForbiddenException()
                else:
                    raise AssertionError("Unexpected target type")

        g.user = DummyUser()

    async def handler():
        return jsonify({"ok": True})

    async def allow(u):
        return True

    routes = [Route.get('/ok', handler, middlewares=[AuthorizeMiddleware(allow)])]
    register_routes(app, routes)
    client = app.test_client()

    resp = await client.get('/ok')
    assert resp.status_code == 200
    data = await resp.get_json()
    assert data == {"ok": True}


@pytest.mark.asyncio
async def test_authorize_middleware_callable_denies():
    app = Quart(__name__)

    @app.before_request
    async def inject_user():
        class DummyUser:
            async def authorize(self, target, ability=None):
                if callable(target):
                    allowed = await target(self)
                    if not allowed:
                        raise ForbiddenException()

        g.user = DummyUser()

    async def handler():
        return jsonify({"ok": True})

    async def deny(u):
        return False

    routes = [Route.get('/deny', handler, middlewares=[AuthorizeMiddleware(deny)])]
    register_routes(app, routes)
    client = app.test_client()

    resp = await client.get('/deny')
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_authorize_middleware_class_ability_invokes_authorize():
    app = Quart(__name__)

    class Post:
        pass

    calls = {"authorized": False, "ability": None}

    @app.before_request
    async def inject_user():
        class DummyUser:
            async def authorize(self, target, ability=None):
                assert target is Post
                calls["authorized"] = True
                calls["ability"] = ability

        g.user = DummyUser()

    async def handler():
        return jsonify({"ok": True})

    routes = [Route.get('/class', handler, middlewares=[AuthorizeMiddleware(Post, "create")])]
    register_routes(app, routes)
    client = app.test_client()

    resp = await client.get('/class')
    assert resp.status_code == 200
    assert calls["authorized"] is True
    assert calls["ability"] == "create"


@pytest.mark.asyncio
async def test_authorize_middleware_unauthenticated():
    app = Quart(__name__)

    async def handler():
        return jsonify({"ok": True})

    async def allow(u):
        return True

    routes = [Route.get('/auth', handler, middlewares=[AuthorizeMiddleware(allow)])]
    register_routes(app, routes)
    client = app.test_client()

    # No g.user provided by before_request -> should be 401
    resp = await client.get('/auth')
    assert resp.status_code == 401


