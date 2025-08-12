"""Create files from templates."""

import argparse
import re
from pathlib import Path

from fast_app.utils.serialisation import pascal_case_to_snake_case, snake_case_to_pascal_case
from .command_base import CommandBase


class MakeCommand(CommandBase):
    """Command to create files from templates."""
    
    TYPE_PATHS = {
        'event': 'app/events',
        'broadcast_event': 'app/events',
        'websocket_event': 'app/events',
        'listener': 'app/listeners', 
        'model': 'app/models',
        'notification': 'app/notifications',
        'notification_channel': 'app/notification_channels',
        'observer': 'app/observers',
        'policy': 'app/policies',
        'resource': 'app/http_files/resources',
        'schema': 'app/http_files/schemas',
        'middleware': 'app/http_files/middlewares',
        'broadcast_channel': 'app/broadcasting',
        'storage_driver': 'app/storage_drivers',
        'validator_rule': 'app/rules',
    }
    
    @property
    def name(self) -> str:
        return "make"
    
    @property
    def help(self) -> str:
        return "Create files from templates"
    
    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        """Configure make command arguments."""
        parser.add_argument("type", help="Type of file to create")
        parser.add_argument("name", help="Name for the file and class")
    
    def execute(self, args: argparse.Namespace) -> None:
        """Create file from template."""
        if args.type not in self.TYPE_PATHS:
            print(f"❌ Unknown type: {args.type}")
            print(f"Available: {', '.join(self.TYPE_PATHS.keys())}")
            return
        
        template_path = self.template_path / "make" / f"{args.type}.py"
        if not template_path.exists():
            print(f"❌ Template not found: {template_path}")
            return
        
        class_name = snake_case_to_pascal_case(args.name)
        file_name = pascal_case_to_snake_case(class_name)
        
        content = self._process_template(template_path, args.type, class_name)
        dest_file = self._get_destination(args.type, file_name)
        
        if dest_file.exists():
            print(f"❌ File exists: {dest_file}")
            return
        
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        dest_file.write_text(content, encoding='utf-8')
        
        print(f"✅ Created {args.type}: {dest_file}")
    
    def _process_template(self, template_path: Path, file_type: str, class_name: str) -> str:
        """Process template with class name replacement."""
        content = template_path.read_text(encoding='utf-8')
        # Replace only the placeholder class name across all templates
        # to avoid touching import symbols or base classes.
        pattern = r'\bNewClass\b'
        return re.sub(pattern, class_name, content)
    
    def _get_destination(self, file_type: str, file_name: str) -> Path:
        """Get destination file path."""
        return Path.cwd() / self.TYPE_PATHS[file_type] / f"{file_name}.py"