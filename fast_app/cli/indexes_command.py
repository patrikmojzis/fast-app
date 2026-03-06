"""Inspect and synchronize MongoDB indexes declared on app models."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from fast_app.database.mongo import get_db
from fast_app.utils.file_utils import resolve_cli_path
from fast_app.utils.index_manager import (
    IndexSyncPlan,
    apply_index_sync_plan,
    build_index_sync_plan,
    discover_project_models,
    get_plan_totals,
)
from .command_base import CommandBase


class IndexesCommand(CommandBase):
    @property
    def name(self) -> str:
        return "indexes"

    @property
    def help(self) -> str:
        return "Inspect and synchronize MongoDB indexes declared on models"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        subparsers = parser.add_subparsers(dest="action", required=True)

        status_parser = subparsers.add_parser("status", help="Show current index drift")
        self._configure_common_options(status_parser)

        check_parser = subparsers.add_parser("check", help="Exit non-zero if index drift exists")
        self._configure_common_options(check_parser)

        sync_parser = subparsers.add_parser("sync", help="Create/recreate declared indexes")
        self._configure_common_options(sync_parser)
        sync_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview actions without applying changes",
        )
        sync_parser.add_argument(
            "--drop-stale",
            action="store_true",
            help="Drop indexes that are not declared on model metadata",
        )

    @staticmethod
    def _configure_common_options(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--path",
            help="Override models directory (relative to project root)",
        )
        parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Show detailed collection/index information",
        )

    def execute(self, args: argparse.Namespace) -> None:
        import fast_app.boot  # noqa: F401

        try:
            if args.action == "status":
                asyncio.run(self._status(args))
                return

            if args.action == "check":
                asyncio.run(self._check(args))
                return

            if args.action == "sync":
                asyncio.run(self._sync(args))
                return

            raise ValueError(f"Unknown indexes action: {args.action}")
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            print(f"❌ Indexes command failed: {exc}")
            raise SystemExit(1) from exc

    async def _status(self, args: argparse.Namespace) -> None:
        plan = await self._load_plan(args.path)
        self._print_plan(plan, verbose=args.verbose)

    async def _check(self, args: argparse.Namespace) -> None:
        plan = await self._load_plan(args.path)
        self._print_plan(plan, verbose=args.verbose)

        if plan.has_drift:
            raise SystemExit(2)

    async def _sync(self, args: argparse.Namespace) -> None:
        plan = await self._load_plan(args.path)
        self._print_plan(plan, verbose=args.verbose)

        if args.dry_run:
            if plan.has_drift:
                raise SystemExit(3)
            return

        db = await get_db()
        result = await apply_index_sync_plan(db, plan, drop_stale=args.drop_stale, dry_run=False)
        print(
            "Applied index changes: "
            f"created={result.created}, recreated={result.recreated}, dropped_stale={result.dropped_stale}"
        )

    async def _load_plan(self, path_override: str | None) -> IndexSyncPlan:
        models_path = resolve_cli_path(path_override, Path("app") / "models")
        models = discover_project_models(models_path)
        db = await get_db()
        return await build_index_sync_plan(db, models)

    @staticmethod
    def _print_plan(plan: IndexSyncPlan, *, verbose: bool = False) -> None:
        totals = get_plan_totals(plan)

        print("Index plan summary:")
        print(
            f"collections={totals.collections}, declared={totals.declared}, "
            f"missing={totals.missing}, changed={totals.changed}, stale={totals.stale}, "
            f"unchanged={totals.unchanged}"
        )

        if verbose:
            for collection in plan.collections:
                print(
                    f"- {collection.collection}: declared={len(collection.desired)}, "
                    f"existing={len(collection.existing)}, missing={len(collection.missing)}, "
                    f"changed={len(collection.changed)}, stale={len(collection.stale)}, "
                    f"unchanged={len(collection.unchanged)}"
                )
                if collection.desired:
                    print(
                        "  declared: "
                        + ", ".join(index.name for index in collection.desired)
                    )
                if collection.unchanged:
                    print("  unchanged: " + ", ".join(collection.unchanged))
                if collection.missing:
                    print("  missing: " + ", ".join(index.name for index in collection.missing))
                if collection.changed:
                    print(
                        "  changed: "
                        + ", ".join(index.name for index, _ in collection.changed)
                    )
                if collection.stale:
                    print(
                        "  stale: "
                        + ", ".join(
                            str(existing.get("name"))
                            for existing in collection.stale
                            if existing.get("name")
                        )
                    )
            return

        for collection in plan.collections:
            if not collection.has_drift:
                continue

            print(f"- {collection.collection}:")
            if collection.missing:
                print("  missing: " + ", ".join(index.name for index in collection.missing))
            if collection.changed:
                print(
                    "  changed: "
                    + ", ".join(index.name for index, _ in collection.changed)
                )
            if collection.stale:
                print(
                    "  stale: "
                    + ", ".join(
                        str(existing.get("name"))
                        for existing in collection.stale
                        if existing.get("name")
                    )
                )


__all__ = ["IndexesCommand"]
