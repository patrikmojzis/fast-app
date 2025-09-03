"""Start the async_farm supervisor: fast-app work"""

import argparse

from .command_base import CommandBase


class WorkCommand(CommandBase):
    """Command to spawn the async_farm supervisor."""

    @property
    def name(self) -> str:
        return "work"

    @property
    def help(self) -> str:
        return "Start the async_farm supervisor (worker manager)"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        # Intentionally minimal; supervisor reads configuration from environment variables
        # Users can set MIN_WORKERS, MAX_WORKERS, PREFETCH_PER_WORKER, etc.
        parser.add_argument(
            "--foreground",
            action="store_true",
            help="Run in foreground (default). Provided for future parity."
        )

    def execute(self, args: argparse.Namespace) -> None:  # noqa: ARG002
        # Import lazily to keep CLI import cost low
        from fast_app.integrations.async_farm.supervisor import run_supervisor

        # Blocks until supervisor shuts down
        run_supervisor()


