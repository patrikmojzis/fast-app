"""Run a migration from app/db/migrations."""

import argparse
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Callable, Optional

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

    def execute(self, args: argparse.Namespace) -> None:
        migration_name: str = args.name
        file_name = pascal_case_to_snake_case(migration_name)
        migration_path = Path.cwd() / "app" / "db" / "migrations" / f"{file_name}.py"
        if not migration_path.exists():
            print(f"❌ Migration not found: {migration_path}")
            return

        module = self._load_module(migration_path)
        if module is None:
            print("❌ Failed to load migration module")
            return

        # Prefer `migrate()` function; fallback to `run()` or Class.migrate()/Class.run()
        runner = self._resolve_runner(module, migration_name)
        if runner is None:
            print("❌ No runner found. Define `migrate()` or `run()`, or a class with `migrate()`/`run()`.")
            return

        try:
            runner()
            print(f"✅ Migration executed: {migration_name}")
        except Exception as exc:  # noqa: BLE001
            print(f"❌ Migration failed: {exc}")

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


