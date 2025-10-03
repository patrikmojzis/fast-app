from __future__ import annotations

import argparse

from fast_app.contracts.command import Command

class NewClass(Command):
    @property
    def name(self) -> str:
        # Use namespaced name like "group:action"
        return "new:command"

    @property
    def help(self) -> str:
        return "Describe what this command does"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--example", help="Example flag", action="store_true")

    async def execute(self, args: argparse.Namespace) -> None:
        if args.example:
            print("Example flag enabled")
        print("NewClass executed")


