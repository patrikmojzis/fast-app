from __future__ import annotations

import importlib
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fast_app.contracts.model import Model
from fast_app.core.indexes import Index


@dataclass(slots=True, frozen=True)
class CollectionIndexPlan:
    collection: str
    desired: list[Index]
    existing: list[dict[str, Any]]
    missing: list[Index]
    changed: list[tuple[Index, dict[str, Any]]]
    stale: list[dict[str, Any]]
    unchanged: list[str]

    @property
    def has_drift(self) -> bool:
        return bool(self.missing or self.changed or self.stale)


@dataclass(slots=True, frozen=True)
class IndexSyncPlan:
    collections: list[CollectionIndexPlan]

    @property
    def has_drift(self) -> bool:
        return any(collection.has_drift for collection in self.collections)


@dataclass(slots=True, frozen=True)
class IndexPlanTotals:
    collections: int
    declared: int
    missing: int
    changed: int
    stale: int
    unchanged: int


@dataclass(slots=True, frozen=True)
class IndexApplyResult:
    created: int
    recreated: int
    dropped_stale: int


def discover_project_models(models_dir: Path) -> list[type[Model]]:
    if not models_dir.exists() or not models_dir.is_dir():
        return []

    project_root = Path.cwd().resolve()
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
        importlib.invalidate_caches()

    try:
        relative_models_path = models_dir.resolve().relative_to(project_root)
    except ValueError as exc:
        raise ValueError("models path must stay within the project root") from exc

    module_prefix = ".".join(relative_models_path.parts)

    discovered_models: list[type[Model]] = []
    for module_path in sorted(models_dir.glob("*.py")):
        module_name = module_path.stem
        if module_name.startswith("__"):
            continue

        import_name = f"{module_prefix}.{module_name}"
        module = importlib.import_module(import_name)

        for _, candidate in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(candidate, Model)
                and candidate is not Model
                and candidate.__module__ == import_name
            ):
                discovered_models.append(candidate)

    seen: set[type[Model]] = set()
    unique_models: list[type[Model]] = []
    for model in discovered_models:
        if model in seen:
            continue
        seen.add(model)
        unique_models.append(model)

    return sorted(unique_models, key=lambda model: model.collection_name())


async def build_index_sync_plan(db: Any, models: list[type[Model]]) -> IndexSyncPlan:
    indexes_by_collection = _collect_declared_indexes_by_collection(models)
    plans: list[CollectionIndexPlan] = []

    for collection_name, declared_indexes in sorted(indexes_by_collection.items(), key=lambda item: item[0]):
        collection = db[collection_name]
        existing_indexes = await collection.list_indexes().to_list(length=None)

        desired_by_name = {index.name: index for index in declared_indexes}
        existing_by_name = {index["name"]: index for index in existing_indexes if "name" in index}

        missing: list[Index] = []
        changed: list[tuple[Index, dict[str, Any]]] = []
        unchanged: list[str] = []

        for declared in declared_indexes:
            existing = existing_by_name.get(declared.name)
            if existing is None:
                missing.append(declared)
                continue

            if _declared_index_signature(declared) == _existing_index_signature(existing):
                unchanged.append(declared.name)
            else:
                changed.append((declared, existing))

        stale = [
            existing
            for name, existing in existing_by_name.items()
            if name != "_id_" and name not in desired_by_name
        ]

        plans.append(
            CollectionIndexPlan(
                collection=collection_name,
                desired=declared_indexes,
                existing=existing_indexes,
                missing=missing,
                changed=changed,
                stale=stale,
                unchanged=unchanged,
            )
        )

    return IndexSyncPlan(collections=plans)


