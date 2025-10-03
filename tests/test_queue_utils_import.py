import asyncio
from typing import Any

import pytest

from fast_app.utils.queue_utils import import_from_path


class _C:
    def __init__(self) -> None:
        self.called = False

    def f(self, x: int) -> int:
        self.called = True
        return x + 1


class _A:
    async def g(self, y: int) -> int:
        await asyncio.sleep(0)
        return y * 2


def test_import_function():
    fn = import_from_path("tests.test_queue_utils_import._C")
    assert isinstance(fn, type)


def test_import_class_method_auto_bind_sync():
    fn = import_from_path("tests.test_queue_utils_import._C.f")
    assert callable(fn)
    assert fn(41) == 42


@pytest.mark.asyncio
async def test_import_class_method_auto_bind_async():
    fn = import_from_path("tests.test_queue_utils_import._A.g")
    assert callable(fn)
    assert await fn(21) == 42


