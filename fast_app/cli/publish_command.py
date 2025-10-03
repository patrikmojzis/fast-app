"""Publish predefined packages."""

import argparse
from pathlib import Path

from fast_app.utils.file_utils import copy_tree
from .command_base import CommandBase


TEMPLATES_PATH = Path(__file__).parent.parent / "templates"


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
        package_path = TEMPLATES_PATH / "publish" / args.package
        
        if not package_path.exists():
            self._show_available_packages(args.package)
            return
        
        destination = Path.cwd()
        copy_tree(package_path, destination)
        print(f"✅ Published '{args.package}' to current project")

        # List all published files and their destinations for clarity
        published_files = [p for p in package_path.rglob('*') if p.is_file()]
        if published_files:
            print("Files published:")
            for src_file in published_files:
                rel = src_file.relative_to(package_path)
                dest_file = destination / rel
                print(f" - {dest_file}")
    
    def _show_available_packages(self, requested: str) -> None:
        """Show available packages when requested package not found."""
        print(f"❌ Package '{requested}' not found")
        
        publish_dir = TEMPLATES_PATH / "publish"
        if not publish_dir.exists():
            return
        
        available = [d.name for d in publish_dir.iterdir() if d.is_dir()]
        if available:
            print(f"Available: {', '.join(available)}")