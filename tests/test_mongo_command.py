from __future__ import annotations

import argparse
import asyncio

import pytest

from fast_app.cli import mongo_command
from fast_app.cli.mongo_command import MongoCommand


class _DummyClient:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _stats_args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "action": "stats",
        "seconds": 5.0,
        "limit": 10,
        "sort": "read-time",
        "database": None,
        "namespace": [],
        "exclude_namespace": [],
        "all_databases": False,
        "include_system": False,
        "json": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _profile_args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "action": "profile",
        "dangerously_enable_profiler": True,
        "seconds": 15.0,
        "slowms": 25,
        "sample_rate": 1.0,
        "capture_all": False,
        "include_writes": False,
        "namespace": [],
        "exclude_namespace": [],
        "only_collection_scans": False,
        "only_suggestions": False,
        "limit": 5,
        "max_profile_docs": 2000,
        "min_count": 1,
        "min_total_millis": 0,
        "min_docs_examined": 0,
        "min_scan_ratio": 0.0,
        "sort": "total-millis",
        "database": None,
        "json": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_mongo_stats_runs_without_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    command = MongoCommand()
    client = _DummyClient()
    called: dict[str, object] = {}

    async def fake_stats(args: argparse.Namespace, current_client: object, database: str) -> None:
        called["action"] = args.action
        called["client"] = current_client
        called["database"] = database

    monkeypatch.setattr(mongo_command, "configure_env_from_app_config", lambda: None)
    monkeypatch.setattr(command, "_build_client", lambda: client)
    monkeypatch.setattr(command, "_default_database_name", lambda: "fastapp")
    monkeypatch.setattr(command, "_stats", fake_stats)

    command.execute(_stats_args())

    assert called == {
        "action": "stats",
        "client": client,
        "database": "fastapp",
    }
    assert client.closed is True


def test_mongo_profile_requires_danger_flag(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command = MongoCommand()
    client = _DummyClient()

    monkeypatch.setattr(mongo_command, "configure_env_from_app_config", lambda: None)
    monkeypatch.setattr(command, "_build_client", lambda: client)
    monkeypatch.setattr(command, "_default_database_name", lambda: "fastapp")

    with pytest.raises(SystemExit) as exc:
        command.execute(_profile_args(dangerously_enable_profiler=False))

    assert exc.value.code == 2
    assert "--dangerously-enable-profiler" in capsys.readouterr().out
    assert client.closed is True


def test_mongo_profile_runs_with_danger_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    command = MongoCommand()
    client = _DummyClient()
    called: dict[str, object] = {}

    async def fake_profile(args: argparse.Namespace, current_client: object, database: str) -> None:
        called["action"] = args.action
        called["client"] = current_client
        called["database"] = database

    monkeypatch.setattr(mongo_command, "configure_env_from_app_config", lambda: None)
    monkeypatch.setattr(command, "_build_client", lambda: client)
    monkeypatch.setattr(command, "_default_database_name", lambda: "fastapp")
    monkeypatch.setattr(command, "_profile", fake_profile)

    command.execute(_profile_args())

    assert called == {
        "action": "profile",
        "client": client,
        "database": "fastapp",
    }
    assert client.closed is True


def test_mongo_profile_rejects_invalid_sample_rate(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command = MongoCommand()

    monkeypatch.setattr(mongo_command, "configure_env_from_app_config", lambda: None)

    with pytest.raises(SystemExit) as exc:
        command.execute(_profile_args(sample_rate=1.5))

    assert exc.value.code == 2
    assert "--sample-rate must be between 0.0 and 1.0" in capsys.readouterr().out


def test_mongo_profile_rejects_invalid_max_profile_docs(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command = MongoCommand()

    monkeypatch.setattr(mongo_command, "configure_env_from_app_config", lambda: None)

    with pytest.raises(SystemExit) as exc:
        command.execute(_profile_args(max_profile_docs=0))

    assert exc.value.code == 2
    assert "--max-profile-docs must be greater than 0" in capsys.readouterr().out


def test_mongo_profile_rejects_invalid_min_count(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command = MongoCommand()

    monkeypatch.setattr(mongo_command, "configure_env_from_app_config", lambda: None)

    with pytest.raises(SystemExit) as exc:
        command.execute(_profile_args(min_count=0))

    assert exc.value.code == 2
    assert "--min-count must be greater than 0" in capsys.readouterr().out


def test_mongo_profile_emits_ready_status_to_stderr(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command = MongoCommand()

    async def fake_capture_profile_report(*args: object, status_callback=None, **kwargs: object) -> object:
        assert status_callback is not None
        status_callback("Mongo profiler enabled for `fastapp`.")
        return object()

    monkeypatch.setattr(mongo_command, "capture_profile_report", fake_capture_profile_report)
    monkeypatch.setattr(command, "_print_profile_report", lambda report, json_output=False: None)

    asyncio.run(command._profile(_profile_args(), {"fastapp": object()}, "fastapp"))

    assert "Mongo profiler enabled for `fastapp`." in capsys.readouterr().err


def test_mongo_stats_emits_ready_status_to_stderr(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command = MongoCommand()

    async def fake_sample_activity(*args: object, status_callback=None, **kwargs: object) -> object:
        assert status_callback is not None
        status_callback("Mongo activity sampling started for `fastapp`.")
        return object()

    monkeypatch.setattr(mongo_command, "sample_activity", fake_sample_activity)
    monkeypatch.setattr(command, "_print_activity_report", lambda report, json_output=False: None)

    asyncio.run(command._stats(_stats_args(), object(), "fastapp"))

    assert "Mongo activity sampling started for `fastapp`." in capsys.readouterr().err
