from __future__ import annotations

from typing import Any, Optional, Sequence, TYPE_CHECKING

from bson import ObjectId
from fast_validation import ValidatorRule, ValidationRuleException

from fast_app.utils.model_resolver import resolve_model_from_field, resolve_model_reference

if TYPE_CHECKING:
    from fast_app.contracts.model import Model as ModelBase


class ExistsValidatorRule(ValidatorRule):
    def __init__(
        self,
        model: type | str | None = None,
        *,
        field: Optional[str] = None,
        db_key: str = "_id",
        allow_null: bool = False,
        is_object_id: bool = True,
        each: bool = False,
    ) -> None:
        self.model = model
        self.field = field
        self.db_key = db_key
        self.allow_null = allow_null
        self.is_object_id = is_object_id
        self.each = each
        self._resolved_model: Optional[type["ModelBase"]] = None

    def _display_name(self, loc: Sequence[str]) -> str:
        if loc:
            return ".".join(str(part) for part in loc)
        if self.field:
            return self.field
        if self.model is None:
            return "id"
        if isinstance(self.model, str):
            return f"{self.model}_id"
        return f"{self.model.__name__.lower()}_id"

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
                "ExistsValidatorRule: unable to resolve model. "
                "Pass model=... or field=... to infer it."
            )

        self._resolved_model = resolve_model_from_field(field_name)
        return self._resolved_model

    async def validate(self, *, value: Any, data: dict, loc: Sequence[str]) -> None:
        model_class = self._resolve_model_class(loc)
        display = self._display_name(loc)

        if value is None or value == "":
            if self.allow_null:
                return
            raise ValidationRuleException(f"[Exists] Field `{display}` is required.", loc=tuple(loc))

        items = value if (self.each and isinstance(value, list)) else [value]

        for item in items:
            if self.is_object_id:
                if not isinstance(item, ObjectId):
                    if not isinstance(item, str) or not ObjectId.is_valid(item):
                        raise ValidationRuleException(f"[Exists] Invalid ObjectId at `{display}`.", loc=tuple(loc))
                    item = ObjectId(item)
            query_value = item
            exists = await model_class.exists({self.db_key: query_value})
            if not exists:
                raise ValidationRuleException(
                    f"[Exists] {model_class.__name__} (`{display}`) not found.",
                    loc=tuple(loc),
                )
