import argparse
import asyncio
import importlib
import inspect
import pkgutil
from pathlib import Path

from fast_app.cli.command_base import CommandBase
from fast_app import Command


class ExecCommand(CommandBase):
    @property
    def name(self) -> str:
        return "exec"

    @property
    def help(self) -> str:
        return "Run app-specific commands from app/cli"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("exec_command", nargs="?", help="Command name, e.g. group:action")
        parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments for the app command")

    def execute(self, args: argparse.Namespace) -> None:
        if not args.exec_command or args.exec_command in ("--list", "list"):
            _list_app_commands()
            return

        commands = _discover_app_commands()
        target = commands.get(args.exec_command)
        if not target:
            print(f"❌ Unknown app command: {args.exec_command}")
            _suggest_similar(args.exec_command, list(commands.keys()))
            print("Use 'fast-app exec --list' to see available app commands.")
            return

        parser = argparse.ArgumentParser(prog=f"fast-app exec {target.name}")
        target.configure_parser(parser)
        parsed = parser.parse_args(args.args)

        async def _run():
            target.boot()
            if not inspect.iscoroutinefunction(target.execute):
                raise TypeError(f"App command '{target.name}' must define async execute(...) ")
            await target.execute(parsed)

        asyncio.run(_run())


def _list_app_commands() -> None:
    commands = _discover_app_commands()
    if not commands:
        print("No app commands found under app/cli")
        return
    print("Available app commands:\n")
    for name, cmd in sorted(commands.items()):
        print(f"  {name:20} {cmd.help}")


def _discover_app_commands() -> dict[str, Command]:
    results: dict[str, Command] = {}
    app_cli_path = Path.cwd() / "app" / "cli"
    if not app_cli_path.exists() or not app_cli_path.is_dir():
        return results

    # Optional provider: app.cli.provider:get_commands
    try:
        provider = importlib.import_module("app.cli.provider")
        get_commands = getattr(provider, "get_commands", None)
        if callable(get_commands):
            for cmd in get_commands():
                if cmd.name in results:
                    raise ValueError(f"Duplicate app command: {cmd.name}")
                results[cmd.name] = cmd
    except ModuleNotFoundError:
        pass
    except Exception as exc:
        print(f"⚠️  Failed loading app.cli.provider: {exc}")

    # Auto-discover modules in app.cli
    try:
        pkg = importlib.import_module("app.cli")
        for _, module_name, _ in pkgutil.iter_modules(pkg.__path__):
            if module_name.startswith("__") or module_name == "provider":
                continue
            try:
                mod = importlib.import_module(f"app.cli.{module_name}")
                for obj in mod.__dict__.values():
                    if isinstance(obj, type) and issubclass(obj, Command) and obj is not Command:
                        instance = obj()  # type: ignore[call-arg]
                        if instance.name in results:
                            raise ValueError(f"Duplicate app command: {instance.name}")
                        results[instance.name] = instance
            except Exception as exc:
                print(f"⚠️  Skipping app.cli.{module_name}: {exc}")
    except ModuleNotFoundError:
        pass

    return results


def _suggest_similar(target: str, choices: list[str]) -> None:
    try:
        import difflib
        matches = difflib.get_close_matches(target, choices, n=3, cutoff=0.4)
        if matches:
            print("Did you mean:")
            for m in matches:
                print(f"  {m}")
    except Exception:
        pass


