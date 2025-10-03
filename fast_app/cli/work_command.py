"""Start the async_farm supervisor: fast-app work"""

import argparse
import asyncio

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
        parser.add_argument(
            "--tui",
            action="store_true",
            help="Start interactive TUI dashboard for the supervisor"
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Verbose output"
        )

    def execute(self, args: argparse.Namespace) -> None:
        # Import lazily to keep CLI import cost low
        from fast_app.integrations.async_farm.supervisor import AsyncFarmSupervisor

        if getattr(args, "tui", False):
            # Start supervisor and TUI together; shut down supervisor when TUI exits
            from fast_app.integrations.async_farm.supervisor_tui import SupervisorTUI
            sup = AsyncFarmSupervisor(verbose=False)
            sup_tui = SupervisorTUI(sup)
            sup_tui.run()
            return

        # Default: run supervisor without TUI; blocks until shutdown
        sup = AsyncFarmSupervisor(verbose=getattr(args, "verbose", True))
        asyncio.run(sup.run())


