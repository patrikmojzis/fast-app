"""Run a database seeder from app/db/seeders."""

import argparse
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Callable, Optional

from fast_app.utils.serialisation import pascal_case_to_snake_case

from .command_base import CommandBase


class SeedCommand(CommandBase):
    @property
    def name(self) -> str:
        return "seed"

    @property
    def help(self) -> str:
        return "Run a database seeder (app/db/seeders/<name>.py)"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("name", help="Seeder name (e.g., UserSeeder)")

    def execute(self, args: argparse.Namespace) -> None:
        seeder_name: str = args.name
        file_name = pascal_case_to_snake_case(seeder_name)
        seeder_path = Path.cwd() / "app" / "db" / "seeders" / f"{file_name}.py"
        if not seeder_path.exists():
            print(f"❌ Seeder not found: {seeder_path}")
            return

        module = self._load_module(seeder_path)
        if module is None:
            print("❌ Failed to load seeder module")
            return

        # Prefer `seed()` function; fallback to `run()` or Class.run()
        runner = self._resolve_runner(module, seeder_name)
        if runner is None:
            print("❌ No runner found. Define a function `seed()` or `run()`, or a class with `run()`.")
            return

        try:
            runner()
            print(f"✅ Seeder executed: {seeder_name}")
        except Exception as exc:  # noqa: BLE001
            print(f"❌ Seeder failed: {exc}")

    def _load_module(self, path: Path) -> Optional[ModuleType]:
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _resolve_runner(self, module: ModuleType, seeder_name: str) -> Optional[Callable[[], None]]:
        # function seed()
        func = getattr(module, "seed", None)
        if callable(func):
            return func
        # function run()
        run_func = getattr(module, "run", None)
        if callable(run_func):
            return run_func
        # class with run()
        cls = getattr(module, seeder_name, None)
        if cls is not None:
            method = getattr(cls, "run", None)
            if callable(method):
                return method
        return None


