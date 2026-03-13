import pytest
from bson import ObjectId
from quart import Quart, g, jsonify

from fast_app import Middleware, Model, Route
from fast_app.application import Application
from fast_app.core.middlewares import AuthorizeMiddleware, BelongsToMiddleware
from fast_app.exceptions import UnauthorizedException
from fast_app.utils.routing_utils import register_routes


@pytest.fixture(autouse=True)
def reset_application_state():
    app = Application()
    app.reset()
    try:
        yield
    finally:
        app.reset()


class RejectAnonymousMiddleware(Middleware):
    phase = "pre_binding"

    async def handle(self, next_handler, *args, **kwargs):
        raise UnauthorizedException()


class Post(Model):
    title: str


class Account(Model):
    name: str


class Membership(Model):
    account_id: ObjectId


async def show_post(post: Post):
    return jsonify({"id": str(post.id)})


async def show_membership(account: Account, membership: Membership):
    return jsonify({"account_id": str(account.id), "membership_id": str(membership.id)})


@pytest.mark.asyncio
async def test_pre_binding_middleware_runs_before_model_binding(monkeypatch):
    calls: list[str] = []

    async def fake_find_by_id_or_fail(cls, _id):
        calls.append(str(_id))
        return cls(_id=ObjectId(_id), title="bound")

    monkeypatch.setattr(Post, "find_by_id_or_fail", classmethod(fake_find_by_id_or_fail))

    app = Quart(__name__)
    register_routes(app, [Route.get("/posts/<post_id>", show_post, middlewares=[RejectAnonymousMiddleware])])
    client = app.test_client()

    invalid_id_response = await client.get("/posts/1")
    assert invalid_id_response.status_code == 401

    valid_shape_response = await client.get("/posts/000000000000000000000000")
    assert valid_shape_response.status_code == 401

    assert calls == []


@pytest.mark.asyncio
async def test_instance_target_authorize_middleware_still_receives_bound_model(monkeypatch):
    post_id = ObjectId()
    calls: dict[str, object] = {}

    async def fake_find_by_id_or_fail(cls, _id):
        return cls(_id=ObjectId(_id), title="bound")

    monkeypatch.setattr(Post, "find_by_id_or_fail", classmethod(fake_find_by_id_or_fail))

    app = Quart(__name__)

    @app.before_request
    async def inject_user():
        class DummyUser:
            async def authorize(self, ability, target):
                calls["ability"] = ability
                calls["target"] = target

        g.user = DummyUser()

    register_routes(
        app,
        [Route.get("/posts/<post_id>", show_post, middlewares=[AuthorizeMiddleware("update", "post")])],
    )
    client = app.test_client()

    response = await client.get(f"/posts/{post_id}")
    assert response.status_code == 200
    assert calls["ability"] == "update"
    assert isinstance(calls["target"], Post)
    assert calls["target"].id == post_id


@pytest.mark.asyncio
async def test_belongs_to_middleware_still_receives_bound_models(monkeypatch):
    account_id = ObjectId()
    membership_id = ObjectId()

    async def fake_account_find_by_id_or_fail(cls, _id):
        return cls(_id=ObjectId(_id), name="Acme")

    async def fake_membership_find_by_id_or_fail(cls, _id):
        return cls(_id=ObjectId(_id), account_id=account_id)

    monkeypatch.setattr(Account, "find_by_id_or_fail", classmethod(fake_account_find_by_id_or_fail))
    monkeypatch.setattr(Membership, "find_by_id_or_fail", classmethod(fake_membership_find_by_id_or_fail))

    app = Quart(__name__)
    register_routes(
        app,
        [
            Route.get(
                "/accounts/<account_id>/memberships/<membership_id>",
                show_membership,
                middlewares=[BelongsToMiddleware("membership", "account")],
            )
        ],
    )
    client = app.test_client()

    response = await client.get(f"/accounts/{account_id}/memberships/{membership_id}")
    assert response.status_code == 200
    body = await response.get_json()
    assert body == {"account_id": str(account_id), "membership_id": str(membership_id)}
