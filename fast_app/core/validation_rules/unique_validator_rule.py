from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable, Optional, Sequence, TYPE_CHECKING

from bson import ObjectId
from fast_validation import ValidatorRule, ValidationRuleException
from quart import has_request_context, request

from fast_app.utils.model_resolver import resolve_model_from_field, resolve_model_reference
from fast_app.utils.serialisation import pascal_case_to_snake_case

if TYPE_CHECKING:
    from fast_app.contracts.model import Model as ModelBase


CurrentIdResolver = Callable[[], Any | Awaitable[Any]]


class UniqueValidatorRule(ValidatorRule):
    def __init__(
        self,
        model: type | str | None = None,
        *,
        field: Optional[str] = None,
        db_key: Optional[str] = None,
        allow_null: bool = False,
        each: bool = False,
        exclude_current: bool = True,
        current_id_key: str = "_id",
        route_param: Optional[str] = None,
        current_id_resolver: Optional[CurrentIdResolver] = None,
    ) -> None:
        self.model = model
        self.field = field
        self.db_key = db_key
        self.allow_null = allow_null
        self.each = each
        self.exclude_current = exclude_current
        self.current_id_key = current_id_key
        self.route_param = route_param
        self.current_id_resolver = current_id_resolver
        self._resolved_model: Optional[type["ModelBase"]] = None

    def _display_name(self, loc: Sequence[str]) -> str:
        if loc:
            return ".".join(str(part) for part in loc)
        if self.field:
            return self.field
        if self.model is None:
            return "value"
        if isinstance(self.model, str):
            return pascal_case_to_snake_case(self.model)
        return pascal_case_to_snake_case(self.model.__name__)

    def _resolve_model_class(self, loc: Sequence[str]) -> type["ModelBase"]:
        if self._resolved_model is not None:
            return self._resolved_model

        if self.model is not None:
            if isinstance(self.model, type):
                try:
                    from fast_app.contracts.model import Model as ModelBase  # local import
                    if issubclass(self.model, ModelBase):
                        self._resolved_model = resolve_model_reference(self.model)
                        return self._resolved_model
                except Exception:
                    pass
                if hasattr(self.model, "exists"):
                    self._resolved_model = self.model  # type: ignore[assignment]
                    return self._resolved_model
            self._resolved_model = resolve_model_reference(self.model)  # type: ignore[arg-type]
            return self._resolved_model

        field_name = self.field
        if not field_name and loc:
            field_name = str(loc[-1])

        if not field_name:
            raise ValueError(
                "UniqueValidatorRule: unable to resolve model. "
                "Pass model=... or field=... to infer it."
            )

        self._resolved_model = resolve_model_from_field(field_name)
        return self._resolved_model

    def _resolve_db_key(self, loc: Sequence[str]) -> str:
        if self.db_key:
            return self.db_key
        if self.field:
            return self.field
        if loc:
            return str(loc[-1])
        raise ValueError(
            "UniqueValidatorRule: unable to resolve db key. "
            "Pass db_key=... or field=...."
        )

    def _default_route_param(self, model_class: type["ModelBase"]) -> str:
        collection_name = getattr(model_class, "collection_name", None)
        if callable(collection_name):
            try:
                base = str(collection_name())
            except Exception:
                base = pascal_case_to_snake_case(model_class.__name__)
        else:
            base = pascal_case_to_snake_case(model_class.__name__)
        return base if base.endswith("_id") else f"{base}_id"

    async def _resolve_current_id(self, model_class: type["ModelBase"]) -> Any:
        if not self.exclude_current:
            return None

        current_id: Any = None
        if self.current_id_resolver is not None:
            resolved = self.current_id_resolver()
            current_id = await resolved if inspect.isawaitable(resolved) else resolved
        elif has_request_context():
            view_args = request.view_args or {}
            candidates = []
            if self.route_param:
                candidates.append(self.route_param)
            candidates.append(self._default_route_param(model_class))
            candidates.extend(["id", "_id"])

            seen: set[str] = set()
            for candidate in candidates:
                if candidate in seen:
                    continue
                seen.add(candidate)
                value = view_args.get(candidate)
                if value not in (None, ""):
                    current_id = value
                    break

            if current_id in (None, ""):
                id_like_keys = [
                    key
                    for key, value in view_args.items()
                    if value not in (None, "") and (key.endswith("_id") or key in {"id", "_id"})
                ]
                if len(id_like_keys) == 1:
                    current_id = view_args[id_like_keys[0]]
                elif len(view_args) == 1:
                    only_key = next(iter(view_args))
                    current_id = view_args.get(only_key)

        if current_id in (None, ""):
            return None

        if isinstance(current_id, bytes):
            current_id = current_id.decode()

        if self.current_id_key == "_id" and isinstance(current_id, str) and ObjectId.is_valid(current_id):
            return ObjectId(current_id)

        return current_id

    async def validate(self, *, value: Any, data: dict, loc: Sequence[str]) -> None:
        model_class = self._resolve_model_class(loc)
        db_key = self._resolve_db_key(loc)
        display = self._display_name(loc)

        if value is None or value == "":
            if self.allow_null:
                return
            raise ValidationRuleException(f"[Unique] Field `{display}` is required.", loc=tuple(loc))

        current_id = await self._resolve_current_id(model_class)
        items = value if (self.each and isinstance(value, list)) else [value]

        for item in items:
            query: dict[str, Any] = {db_key: item}
            if current_id is not None:
                query[self.current_id_key] = {"$ne": current_id}

            exists = await model_class.exists(query)
            if exists:
                raise ValidationRuleException(
                    f"[Unique] Field `{display}` must be unique.",
                    loc=tuple(loc),
                )


class Unique(UniqueValidatorRule):
    """Alias for concise schema declarations."""
