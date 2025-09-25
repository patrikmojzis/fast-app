import asyncio
import logging
import pickle
from typing import Any, Dict

import pytest
@pytest.fixture(autouse=True)
def _configure_logging() -> None:
    root = logging.getLogger()
    prev = root.level
    root.setLevel(logging.DEBUG)
    try:
        yield
    finally:
        root.setLevel(prev)



# Top-level test callables to allow import via dotted path
def sync_capture_func(name: str) -> str:
    print(f"sync-print-{name}")
    logging.info(f"sync-log-info-{name}")
    logging.warning(f"sync-log-warn-{name}")
    return f"ok-{name}"


async def async_capture_func(name: str) -> str:
    print(f"async-print-{name}")
    logging.info(f"async-log-info-{name}")
    await asyncio.sleep(0)
    logging.error(f"async-log-error-{name}")
    return f"ok-{name}"


class _FakeIncomingMessage:
    def __init__(self, body: bytes, headers: Dict[str, Any] | None = None) -> None:
        self.body = body
        self.headers = headers or {}
        self._acked = False

    async def ack(self) -> None:  # aio_pika compatibility
        self._acked = True

    # Compatibility: Task may access delivery_tag for task_id
    @property
    def delivery_tag(self) -> int:
        return id(self)


def _payload_for(func_path: str, *, args: tuple[Any, ...] = (), kwargs: Dict[str, Any] | None = None) -> bytes:
    payload = {
        "func_path": func_path,
    }
    if args:
        payload["args_pickled"] = pickle.dumps(args)
    if kwargs:
        payload["kwargs_pickled"] = pickle.dumps(kwargs)
    return pickle.dumps(payload)


@pytest.mark.asyncio
async def test_task_captures_print_and_logs_sync() -> None:
    from fast_app.integrations.async_farm.task import Task

    body = _payload_for("tests.test_async_farm_task_capture.sync_capture_func", args=("A",))
    msg = _FakeIncomingMessage(body)
    task = Task(msg)

    await task.run()

    # Wait until ack processed by done callback
    for _ in range(100):
        if msg._acked:
            break
        await asyncio.sleep(0.01)

    captured = task.get_captured_text()
    assert "sync-print-A" in captured
    assert "sync-log-info-A" in captured
    assert "sync-log-warn-A" in captured
    assert msg._acked is True


@pytest.mark.asyncio
async def test_task_captures_print_and_logs_async() -> None:
    from fast_app.integrations.async_farm.task import Task

    body = _payload_for("tests.test_async_farm_task_capture.async_capture_func", args=("B",))
    msg = _FakeIncomingMessage(body)
    task = Task(msg)

    await task.run()

    for _ in range(100):
        if msg._acked:
            break
        await asyncio.sleep(0.01)

    captured = task.get_captured_text()
    assert "async-print-B" in captured
    assert "async-log-info-B" in captured
    assert "async-log-error-B" in captured
    assert msg._acked is True


@pytest.mark.asyncio
async def test_concurrent_tasks_isolated_capture() -> None:
    from fast_app.integrations.async_farm.task import Task

    body1 = _payload_for("tests.test_async_farm_task_capture.sync_capture_func", args=("X",))
    body2 = _payload_for("tests.test_async_farm_task_capture.async_capture_func", args=("Y",))

    msg1 = _FakeIncomingMessage(body1)
    msg2 = _FakeIncomingMessage(body2)

    task1 = Task(msg1)
    task2 = Task(msg2)

    await asyncio.gather(task1.run(), task2.run())

    # Wait both acks
    for _ in range(200):
        if msg1._acked and msg2._acked:
            break
        await asyncio.sleep(0.01)

    cap1 = task1.get_captured_text()
    cap2 = task2.get_captured_text()

    # Each task must contain its own prints/logs
    assert "sync-print-X" in cap1
    assert "sync-print-X" not in cap2

    assert "async-print-Y" in cap2
    assert "async-print-Y" not in cap1

    # Mixed log levels should be present for respective tasks
    assert "sync-log-info-X" in cap1 and "sync-log-warn-X" in cap1
    assert "async-log-info-Y" in cap2 and "async-log-error-Y" in cap2

    assert msg1._acked is True and msg2._acked is True


