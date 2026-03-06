from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeAlias

ASC = 1
DESC = -1

IndexDirection: TypeAlias = int | str
IndexKey: TypeAlias = tuple[str, IndexDirection]


@dataclass(frozen=True, slots=True)
class Index:
    keys: list[IndexKey]
    name: str
    unique: bool = False
    sparse: bool = False
    partial_filter_expression: dict[str, Any] | None = None
    expire_after_seconds: int | None = None
    collation: dict[str, Any] | None = None
    hidden: bool = False

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Index name must be a non-empty string")

        if not self.keys:
            raise ValueError(f"Index '{self.name}' must define at least one key")

        normalised_keys: list[IndexKey] = []
        for key in self.keys:
            if not isinstance(key, tuple) or len(key) != 2:
                raise ValueError(f"Index '{self.name}' has invalid key declaration: {key!r}")

            field, direction = key
            if not isinstance(field, str) or not field:
                raise ValueError(f"Index '{self.name}' has invalid field name: {field!r}")

            if not isinstance(direction, (int, str)):
                raise ValueError(
                    f"Index '{self.name}' has invalid direction for '{field}': {direction!r}"
                )

            normalised_keys.append((field, direction))

        object.__setattr__(self, "keys", normalised_keys)

        if self.expire_after_seconds is not None and self.expire_after_seconds < 0:
            raise ValueError("expire_after_seconds must be greater than or equal to 0")

    def mongo_options(self) -> dict[str, Any]:
        options: dict[str, Any] = {"name": self.name}

        if self.unique:
            options["unique"] = True
        if self.sparse:
            options["sparse"] = True
        if self.partial_filter_expression is not None:
            options["partialFilterExpression"] = self.partial_filter_expression
        if self.expire_after_seconds is not None:
            options["expireAfterSeconds"] = self.expire_after_seconds
        if self.collation is not None:
            options["collation"] = self.collation
        if self.hidden:
            options["hidden"] = True

        return options


__all__ = ["ASC", "DESC", "Index", "IndexDirection", "IndexKey"]
