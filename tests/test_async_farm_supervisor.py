from __future__ import annotations

from typing import Any

import pytest

from fast_app.integrations.async_farm import supervisor as supervisor_module
from fast_app.integrations.async_farm.supervisor import AsyncFarmSupervisor


class _DummyProcess:
    def __init__(self, pid: int, *, alive: bool) -> None:
        self.pid = pid
        self._alive = alive
        self.terminate_calls = 0
        self.kill_calls = 0

    def is_alive(self) -> bool:
        return self._alive

    def terminate(self) -> None:
        self.terminate_calls += 1
        self._alive = False

    def kill(self) -> None:
        self.kill_calls += 1
        self._alive = False


def _worker_state(process: _DummyProcess) -> dict[str, Any]:
    return {
        "process": process,
        "active_tasks": 0,
        "task_success_count": 0,
        "task_failure_count": 0,
        "start_timestamp": 0.0,
        "last_heartbeat_timestamp": 0.0,
    }


def test_get_alive_processes_prunes_stale_worker_snapshots() -> None:
    supervisor = AsyncFarmSupervisor(verbose=False)
    process = _DummyProcess(1, alive=False)
    supervisor.workers["worker-1"] = _worker_state(process)
    supervisor.tasks_snapshots["worker-1"] = [{"logs": "stale"}]
    supervisor.muted_heartbeats = ["worker-1"]

    assert supervisor.get_alive_processes() == []
    assert "worker-1" not in supervisor.workers
    assert "worker-1" not in supervisor.tasks_snapshots
    assert supervisor.muted_heartbeats == []


@pytest.mark.asyncio
async def test_terminate_worker_prunes_snapshots(monkeypatch: pytest.MonkeyPatch) -> None:
    supervisor = AsyncFarmSupervisor(verbose=False)
    process = _DummyProcess(2, alive=True)
    supervisor.workers["worker-2"] = _worker_state(process)
    supervisor.pending_processes = [process]
    supervisor.tasks_snapshots["worker-2"] = [{"logs": "stale"}]
    supervisor.muted_heartbeats = ["worker-2"]

    async def fake_await_processes_death(processes, timeout) -> None:
        return None

    monkeypatch.setattr(supervisor_module, "await_processes_death", fake_await_processes_death)

    await supervisor.terminate_worker("worker-2")

    assert process.terminate_calls == 1
    assert process.kill_calls == 0
    assert "worker-2" not in supervisor.workers
    assert "worker-2" not in supervisor.tasks_snapshots
    assert supervisor.pending_processes == []
    assert supervisor.muted_heartbeats == []
