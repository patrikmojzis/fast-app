from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence


class ValidatorRule(ABC):
    """
    Contract for post-parse validation rules used by `core.Schema`.

    Implementations should raise `ValidationRuleException` on failure.
    """

    @abstractmethod
    async def validate(self, *, value: Any, data: dict, loc: Sequence[str]) -> None:
        """
        Validate a value within the context of the entire payload.

        Args:
            value: The value at the resolved location.
            data: The full parsed payload as a dict (respecting partial updates when applicable).
            loc: Path components from the schema root to the value.

        Raises:
            ValidationRuleException: If the validation fails.
        """
        raise NotImplementedError


