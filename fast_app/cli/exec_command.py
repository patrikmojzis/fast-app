import argparse
import asyncio
import importlib
import importlib.util
import inspect
import pkgutil
import sys
from pathlib import Path
from types import ModuleType

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
        parser.add_argument("--list", "-l", dest="list_commands", action="store_true", help="List available app commands and exit")

    def execute(self, args: argparse.Namespace) -> None:
        exec_command = args.exec_command
        if args.list_commands or exec_command is None or exec_command.lower() == "list":
            _list_app_commands()
            return

        commands = _discover_app_commands()
        target = commands.get(exec_command)
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

    _ensure_project_path_on_syspath(Path.cwd())

    _load_provider_commands(results)
    imported_modules = _load_package_modules(results)
    _load_fallback_modules(app_cli_path, imported_modules, results)

    return results


def _load_provider_commands(results: dict[str, Command]) -> None:
    try:
        provider = importlib.import_module("app.cli.provider")
        get_commands = getattr(provider, "get_commands", None)
        if callable(get_commands):
            for cmd in get_commands():
                _register_command(cmd, results)
    except ModuleNotFoundError:
        return
    except Exception as exc:
        print(f"⚠️  Failed loading app.cli.provider: {exc}")


def _load_package_modules(results: dict[str, Command]) -> set[str]:
    imported: set[str] = set()
    try:
        pkg = importlib.import_module("app.cli")
    except ModuleNotFoundError:
        return imported
    except Exception as exc:
        print(f"⚠️  Failed importing app.cli: {exc}")
        return imported

    module_path = getattr(pkg, "__path__", None)
    if module_path is None:
        _collect_module_commands(pkg, results)
        return imported

    for _, module_name, _ in pkgutil.iter_modules(module_path):
        if module_name.startswith("__") or module_name == "provider":
            continue
        try:
            mod = importlib.import_module(f"app.cli.{module_name}")
            imported.add(module_name)
            _collect_module_commands(mod, results)
        except Exception as exc:
            print(f"⚠️  Skipping app.cli.{module_name}: {exc}")
    return imported


def _load_fallback_modules(app_cli_path: Path, imported_modules: set[str], results: dict[str, Command]) -> None:
    for module_path in sorted(app_cli_path.glob("*.py")):
        module_name = module_path.stem
        if module_name.startswith("__") or module_name == "provider" or module_name in imported_modules:
            continue

        spec = importlib.util.spec_from_file_location(f"app.cli.{module_name}", module_path)
        if spec is None or spec.loader is None:
            print(f"⚠️  Skipping {module_path.name}: unable to create module spec")
            continue

        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            _collect_module_commands(module, results)
        except Exception as exc:
            print(f"⚠️  Skipping {module_path.name}: {exc}")


def _collect_module_commands(module: ModuleType, results: dict[str, Command]) -> None:
    for obj in module.__dict__.values():
        if isinstance(obj, type) and issubclass(obj, Command) and obj is not Command:
            instance = obj()  # type: ignore[call-arg]
            _register_command(instance, results)


def _register_command(command: Command, results: dict[str, Command]) -> None:
    if command.name in results:
        raise ValueError(f"Duplicate app command: {command.name}")
    results[command.name] = command


def _ensure_project_path_on_syspath(project_path: Path) -> None:
    project_str = str(project_path)
    if project_str not in sys.path:
        sys.path.insert(0, project_str)
        importlib.invalidate_caches()


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


