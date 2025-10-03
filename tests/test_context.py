from __future__ import annotations

import warnings

import pytest

from fast_app.core.context import context, define_key


def test_string_keys_basic_set_get_clear() -> None:
    context.set("request_id", "r1")
    assert context.get("request_id") == "r1"

    context.clear("request_id")
    assert context.get("request_id") is None


def test_typed_keys_set_get_defaults() -> None:
    UserId = define_key[int]("user_id")
    assert context.get(UserId) is None
    context.set(UserId, 7)
    v = context.get(UserId)
    assert isinstance(v, (int, type(None))) and v == 7


def test_picklability_warning_once_and_snapshot_omits() -> None:
    Tmp = define_key("tmp_unpicklable")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        context.set(Tmp, lambda: None)  # warns once (lambda is not picklable)
        context.set(Tmp, lambda: None)  # no second warning for same key
        warned = [x for x in w if issubclass(x.category, RuntimeWarning)]
        assert len(warned) >= 1

    snap = context.snapshot()
    assert "tmp_unpicklable" not in snap


def test_require_picklable_enforced() -> None:
    Strict = define_key("strict_key", require_picklable=True)
    with pytest.raises(TypeError):
        context.set(Strict, lambda: None)


def test_snapshot_and_install_roundtrip() -> None:
    A = define_key[str]("A")
    B = define_key[int]("B")
    context.set(A, "x")
    context.set(B, 10)

    snap = context.snapshot()
    assert snap["A"] == "x"
    assert snap["B"] == 10

    # Simulate new process by clearing then installing
    context.clear("A", "B")
    assert context.get(A) is None
    assert context.get(B) is None
    context.install(snap)
    assert context.get(A) == "x"
    assert context.get(B) == 10


