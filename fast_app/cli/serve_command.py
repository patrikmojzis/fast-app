"""Serve the ASGI app with Hypercorn.

Usage:
  fast-app serve [--debug]

When run with --debug, it enables auto-reload and debug log level.
"""

import argparse
import subprocess

from .command_base import CommandBase


class ServeCommand(CommandBase):
    """Command to serve the ASGI app via Hypercorn."""

    @property
    def name(self) -> str:
        return "serve"

    @property
    def help(self) -> str:
        return "Serve the ASGI app with Hypercorn in debug mode"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        pass

    def execute(self, args: argparse.Namespace) -> None:
        cmd: list[str] = [
            "hypercorn",
            "app.modules.asgi.app:app",
            "--bind",
            "0.0.0.0:8000",
            "--reload",
            "--log-level",
            "debug",
        ]

        print(f"Starting Hypercorn in debug mode...")

        try:
            result = subprocess.run(cmd)
            if result.returncode != 0:
                print(f"❌ Serve exited with code {result.returncode}: {' '.join(cmd)}")
        except FileNotFoundError:
            print("❌ 'hypercorn' executable not found. Is it installed in your environment?")
        except Exception as exc:
            print(f"❌ Failed to start Hypercorn: {exc}")


