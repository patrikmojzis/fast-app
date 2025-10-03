"""Base command for built-in FastApp CLI operations (synchronous)."""

import argparse
from abc import ABC, abstractmethod


class CommandBase(ABC):
    """Base class for all built-in CLI commands (sync)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Command name."""
        pass

    @property
    @abstractmethod
    def help(self) -> str:
        """Command help text."""
        pass

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        """Configure command-specific arguments. Override if needed."""
        pass

    @abstractmethod
    def execute(self, args: argparse.Namespace) -> None:
        """Execute the command."""
        pass

