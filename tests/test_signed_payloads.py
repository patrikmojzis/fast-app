import pytest

from fast_app.utils import signed_payloads


def test_signed_payloads_reuse_cached_derived_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    signed_payloads._derive_hmac_key.cache_clear()

    raw = signed_payloads.dumps_signed_bytes(b"payload", purpose="cache-test")

    assert signed_payloads.loads_signed_bytes(raw, purpose="cache-test") == b"payload"

    info = signed_payloads._derive_hmac_key.cache_info()
    assert info.misses == 1
    assert info.hits == 1


def test_signed_payloads_do_not_cache_resolved_env_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECRET_KEY", "first-secret")
    signed_payloads._derive_hmac_key.cache_clear()

    first = signed_payloads.dumps_signed_bytes(b"payload", purpose="cache-test")

    monkeypatch.setenv("SECRET_KEY", "second-secret")
    second = signed_payloads.dumps_signed_bytes(b"payload", purpose="cache-test")

    assert first != second
