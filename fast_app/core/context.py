from __future__ import annotations

import pickle
import warnings
from contextvars import ContextVar
from typing import Any, Callable, Dict, Generic, Iterable, Mapping, MutableMapping, Optional, Tuple, Type, TypeVar, overload, cast


T = TypeVar("T")


class ContextKey(Generic[T]):
    """Typed key handle for values stored in the application context.

    Using a typed key provides better type inference for `get`/`set` calls.
    """

    __slots__ = ("name", "default", "require_picklable")

    def __init__(self, name: str, default: Optional[T] = None, *, require_picklable: bool = False) -> None:
        self.name = name
        self.default = default
        self.require_picklable = require_picklable

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"ContextKey(name={self.name!r}, default={self.default!r}, require_picklable={self.require_picklable!r})"


class _ContextStore:
    """Central, typed runtime context based on Python ContextVars.

    - Per-task/process values stored in `ContextVar`s.
    - Provides typed helpers via `ContextKey[T]`.
    - Can produce a picklable snapshot for cross-process propagation.
    - Can install such snapshot in a fresh process.

    Notes on picklability:
    - Values that are not picklable will not be included in snapshots.
    - `set()` warns once per key when storing a non-picklable value.
    """

    def __init__(self) -> None:
        self._vars: Dict[str, ContextVar[Any]] = {}
        self._defaults: Dict[str, Any] = {}
        self._warned_unpicklable: set[str] = set()

    # --------------- registration ---------------
    def define(self, key: ContextKey[T]) -> ContextKey[T]:
        """Define/register a key. If already present, returns the same key.

        Defining creates a backing ContextVar with the provided default.
        """
        if key.name not in self._vars:
            self._vars[key.name] = ContextVar(key.name, default=key.default)
            if key.default is not None:
                self._defaults[key.name] = key.default
        return key

    # --------------- basic get/set ---------------
    def _get_var(self, name: str, default: Any = None) -> ContextVar[Any]:
        if name not in self._vars:
            self._vars[name] = ContextVar(name, default=default)
            if default is not None:
                self._defaults[name] = default
        return self._vars[name]

    def _warn_if_unpicklable(self, key: str, value: Any, *, required: bool = False) -> None:
        try:
            pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            if required:
                raise TypeError(
                    f"Context value for key {key!r} must be picklable for cross-process propagation."
                )
            if key not in self._warned_unpicklable:
                self._warned_unpicklable.add(key)
                warnings.warn(
                    f"Context value for key {key!r} is not picklable; it will not propagate to workers or listeners.",
                    RuntimeWarning,
                    stacklevel=2,
                )

    @overload
    def get(self, key: ContextKey[T]) -> Optional[T]:
        ...

    @overload
    def get(self, key: ContextKey[T], default: T) -> T:
        ...

    @overload
    def get(self, key: str) -> Any:
        ...

    @overload
    def get(self, key: str, default: T) -> T:
        ...

    def get(self, key: ContextKey[Any] | str, default: Any = None) -> Any:
        name = key.name if isinstance(key, ContextKey) else key
        var_default = key.default if isinstance(key, ContextKey) else self._defaults.get(name, None)
        var = self._get_var(name, default=var_default)
        sentinel = object()
        val = var.get(sentinel)
        if val is sentinel:
            return default if default is not None else var_default
        return val

    @overload
    def set(self, key: ContextKey[T], value: T) -> None:
        ...

    @overload
    def set(self, key: str, value: Any) -> None:
        ...

    def set(self, key: ContextKey[Any] | str, value: Any) -> None:
        name = key.name if isinstance(key, ContextKey) else key
        require_picklable = key.require_picklable if isinstance(key, ContextKey) else False
        self._warn_if_unpicklable(name, value, required=require_picklable)
        var_default = key.default if isinstance(key, ContextKey) else self._defaults.get(name, None)
        var = self._get_var(name, default=var_default)
        var.set(value)

    def clear(self, *names: str) -> None:
        """Clear selected keys (or all if none provided) back to defaults for this context."""
        to_clear: Iterable[str] = names or tuple(self._vars.keys())
        for name in to_clear:
            # Reset by setting to default (ContextVar has no direct reset-to-default API per context)
            default = self._defaults.get(name, None)
            var = self._get_var(name, default=default)
            if default is None:
                # Setting to None is acceptable; consumers should handle None if no default is defined.
                var.set(None)
            else:
                var.set(default)

    # --------------- cross-process propagation ---------------
    def snapshot(self, *, picklable_only: bool = True, include_defaults: bool = True) -> Dict[str, Any]:
        """Return a dict snapshot suitable for pickling and sending to another process.

        - When `picklable_only` is True, unpicklable values are dropped.
        - When `include_defaults` is True, include keys even if at default.
        """
        out: Dict[str, Any] = {}
        for name, var in self._vars.items():
            sentinel = object()
            val = var.get(sentinel)
            if val is sentinel:
                # No value set; fall back to explicit default if requested
                if include_defaults and name in self._defaults:
                    val = self._defaults[name]
                else:
                    continue
            if picklable_only:
                try:
                    pickle.dumps(val, protocol=pickle.HIGHEST_PROTOCOL)
                except Exception:
                    continue
            out[name] = val
        return out

    def install(self, values: Mapping[str, Any]) -> None:
        """Install values from a snapshot dict into the current context.

        Unknown keys are created lazily.
        """
        for name, value in values.items():
            var = self._get_var(name, default=self._defaults.get(name))
            var.set(value)

    # --------------- utils ---------------
    def keys(self) -> Tuple[str, ...]:
        return tuple(self._vars.keys())

    def items(self) -> Tuple[Tuple[str, Any], ...]:
        return tuple((k, self.get(k)) for k in self._vars.keys())


# Public singleton store
context = _ContextStore()


U = TypeVar("U")


class _DefineKey:
    """Callable + subscribable factory for `ContextKey`.

    Supports both:
    - define_key("name", default=None, require_picklable=False)
    - define_key[T]("name", default=None, require_picklable=False)
    """

    def __call__(
        self, name: str, default: Optional[U] = None, *, require_picklable: bool = False
    ) -> ContextKey[U]:
        key: ContextKey[Any] = ContextKey(name, default, require_picklable=require_picklable)
        return cast(ContextKey[U], context.define(key))

    def __getitem__(self, _typ: Type[U]) -> Callable[[str, Optional[U]], ContextKey[U]]:
        def factory(name: str, default: Optional[U] = None, *, require_picklable: bool = False) -> ContextKey[U]:
            key: ContextKey[Any] = ContextKey(name, default, require_picklable=require_picklable)
            return cast(ContextKey[U], context.define(key))

        return factory


define_key = _DefineKey()


__all__ = [
    "ContextKey",
    "context",
    "define_key",
]


