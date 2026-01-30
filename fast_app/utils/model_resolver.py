from __future__ import annotations

import importlib
import re
import sys
from typing import Iterable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from fast_app.contracts.model import Model as ModelBase


def get_model_base() -> type["ModelBase"]:
    from fast_app.contracts.model import Model  # local import to avoid cycles
    return Model


def resolve_model_annotation(annotation: object) -> Optional[type["ModelBase"]]:
    try:
        model_base = get_model_base()
        if isinstance(annotation, type) and issubclass(annotation, model_base):
            return annotation
    except Exception:
        return None
    return None


def normalize_model_name(name: str) -> str:
    parts = [part for part in name.replace("-", "_").split("_") if part]
    if not parts:
        return name
    return "".join(part.capitalize() for part in parts)


def to_snake_case(name: str) -> str:
    if not name:
        return name
    # Convert CamelCase to snake_case while preserving existing underscores
    step_one = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    step_two = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", step_one)
    return step_two.replace("-", "_").lower()


def model_name_from_field(field: str) -> Optional[str]:
    if not field:
        return None
    cleaned = field.strip()
    if cleaned.startswith("$."):
        cleaned = cleaned[2:]
    if "." in cleaned:
        cleaned = cleaned.split(".")[-1]
    if cleaned.endswith("_ids"):
        cleaned = cleaned[:-4]
    elif cleaned.endswith("_id"):
        cleaned = cleaned[:-3]
    return cleaned or None


def resolve_model_reference(
    reference: type["ModelBase"] | str,
    *,
    base: Optional[type] = None,
    module_hint: Optional[str] = None,
) -> type["ModelBase"]:
    model_base = base or get_model_base()
    if isinstance(reference, type) and issubclass(reference, model_base):
        return reference
    if isinstance(reference, str):
        return resolve_model_from_name(reference, base=model_base, module_hint=module_hint)
    raise TypeError("Model reference must be a Model subclass or string name")


def resolve_model_from_field(
    field: str,
    *,
    base: Optional[type] = None,
    module_hint: Optional[str] = None,
) -> type["ModelBase"]:
    name = model_name_from_field(field)
    if not name:
        raise ValueError(f"Unable to infer model name from field '{field}'")
    return resolve_model_from_name(name, base=base, module_hint=module_hint)


def resolve_model_from_name(
    name: str,
    *,
    base: Optional[type] = None,
    module_hint: Optional[str] = None,
) -> type["ModelBase"]:
    model_base = base or get_model_base()
    normalized = normalize_model_name(name)

    # Prefer already-loaded subclasses to avoid extra imports
    for cls in _iter_model_subclasses(model_base):
        if cls.__name__ == normalized:
            return cls

    candidates = _candidate_model_paths(name, normalized, module_hint=module_hint)
    last_error: Optional[Exception] = None
    for module_name, class_name in candidates:
        try:
            module = sys.modules.get(module_name) or importlib.import_module(module_name)
        except Exception as exc:
            last_error = exc
            continue
        model_cls = getattr(module, class_name, None)
        if isinstance(model_cls, type) and issubclass(model_cls, model_base):
            return model_cls

    raise ValueError(
        f"Unable to resolve model '{name}'. Tried modules {[c[0] for c in candidates]}."
    ) from last_error


def _iter_model_subclasses(base: type) -> Iterable[type]:
    for cls in base.__subclasses__():
        yield cls
        yield from _iter_model_subclasses(cls)


def _candidate_model_paths(
    name: str,
    normalized: str,
    *,
    module_hint: Optional[str],
) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    snake = to_snake_case(name)

    def _add(module: Optional[str], cls_name: Optional[str]) -> None:
        if not module or not cls_name:
            return
        entry = (module, cls_name)
        if entry not in candidates:
            candidates.append(entry)

    if module_hint:
        _add(module_hint, normalized)
        if "." in module_hint:
            base_module = module_hint.rsplit(".", 1)[0]
            _add(base_module, normalized)
            _add(f"{base_module}.{snake}", normalized)

    if "." in name:
        module, _, tail = name.rpartition(".")
        if module and tail:
            _add(module, tail)
            _add(module, normalized)
        _add(name, normalized)

    _add(f"app.models.{snake}", normalized)
    _add(name, normalized)
    _add(f"{name}.{normalized}", normalized)

    return candidates
