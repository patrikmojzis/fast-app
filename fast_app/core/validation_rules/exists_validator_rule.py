from __future__ import annotations

from typing import Any, Sequence

from bson import ObjectId

from fast_validation import ValidatorRule, ValidationRuleException


class ExistsValidatorRule(ValidatorRule):
    def __init__(
        self,
        model: type,
        *,
        db_key: str = "_id",
        allow_null: bool = False,
        is_object_id: bool = True,
        each: bool = False,
    ) -> None:
        self.model = model
        self.db_key = db_key
        self.allow_null = allow_null
        self.is_object_id = is_object_id
        self.each = each

    async def validate(self, *, value: Any, data: dict, loc: Sequence[str]) -> None:
        display = ".".join(loc) if loc else self.model.__name__.lower() + "_id"

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
            exists = await self.model.exists({self.db_key: query_value})
            if not exists:
                raise ValidationRuleException(f"[Exists] {self.model.__name__} (`{display}`) not found.", loc=tuple(loc))


