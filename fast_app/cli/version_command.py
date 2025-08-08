"""Show version information."""

import argparse

from .command_base import CommandBase


class VersionCommand(CommandBase):
    """Command to show version information."""
    
    @property
    def name(self) -> str:
        return "version"
    
    @property
    def help(self) -> str:
        return "Show version information"
    
    def execute(self, args: argparse.Namespace) -> None:
        """Show version and author information."""
        print("FastApp v0.1.0")
        print("Author: Patrik Mojzis")