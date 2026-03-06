from __future__ import annotations

import argparse
from typing import Any

import pytest

from fast_app import ASC, Index
from fast_app.cli import indexes_command
from fast_app.cli.indexes_command import IndexesCommand
from fast_app.utils.index_manager import CollectionIndexPlan, IndexApplyResult, IndexSyncPlan


def _make_plan(has_drift: bool) -> IndexSyncPlan:
    if not has_drift:
        return IndexSyncPlan(
            collections=[
                CollectionIndexPlan(
                    collection="order",
                    desired=[],
                    existing=[],
                    missing=[],
                    changed=[],
                    stale=[],
                    unchanged=[],
                )
            ]
        )

    return IndexSyncPlan(
        collections=[
            CollectionIndexPlan(
                collection="order",
                desired=[Index(keys=[("business_id", ASC)], name="order_business")],
                existing=[{"name": "_id_", "key": {"_id": 1}}],
                missing=[Index(keys=[("business_id", ASC)], name="order_business")],
                changed=[],
                stale=[],
                unchanged=[],
            )
        ]
    )


@pytest.mark.asyncio
async def _load_plan_with_drift(_: str | None) -> IndexSyncPlan:
    return _make_plan(True)


@pytest.mark.asyncio
async def _load_plan_without_drift(_: str | None) -> IndexSyncPlan:
    return _make_plan(False)


def test_indexes_check_exits_with_code_2_when_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    command = IndexesCommand()
    monkeypatch.setattr(command, "_load_plan", _load_plan_with_drift)

    args = argparse.Namespace(action="check", path=None, verbose=False)
    with pytest.raises(SystemExit) as exc:
        command.execute(args)

    assert exc.value.code == 2


def test_indexes_check_exits_zero_when_no_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    command = IndexesCommand()
    monkeypatch.setattr(command, "_load_plan", _load_plan_without_drift)

    args = argparse.Namespace(action="check", path=None, verbose=False)
    command.execute(args)


def test_indexes_sync_dry_run_exits_with_code_3_when_changes_needed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = IndexesCommand()
    monkeypatch.setattr(command, "_load_plan", _load_plan_with_drift)

    args = argparse.Namespace(action="sync", path=None, dry_run=True, drop_stale=False, verbose=False)
    with pytest.raises(SystemExit) as exc:
        command.execute(args)

    assert exc.value.code == 3


def test_indexes_sync_applies_changes_when_not_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    command = IndexesCommand()
    monkeypatch.setattr(command, "_load_plan", _load_plan_with_drift)

    called: dict[str, Any] = {}

    async def fake_get_db() -> object:
        return object()

    async def fake_apply_index_sync_plan(
        db: object,
        plan: IndexSyncPlan,
        *,
        drop_stale: bool,
        dry_run: bool,
    ) -> IndexApplyResult:
        called["db"] = db
        called["plan"] = plan
        called["drop_stale"] = drop_stale
        called["dry_run"] = dry_run
        return IndexApplyResult(created=1, recreated=0, dropped_stale=0)

    monkeypatch.setattr(indexes_command, "get_db", fake_get_db)
    monkeypatch.setattr(indexes_command, "apply_index_sync_plan", fake_apply_index_sync_plan)

    args = argparse.Namespace(action="sync", path=None, dry_run=False, drop_stale=True, verbose=False)
    command.execute(args)

    assert called["drop_stale"] is True
    assert called["dry_run"] is False


def test_indexes_status_runs_without_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    command = IndexesCommand()
    monkeypatch.setattr(command, "_load_plan", _load_plan_without_drift)

    args = argparse.Namespace(action="status", path=None, verbose=False)
    command.execute(args)


def test_indexes_status_verbose_prints_declared_indexes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command = IndexesCommand()
    monkeypatch.setattr(command, "_load_plan", _load_plan_with_drift)

    args = argparse.Namespace(action="status", path=None, verbose=True)
    command.execute(args)

    output = capsys.readouterr().out
    assert "declared: order_business" in output
