from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from functools import lru_cache
from typing import Any

from fast_app.exceptions.common_exceptions import EnvMissingException


class SignedPayloadError(ValueError):
    """Raised when a signed payload is malformed or fails verification."""


def _resolve_secret(env_var: str | None = None) -> str:
    if env_var:
        secret = os.getenv(env_var)
        if secret:
            return secret

    secret = os.getenv("SECRET_KEY")
    if secret:
        return secret

    raise EnvMissingException("SECRET_KEY")


@lru_cache(maxsize=128)
def _derive_hmac_key(purpose: str, secret: str) -> bytes:
    return hashlib.sha256(f"{purpose}:{secret}".encode("utf-8")).digest()


def _sign(payload: bytes, *, purpose: str, env_var: str | None = None) -> str:
    secret = _resolve_secret(env_var)
    key = _derive_hmac_key(purpose, secret)
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def dumps_signed_bytes(
    payload: bytes,
    *,
    purpose: str,
    env_var: str | None = None,
) -> bytes:
    envelope = {
        "v": 1,
        "purpose": purpose,
        "payload_b64": base64.b64encode(payload).decode("ascii"),
        "sig": _sign(payload, purpose=purpose, env_var=env_var),
    }
    return json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode("utf-8")


def loads_signed_bytes(
    raw: bytes,
    *,
    purpose: str,
    env_var: str | None = None,
) -> bytes:
    try:
        envelope: dict[str, Any] = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SignedPayloadError("Signed payload is not valid JSON") from exc

    if envelope.get("v") != 1:
        raise SignedPayloadError("Signed payload version is invalid")
    if envelope.get("purpose") != purpose:
        raise SignedPayloadError("Signed payload purpose mismatch")

    payload_b64 = envelope.get("payload_b64")
    signature = envelope.get("sig")
    if not isinstance(payload_b64, str) or not isinstance(signature, str):
        raise SignedPayloadError("Signed payload is missing required fields")

    try:
        payload = base64.b64decode(payload_b64.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as exc:
        raise SignedPayloadError("Signed payload body is invalid") from exc

    expected = _sign(payload, purpose=purpose, env_var=env_var)
    if not hmac.compare_digest(signature, expected):
        raise SignedPayloadError("Signed payload verification failed")

    return payload
