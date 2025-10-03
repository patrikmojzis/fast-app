"""Command contract for app-local exec commands (async with customizable boot)."""

from __future__ import annotations

import argparse
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
# from fast_app.app_provider import boot


class Command(ABC):
    """Base class for app-local commands (to be run via `fast-app exec`)."""
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def help(self) -> str:
        pass

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        pass

    def boot(self):
        """Optional boot hook. Override to customize environment before execute."""
        import fast_app.boot

    @abstractmethod
    async def execute(self, args: argparse.Namespace) -> Any:
        """Run the command asynchronously."""
        raise NotImplementedError


