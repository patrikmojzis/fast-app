"""Run app modules easily for debugging: fast-app run <module_name>."""

import argparse
import subprocess
import sys

from .command_base import CommandBase


class RunCommand(CommandBase):
    """Command to run a module via `python -m app.modules.<module_name>`."""

    @property
    def name(self) -> str:
        return "run"

    @property
    def help(self) -> str:
        return "Run a module: fast-app run <module_name> (e.g., api, scheduler)"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "module_name",
            help="Module name under app.modules to run (e.g., api, scheduler)",
        )

    def execute(self, args: argparse.Namespace) -> None:
        module = args.module_name.strip().replace("/", ".").replace("-", "_")
        module_path = f"app.modules.{module}"
        cmd = [sys.executable, "-m", module_path]
        try:
            result = subprocess.run(cmd)
            if result.returncode != 0:
                print(f"❌ Module exited with code {result.returncode}: {' '.join(cmd)}")
        except FileNotFoundError:
            print("❌ Python executable not found")
        except Exception as exc:
            print(f"❌ Failed to run module '{module_path}': {exc}")