async def apply_index_sync_plan(
    db: Any,
    plan: IndexSyncPlan,
    *,
    drop_stale: bool = False,
    dry_run: bool = False,
) -> IndexApplyResult:
    created = 0
    recreated = 0
    dropped_stale = 0

    for collection_plan in plan.collections:
        collection = db[collection_plan.collection]

        for declared, _ in collection_plan.changed:
            recreated += 1
            if dry_run:
                continue
            await collection.drop_index(declared.name)
            await collection.create_index(declared.keys, **declared.mongo_options())

        for declared in collection_plan.missing:
            created += 1
            if dry_run:
                continue
            await collection.create_index(declared.keys, **declared.mongo_options())

        if drop_stale:
            for stale in collection_plan.stale:
                stale_name = stale.get("name")
                if not stale_name or stale_name == "_id_":
                    continue
                dropped_stale += 1
                if dry_run:
                    continue
                await collection.drop_index(stale_name)

    return IndexApplyResult(created=created, recreated=recreated, dropped_stale=dropped_stale)


def get_plan_totals(plan: IndexSyncPlan) -> IndexPlanTotals:
    declared = sum(len(collection.desired) for collection in plan.collections)
    missing = sum(len(collection.missing) for collection in plan.collections)
    changed = sum(len(collection.changed) for collection in plan.collections)
    stale = sum(len(collection.stale) for collection in plan.collections)
    unchanged = sum(len(collection.unchanged) for collection in plan.collections)

    return IndexPlanTotals(
        collections=len(plan.collections),
        declared=declared,
        missing=missing,
        changed=changed,
        stale=stale,
        unchanged=unchanged,
    )


def _collect_declared_indexes_by_collection(
    models: list[type[Model]],
) -> dict[str, list[Index]]:
    by_collection: dict[str, list[Index]] = {}
    signatures_by_collection_and_name: dict[tuple[str, str], tuple[Any, ...]] = {}

    for model in models:
        collection_name = model.collection_name()
        by_collection.setdefault(collection_name, [])

        declared = getattr(model, "indexes", []) or []
        if not isinstance(declared, list):
            raise TypeError(
                f"Model '{model.__name__}' must declare 'indexes' as list[Index], got {type(declared).__name__}"
            )

        for index in declared:
            if not isinstance(index, Index):
                raise TypeError(
                    f"Model '{model.__name__}' index declarations must contain Index instances"
                )

            signature = _declared_index_signature(index)
            key = (collection_name, index.name)
            if key in signatures_by_collection_and_name:
                if signatures_by_collection_and_name[key] != signature:
                    raise ValueError(
                        f"Conflicting index definitions for '{index.name}' in collection '{collection_name}'"
                    )
                continue

            signatures_by_collection_and_name[key] = signature
            by_collection[collection_name].append(index)

    for collection_name in by_collection:
        by_collection[collection_name].sort(key=lambda index: index.name)

    return by_collection


def _normalise_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalise_value(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_normalise_value(item) for item in value]
    return value


def _normalise_keys(keys: Any) -> tuple[tuple[str, Any], ...]:
    if hasattr(keys, "items"):
        return tuple((field, direction) for field, direction in keys.items())

    raise TypeError(f"Unsupported key format for index definition: {keys!r}")


def _declared_index_signature(index: Index) -> tuple[Any, ...]:
    return (
        tuple(index.keys),
        bool(index.unique),
        bool(index.sparse),
        bool(index.hidden),
        _normalise_value(index.partial_filter_expression),
        index.expire_after_seconds,
        _normalise_value(index.collation),
    )


def _existing_index_signature(existing: dict[str, Any]) -> tuple[Any, ...]:
    return (
        _normalise_keys(existing.get("key", {})),
        bool(existing.get("unique", False)),
        bool(existing.get("sparse", False)),
        bool(existing.get("hidden", False)),
        _normalise_value(existing.get("partialFilterExpression")),
        existing.get("expireAfterSeconds"),
        _normalise_value(existing.get("collation")),
    )


__all__ = [
    "CollectionIndexPlan",
    "IndexApplyResult",
    "IndexPlanTotals",
    "IndexSyncPlan",
    "apply_index_sync_plan",
    "build_index_sync_plan",
    "discover_project_models",
    "get_plan_totals",
]
