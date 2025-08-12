"""Publish predefined packages."""

import argparse
from pathlib import Path

from fast_app.utils.file_utils import copy_tree
from .command_base import CommandBase


class PublishCommand(CommandBase):
    """Command to publish predefined packages."""
    
    @property
    def name(self) -> str:
        return "publish"
    
    @property
    def help(self) -> str:
        return "Publish predefined packages"
    
    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        """Configure publish command arguments."""
        parser.add_argument("package", help="Package name to publish")
    
    def execute(self, args: argparse.Namespace) -> None:
        """Publish package to current project."""
        package_path = self.template_path / "publish" / args.package
        
        if not package_path.exists():
            self._show_available_packages(args.package)
            return
        
        destination = Path.cwd()
        copy_tree(package_path, destination)
        print(f"✅ Published '{args.package}' to current project")
    
    def _show_available_packages(self, requested: str) -> None:
        """Show available packages when requested package not found."""
        print(f"❌ Package '{requested}' not found")
        
        publish_dir = self.template_path / "publish"
        if not publish_dir.exists():
            return
        
        available = [d.name for d in publish_dir.iterdir() if d.is_dir()]
        if available:
            print(f"Available: {', '.join(available)}")