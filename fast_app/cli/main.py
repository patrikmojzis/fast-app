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
from .exec_command import ExecCommand
from .work_command import WorkCommand
from .serve_command import ServeCommand


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
        WorkCommand(),
        ServeCommand(),
        SeedCommand(),
        MigrateCommand(),
        VersionCommand(),
    ]
    
    command_map = {}
    for command in commands:
        cmd_parser = subparsers.add_parser(command.name, help=command.help)
        command.configure_parser(cmd_parser)
        command_map[command.name] = command

    # exec subcommand for app-local commands
    exec_cmd = ExecCommand()
    exec_parser = subparsers.add_parser(exec_cmd.name, help=exec_cmd.help)
    exec_cmd.configure_parser(exec_parser)
    command_map[exec_cmd.name] = exec_cmd
    
    args = parser.parse_args()
    
    if args.command in command_map:
        command_map[args.command].execute(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()