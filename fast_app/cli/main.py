#!/usr/bin/env python3
"""FastApp CLI - Laravel-inspired Python framework."""

import argparse

from .init_command import InitCommand
from .make_command import MakeCommand
from .publish_command import PublishCommand
from .run_command import RunCommand
from .seed_command import SeedCommand
from .migrate_command import MigrateCommand
from .version_command import VersionCommand


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="FastApp CLI - Modular Python framework for building backend apps",
        prog="fast-app"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Auto-register commands
    commands = [
        InitCommand(),
        MakeCommand(), 
        PublishCommand(),
        RunCommand(),
        SeedCommand(),
        MigrateCommand(),
        VersionCommand(),
    ]
    
    command_map = {}
    for command in commands:
        cmd_parser = subparsers.add_parser(command.name, help=command.help)
        command.configure_parser(cmd_parser)
        command_map[command.name] = command
    
    args = parser.parse_args()
    
    if args.command in command_map:
        command_map[args.command].execute(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()