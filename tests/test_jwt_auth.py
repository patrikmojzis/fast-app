import os
from datetime import datetime, timezone
from typing import Any

import pytest
import jwt

from fast_app import (
    create_access_token,
    create_refresh_token,
    decode_token,
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_LIFETIME,
)
from fast_app.core.jwt_auth import REFRESH_TOKEN_TYPE
from fast_app.exceptions.auth_exceptions import (
    InvalidTokenTypeException,
)


@pytest.fixture(autouse=True)
def _secret_key_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")


def test_access_token_roundtrip():
    token = create_access_token("user123", "auth456")
    payload = decode_token(token, token_type=ACCESS_TOKEN_TYPE)
    assert payload["sub"] == "user123"
    assert payload["sid"] == "auth456"
    assert payload["token_type"] == ACCESS_TOKEN_TYPE


def test_refresh_token_roundtrip():
    token = create_refresh_token("user123")
    payload = decode_token(token, token_type=REFRESH_TOKEN_TYPE)
    assert payload["sub"] == "user123"
    assert payload["jti"]
    assert payload["token_type"] == REFRESH_TOKEN_TYPE


def test_refresh_token_rejected_when_access_expected():
    token = create_refresh_token("user123")
    with pytest.raises(InvalidTokenTypeException):
        decode_token(token, token_type=ACCESS_TOKEN_TYPE)


def test_refresh_token_is_unique_even_same_second(monkeypatch: pytest.MonkeyPatch):
    fixed_now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr("fast_app.core.jwt_auth.now", lambda: fixed_now)

    first = create_refresh_token("user123")
    second = create_refresh_token("user123")

    assert first != second
    first_payload = jwt.decode(
        first,
        "test-secret-key",
        algorithms=["HS256"],
        options={"verify_exp": False, "verify_iat": False},
    )
    second_payload = jwt.decode(
        second,
        "test-secret-key",
        algorithms=["HS256"],
        options={"verify_exp": False, "verify_iat": False},
    )
    assert first_payload["jti"] != second_payload["jti"]


def test_auth_resource_mapping_returns_correct_tokens():
    # Import the template AuthResource to validate mapping
    from fast_app.templates.project_structure.app.http_files.resources.auth_resource import (
        AuthResource,
    )

    class DummyAuth:
        refresh_token: str = "dummy-refresh-token"

        def create_access_token(self) -> str:
            return "dummy-access-token"

    res = AuthResource(DummyAuth())
    data: dict[str, Any] = pytest.run(async_fn=res.to_dict, auth=DummyAuth()) if False else None  # type: ignore
    # Call the coroutine directly using pytest's event loop
    # Using pytest.mark.asyncio for the coroutine call instead


@pytest.mark.asyncio
async def test_auth_resource_mapping_async():
    from fast_app.templates.project_structure.app.http_files.resources.auth_resource import (
        AuthResource,
    )

    class DummyAuth:
        refresh_token: str = "dummy-refresh-token"

        def create_access_token(self) -> str:
            return "dummy-access-token"

    data = await AuthResource(DummyAuth()).to_dict(DummyAuth())
    assert data["token_type"] == "bearer"
    assert data["access_token"] == "dummy-access-token"
    assert data["refresh_token"] == "dummy-refresh-token"
