"""Serve the ASGI app with Hypercorn (development only).

Usage:
  fast-app serve [--bind HOST:PORT] [--app IMPORT] [--reload-dir DIR ...]

Always runs with auto-reload and log level set to debug. Not for production use.
"""

import argparse
import os
import subprocess
from typing import List

from .command_base import CommandBase


class ServeCommand(CommandBase):
    """Command to serve the ASGI app via Hypercorn."""

    @property
    def name(self) -> str:
        return "serve"

    @property
    def help(self) -> str:
        return "Serve the ASGI app for development (Hypercorn with auto-reload)"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--bind",
            default="0.0.0.0:8000",
            help="Bind address, e.g. 0.0.0.0:8000",
        )
        parser.add_argument(
            "--app",
            default="app.modules.asgi.app:app",
            help="ASGI app import path for Hypercorn",
        )
        parser.add_argument(
            "--reload-dir",
            action="append",
            default=None,
            help="Additional directory to watch for reload (can be used multiple times)",
        )
        parser.add_argument(
            "--log-level",
            default=None,
            help="Override log level (debug, info, warning, error)",
        )

    def _collect_reload_dirs(self, specified: List[str] | None) -> List[str]:
        directories: List[str] = list(specified or [])
        cwd = os.getcwd()
        app_dir = os.path.join(cwd, "app")
        for directory in [cwd, app_dir]:
            if os.path.isdir(directory) and directory not in directories:
                directories.append(directory)
        return directories

    def _build_hypercorn_cmd(self, args: argparse.Namespace) -> List[str]:
        effective_log_level = args.log_level or "debug"

        cmd: List[str] = ["hypercorn", args.app, "--bind", args.bind]

        # Always run in reload mode for development server
        cmd.append("--reload")
        cmd.append("--debug")

        # Some Hypercorn versions do not support --reload-dir; detect and add only if available
        if self._hypercorn_supports_reload_dir():
            for directory in self._collect_reload_dirs(args.reload_dir):
                cmd.extend(["--reload-dir", directory])

        cmd.extend(["--log-level", effective_log_level])
        return cmd

    def _hypercorn_supports_reload_dir(self) -> bool:
        """Return True if the installed Hypercorn supports --reload-dir."""
        try:
            result = subprocess.run(
                ["hypercorn", "-h"], capture_output=True, text=True, check=False
            )
            help_text = (result.stdout or "") + (result.stderr or "")
            return "--reload-dir" in help_text
        except Exception:
            return False

    def execute(self, args: argparse.Namespace) -> None:
        effective_log_level = args.log_level or "debug"
        cmd = self._build_hypercorn_cmd(args)

        print(
            "Starting Hypercorn (development only) ...\n  app=\"%s\"\n  bind=\"%s\"\n  reload=on\n  log-level=\"%s\"\n\nWARNING: This command is for development only and should not be used in production."
            % (
                args.app,
                args.bind,
                effective_log_level,
            )
        )

        try:
            result = subprocess.run(cmd)
            if result.returncode != 0:
                print(f"❌ Serve exited with code {result.returncode}: {' '.join(cmd)}")
        except FileNotFoundError:
            print("❌ 'hypercorn' executable not found. Is it installed in your environment?")
        except Exception as exc:
            print(f"❌ Failed to start Hypercorn: {exc}")


