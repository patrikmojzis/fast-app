"""Base command for CLI operations."""

import argparse
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class CommandBase(ABC):
    """Base class for all CLI commands."""
    
    @property
    def template_path(self) -> Path:
        """Get the path to template files."""
        return Path(__file__).parent.parent / "templates"
    
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