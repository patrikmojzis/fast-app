import pytest
from fast_validation import Schema, ValidatorRule, ValidationRuleException
from quart import Quart, jsonify, g

from fast_app import Middleware, Route
from fast_app.utils.routing_utils import register_routes


class RequiresAuthContextRule(ValidatorRule):
    async def validate(self, *, value, data, loc) -> None:
        if not g.get("auth_ready"):
            raise ValidationRuleException("[Scope] User not set. Authenticate user.", loc=tuple(loc))


class PayloadSchema(Schema):
    lead_id: str

    class Meta:
        rules = [
            Schema.Rule("$.lead_id", [RequiresAuthContextRule()]),
        ]


class PreValidationAuthMiddleware(Middleware):
    phase = "pre_validation"

    async def handle(self, next_handler, *args, **kwargs):
        g.auth_ready = True
        return await next_handler(*args, **kwargs)


class DefaultPhaseAuthMiddleware(Middleware):
    async def handle(self, next_handler, *args, **kwargs):
        g.auth_ready = True
        return await next_handler(*args, **kwargs)


async def create(data: PayloadSchema):
    return jsonify({"lead_id": data.lead_id})


@pytest.mark.asyncio
async def test_pre_validation_middleware_runs_before_schema_validation():
    app = Quart(__name__)
    register_routes(app, [Route.post("/items", create, middlewares=[PreValidationAuthMiddleware])])
    client = app.test_client()

    resp = await client.post("/items", json={"lead_id": "x"})
    assert resp.status_code == 200
    body = await resp.get_json()
    assert body["lead_id"] == "x"


@pytest.mark.asyncio
async def test_default_phase_middleware_runs_after_schema_validation():
    app = Quart(__name__)
    register_routes(app, [Route.post("/items", create, middlewares=[DefaultPhaseAuthMiddleware])])
    client = app.test_client()

    resp = await client.post("/items", json={"lead_id": "x"})
    assert resp.status_code == 422
    body = await resp.get_json()
    assert body["error_type"] == "invalid_request"
    assert "[Scope] User not set. Authenticate user." in body["data"][0]["msg"]
