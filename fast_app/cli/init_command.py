"""Initialize new FastApp project."""

import argparse
from pathlib import Path

from fast_app.utils.file_utils import copy_tree
from .command_base import CommandBase


TEMPLATES_PATH = Path(__file__).parent.parent / "templates"


class InitCommand(CommandBase):
    """Command to initialize a new FastApp project."""
    
    @property
    def name(self) -> str:
        return "init"
    
    @property
    def help(self) -> str:
        return "Initialize a new FastApp project"
    
    def execute(self, args: argparse.Namespace) -> None:
        """Initialize project in current directory."""
        destination = Path.cwd()
        source = TEMPLATES_PATH / "project_structure"
        
        if not source.exists():
            print(f"❌ Template not found: {source}")
            return
        
        copy_tree(source, destination)
        
        print(f"✅ Project created in {destination}")
        self._show_next_steps()
    
    def _show_next_steps(self) -> None:
        """Display next steps for user."""
        print("\n🎉 Project created successfully!")
        print("\n📋 Next steps:")
        print("1. cp .env.example .env")
        print("2. fast-app serve")
        print("3. Start developing!")