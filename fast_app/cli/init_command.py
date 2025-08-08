"""Initialize new FastApp project."""

import argparse
from pathlib import Path

from fast_app.utils.file_utils import copy_tree

from .command_base import CommandBase


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
        source = self.template_path / "project_structure"
        
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
        print("1. python -m venv .venv")
        print("2. source .venv/bin/activate")
        print("3. pip install -e .")
        print("4. Start developing!")