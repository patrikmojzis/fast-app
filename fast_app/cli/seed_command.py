"""Run a database seeder from app/db/seeders.

Supports both legacy functions and new contract-based seeders.
"""

import argparse
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Callable, Optional, Any

from fast_app.contracts.seeder import Seeder
from fast_app.utils.file_utils import resolve_cli_path
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
        parser.add_argument(
            "--path",
            help="Override seeders directory (relative to project root)",
        )

    def execute(self, args: argparse.Namespace) -> None:
        seeder_name: str = args.name
        file_name = pascal_case_to_snake_case(seeder_name)
        try:
            seeders_dir = resolve_cli_path(args.path, Path("app") / "db" / "seeders")
        except ValueError as exc:
            print(f"❌ {exc}")
            return
        seeder_path = seeders_dir / f"{file_name}.py"
        if not seeder_path.exists():
            print(f"❌ Seeder not found: {seeder_path}")
            return

        module = self._load_module(seeder_path)
        if module is None:
            print("❌ Failed to load seeder module")
            return

        # Prefer new contract class; fallback to functions
        contract = self._resolve_contract(module, seeder_name)
        if contract is not None:
            return self._run_contract(contract, seeder_name)

        runner = self._resolve_runner(module, seeder_name)
        if runner is not None:
            try:
                runner()
                print(f"✅ Seeder executed: {seeder_name}")
            except Exception as exc:  # noqa: BLE001
                print(f"❌ Seeder failed: {exc}")
            return

        print("❌ No seeder entry found. Provide a Seeder class with async seed(), or legacy `seed()`/`run()`.")

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

    def _resolve_contract(self, module: ModuleType, seeder_name: str) -> Optional[Seeder]:
        # Class named seeder_name implements Seeder
        cls = getattr(module, seeder_name, None)
        if isinstance(cls, type) and issubclass(cls, Seeder):
            return cls()  # type: ignore[call-arg]
        # Fallback: class named Seeder
        cls2 = getattr(module, "Seeder", None)
        if isinstance(cls2, type) and issubclass(cls2, Seeder):
            return cls2()  # type: ignore[call-arg]
        return None

    def _run_contract(self, contract: Seeder, seeder_name: str) -> None:
        import asyncio
        async def _run() -> Any:
            contract.boot()
            return await contract.seed()
        try:
            asyncio.run(_run())
            print(f"✅ Seeder executed: {seeder_name}")
        except Exception as exc:  # noqa: BLE001
            print(f"❌ Seeder failed: {exc}")

