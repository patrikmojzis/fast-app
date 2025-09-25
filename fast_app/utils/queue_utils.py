import contextvars
import asyncio
import inspect
import importlib
from typing import Any, Callable
import types



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
    """Import an object from a dotted path.

    Supports:
    - package.module.func
    - package.module:func
    - package.module.Class
    - package.module.Class.method (auto-binds by instantiating Class with no args)
    """
    dotted = path.replace(":", ".")
    parts = dotted.split(".")
    if len(parts) < 2:
        raise ValueError(f"Invalid import path: {path}")

    # Find the deepest importable module prefix
    module: Any | None = None
    for i in range(len(parts), 0, -1):
        module_name = ".".join(parts[:i])
        try:
            module = importlib.import_module(module_name)
            attrs = parts[i:]
            break
        except ModuleNotFoundError:
            continue

    if module is None:
        # Fallback: try typical split once
        module_name, _, _ = dotted.rpartition(".")
        if not module_name:
            raise ValueError(f"Invalid import path: {path}")
        module = importlib.import_module(module_name)
        attrs = []

    # Resolve attribute chain
    obj: Any = module
    prev: Any = None
    for attr in attrs:
        prev = obj
        obj = getattr(obj, attr)

    # Auto-bind unbound instance method defined on a class
    if isinstance(prev, type) and isinstance(obj, types.FunctionType):
        # obj is function defined on class `prev` (descriptor). Create a callable that instantiates and dispatches
        func = obj
        cls = prev
        if inspect.iscoroutinefunction(func):
            async def _bound_async(*args: Any, **kwargs: Any) -> Any:
                instance = cls()
                return await func(instance, *args, **kwargs)
            return _bound_async
        else:
            def _bound_sync(*args: Any, **kwargs: Any) -> Any:
                instance = cls()
                return func(instance, *args, **kwargs)
            return _bound_sync

    return obj