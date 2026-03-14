import inspect

import pytest
from pydantic import BaseModel
from quart import Quart

import fast_app.core.middlewares.schema_validation_middleware as schema_middleware


class ExampleSchema(BaseModel):
    value: str


@pytest.fixture(autouse=True)
def clear_schema_handler_cache():
    schema_middleware._resolve_schema_handler.cache_clear()
    yield
    schema_middleware._resolve_schema_handler.cache_clear()


@pytest.mark.asyncio
async def test_handle_caches_non_schema_handler_signature(monkeypatch):
    signature_calls = 0
    original_signature = inspect.signature

    def counting_signature(handler):
        nonlocal signature_calls
        signature_calls += 1
        return original_signature(handler)

    async def unexpected_validate(*args, **kwargs):  # pragma: no cover
        raise AssertionError("validation should not run for non-schema handlers")

    async def handler(chat_id: str):
        return chat_id

    monkeypatch.setattr(schema_middleware, "signature", counting_signature)
    monkeypatch.setattr(schema_middleware, "validate_query", unexpected_validate)
    monkeypatch.setattr(schema_middleware, "validate_request", unexpected_validate)

    middleware = schema_middleware.SchemaValidationMiddleware()

    assert await middleware.handle(handler, chat_id="a") == "a"
    assert await middleware.handle(handler, chat_id="b") == "b"
    assert signature_calls == 1


@pytest.mark.asyncio
async def test_handle_caches_schema_handler_signature_for_post(monkeypatch):
    signature_calls = 0
    validate_request_calls = 0
    original_signature = inspect.signature

    def counting_signature(handler):
        nonlocal signature_calls
        signature_calls += 1
        return original_signature(handler)

    async def fake_validate_request(schema_type, *, partial=False):
        nonlocal validate_request_calls
        validate_request_calls += 1
        assert schema_type is ExampleSchema
        assert partial is False
        return ExampleSchema(value="validated")

    async def unexpected_validate_query(*args, **kwargs):  # pragma: no cover
        raise AssertionError("POST should not use validate_query")

    async def handler(data: ExampleSchema):
        return data.value

    monkeypatch.setattr(schema_middleware, "signature", counting_signature)
    monkeypatch.setattr(schema_middleware, "validate_request", fake_validate_request)
    monkeypatch.setattr(schema_middleware, "validate_query", unexpected_validate_query)

    app = Quart(__name__)
    middleware = schema_middleware.SchemaValidationMiddleware()

    async with app.test_request_context("/", method="POST", json={"value": "ignored"}):
        assert await middleware.handle(handler) == "validated"

    async with app.test_request_context("/", method="POST", json={"value": "ignored"}):
        assert await middleware.handle(handler) == "validated"

    assert validate_request_calls == 2
    assert signature_calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "expected_validator", "expected_partial"),
    [
        ("GET", "query", False),
        ("DELETE", "query", False),
        ("POST", "request", False),
        ("PUT", "request", False),
        ("PATCH", "request", True),
    ],
)
async def test_handle_routes_methods_to_expected_validator(
    monkeypatch,
    method: str,
    expected_validator: str,
    expected_partial: bool,
):
    calls: list[tuple[str, bool, type[ExampleSchema]]] = []

    async def fake_validate_request(schema_type, *, partial=False):
        calls.append(("request", partial, schema_type))
        return ExampleSchema(value="request")

    async def fake_validate_query(schema_type, *, partial=False):
        calls.append(("query", partial, schema_type))
        return ExampleSchema(value="query")

    async def handler(data: ExampleSchema):
        return data.value

    monkeypatch.setattr(schema_middleware, "validate_request", fake_validate_request)
    monkeypatch.setattr(schema_middleware, "validate_query", fake_validate_query)

    app = Quart(__name__)
    middleware = schema_middleware.SchemaValidationMiddleware()

    async with app.test_request_context("/", method=method):
        result = await middleware.handle(handler)

    assert calls == [(expected_validator, expected_partial, ExampleSchema)]
    assert result == expected_validator
