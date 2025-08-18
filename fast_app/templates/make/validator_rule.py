from typing import Any, Sequence

from fast_validation import ValidatorRule, ValidationRuleException


class NewClass(ValidatorRule):
    async def validate(self, *, value: Any, data: dict, loc: Sequence[str]) -> None:
        # Example: enforce non-empty string
        if isinstance(value, str) and value.strip() == "":
            raise ValidationRuleException("Value must not be empty", loc=list(loc))


