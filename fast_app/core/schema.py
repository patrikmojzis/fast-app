from __future__ import annotations

from typing import Any, List

from pydantic import BaseModel

from fast_app.contracts.validator_rule import ValidatorRule
from fast_app.exceptions.common_exceptions import ValidationRuleException
from fast_app.utils.path_resolver import resolve_path_expressions


class Schema(BaseModel):
    """
    Base schema with optional post-parse rule validation.

    Users declare rules via an inner Meta class:

        class MySchema(Schema):
            ...fields...
            class Meta:
                rules = [
                    Rule("$.field", [Exists(...)]),
                ]
    """

    class Rule:
        def __init__(self, path: str, validators: List[ValidatorRule]):
            self.path = path
            self.validators = validators

    class Meta:
        rules: List['Schema.Rule'] = []  # override in subclasses

    async def avalidate(self, *, partial: bool = False) -> None:
        data = self.model_dump(exclude_unset=partial)

        rules: List[Schema.Rule] = getattr(self.Meta, 'rules', []) or []
        if not rules:
            return

        errors: List[dict[str, Any]] = []
        for rule in rules:
            matches = resolve_path_expressions(data, rule.path)
            for loc, value in matches:
                for validator in rule.validators:
                    try:
                        await validator.validate(value=value, data=data, loc=loc)
                    except ValidationRuleException as exc:
                        if exc.errors:
                            errors.extend(exc.errors)
                        else:
                            errors.append({
                                "loc": tuple(loc) if loc else tuple(),
                                "msg": exc.message,
                                "type": exc.error_type,
                            })

        if errors:
            # Mirror pydantic-like error format and signal to caller to convert to HTTP 422
            raise ValidationRuleException(
                "schema rule validation failed",
                loc=tuple(),
                error_type="rule_error",
                errors=errors,
            )


