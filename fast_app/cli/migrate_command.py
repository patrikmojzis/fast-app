"""Run a migration from app/db/migrations.

Supports both legacy functions and new contract-based migrations.
"""

import argparse
import importlib.util
import inspect
from pathlib import Path
from types import ModuleType
from typing import Callable, Optional, Any

from fast_app.contracts.migration import Migration
from fast_app.utils.file_utils import resolve_cli_path
from fast_app.utils.serialisation import pascal_case_to_snake_case
from .command_base import CommandBase


class MigrateCommand(CommandBase):
    @property
    def name(self) -> str:
        return "migrate"

    @property
    def help(self) -> str:
        return "Run a migration (app/db/migrations/<name>.py)"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("name", help="Migration name (e.g., AddIndexToUsers)")
        parser.add_argument(
            "--path",
            help="Override migrations directory (relative to project root)",
        )

    def execute(self, args: argparse.Namespace) -> None:
        migration_name: str = args.name
        file_name = pascal_case_to_snake_case(migration_name)
        try:
            migrations_dir = resolve_cli_path(args.path, Path("app") / "db" / "migrations")
        except ValueError as exc:
            print(f"❌ {exc}")
            return
        migration_path = migrations_dir / f"{file_name}.py"
        if not migration_path.exists():
            print(f"❌ Migration not found: {migration_path}")
            return

        module = self._load_module(migration_path)
        if module is None:
            print("❌ Failed to load migration module")
            return

        # Prefer new contract class; fallback to functions
        try:
            contract = self._resolve_contract(module, migration_name)
        except ValueError as exc:
            print(f"❌ {exc}")
            return
        if contract is not None:
            return self._run_contract(contract, migration_name)

        runner = self._resolve_runner(module, migration_name)
        if runner is not None:
            try:
                runner()
                print(f"✅ Migration executed: {migration_name}")
            except Exception as exc:  # noqa: BLE001
                print(f"❌ Migration failed: {exc}")
            return

        print(
            "❌ No migration entry found. Provide a Migration class with async migrate(), "
            "a single local Migration subclass, or legacy `migrate()`/`run()`."
        )

    def _load_module(self, path: Path) -> Optional[ModuleType]:
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _resolve_runner(self, module: ModuleType, migration_name: str) -> Optional[Callable[[], None]]:
        # function migrate()
        func = getattr(module, "migrate", None)
        if callable(func):
            return func
        # function run()
        run_func = getattr(module, "run", None)
        if callable(run_func):
            return run_func
        # class with migrate() / run()
        cls = getattr(module, migration_name, None)
        if cls is not None:
            mig = getattr(cls, "migrate", None)
            if callable(mig):
                return mig
            run_method = getattr(cls, "run", None)
            if callable(run_method):
                return run_method
        return None

    def _resolve_contract(self, module: ModuleType, migration_name: str) -> Optional[Migration]:
        for class_name in (migration_name, "Migration"):
            cls = getattr(module, class_name, None)
            if self._is_contract_candidate(cls, module):
                return cls()  # type: ignore[call-arg]

        candidates = [
            value
            for value in vars(module).values()
            if self._is_contract_candidate(value, module)
        ]
        if len(candidates) == 1:
            return candidates[0]()  # type: ignore[call-arg]
        if len(candidates) > 1:
            names = ", ".join(sorted(candidate.__name__ for candidate in candidates))
            raise ValueError(
                "Multiple migration classes found in the module. "
                f"Use a class named '{migration_name}' or 'Migration'. Candidates: {names}."
            )
        return None

    def _is_contract_candidate(self, value: object, module: ModuleType) -> bool:
        return (
            isinstance(value, type)
            and value is not Migration
            and issubclass(value, Migration)
            and value.__module__ == module.__name__
            and not inspect.isabstract(value)
        )

    def _run_contract(self, contract: Migration, migration_name: str) -> None:
        import asyncio
        async def _run() -> Any:
            contract.boot()
            return await contract.migrate()
        try:
            asyncio.run(_run())
            print(f"✅ Migration executed: {migration_name}")
        except Exception as exc:  # noqa: BLE001
            print(f"❌ Migration failed: {exc}")
