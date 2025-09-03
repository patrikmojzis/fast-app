import contextvars
import asyncio
import inspect
import importlib
from typing import Any, Callable


def boot_if_needed(boot_args: dict[str, Any]) -> None:
    if boot_args:
        from fast_app.app_provider import boot
        boot(**boot_args)


def run_async_task(ctx: contextvars.Context, boot_args: dict[str, Any], func: Callable[..., Any], *args, **kwargs) -> Any:
    """Run async function with preserved context and optional app boot."""
    boot_if_needed(boot_args or {})

    def run_in_context() -> Any:
        return asyncio.run(func(*args, **kwargs))

    return ctx.run(run_in_context)


def run_sync_task(ctx: contextvars.Context, boot_args: dict[str, Any], func: Callable[..., Any], *args, **kwargs) -> Any:
    """Run sync function with preserved context and optional app boot."""
    boot_if_needed(boot_args or {})
    return ctx.run(func, *args, **kwargs)


def to_dotted_path(obj: Any) -> str:
    """Return dotted import path for a callable/class/function.

    Only top-level objects are supported (no lambdas, no inner/locals).
    """
    module = inspect.getmodule(obj)
    if module is None or module.__name__ == "__main__":
        raise ValueError("Object must be defined in an importable module")
    qualname = getattr(obj, "__qualname__", getattr(obj, "__name__", None))
    if not qualname:
        raise ValueError("Object must have a qualified name")
    # Reject lambdas and inner functions/classes (contain '<locals>')
    if "<locals>" in qualname or "<lambda>" in qualname or qualname == "<lambda>":
        raise ValueError("Callable must be defined at module top-level to be queued")
    return f"{module.__name__}.{qualname}"


def import_from_path(path: str) -> Any:
    """Import an object from a dotted path like 'package.module:Class' or 'package.module.func'."""
    module_path, _, attr = path.replace(":", ".").rpartition(".")
    if not module_path or not attr:
        raise ValueError(f"Invalid import path: {path}")
    module = importlib.import_module(module_path)
    return getattr(module, attr)