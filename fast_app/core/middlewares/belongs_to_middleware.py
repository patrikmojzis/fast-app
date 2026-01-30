from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional

from bson import ObjectId
from bson.errors import InvalidId

from fast_app.contracts.middleware import Middleware
from fast_app.exceptions.http_exceptions import NotFoundException


class BelongsToMiddleware(Middleware):
    """Ensure that a bound child model belongs to a given parent model."""

    def __init__(
        self,
        child_name: str,
        parent_name: str,
        *,
        foreign_key: Optional[str] = None,
        parent_key: str = "_id",
    ) -> None:
        self._child_name = child_name
        self._parent_name = parent_name
        self._foreign_key = foreign_key
        self._parent_key = parent_key

    async def handle(
        self,
        next_handler: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        from fast_app.contracts.model import Model as ModelBase

        child = kwargs.get(self._child_name)
        parent = kwargs.get(self._parent_name)

        if child is None:
            raise ValueError(
                f"BelongsToMiddleware: child kwarg '{self._child_name}' not found in handler arguments",
            )

        if parent is None:
            raise ValueError(
                f"BelongsToMiddleware: parent kwarg '{self._parent_name}' not found in handler arguments",
            )

        if not isinstance(child, ModelBase):
            raise ValueError(
                "BelongsToMiddleware: child value must be a bound Model instance",
            )

        if not isinstance(parent, ModelBase):
            raise ValueError(
                "BelongsToMiddleware: parent value must be a bound Model instance",
            )

        foreign_key = self._foreign_key or f"{self._parent_name}_id"

        if not hasattr(child, foreign_key):
            raise ValueError(
                f"BelongsToMiddleware: child model '{child.__class__.__name__}' has no attribute '{foreign_key}'",
            )

        if not hasattr(parent, self._parent_key):
            raise ValueError(
                f"BelongsToMiddleware: parent model '{parent.__class__.__name__}' has no attribute '{self._parent_key}'",
            )

        child_identifier = getattr(child, foreign_key)
        parent_identifier = getattr(parent, self._parent_key)

        if child_identifier is None or parent_identifier is None:
            raise NotFoundException(
                message="Related resource identifiers missing; cannot verify relationship.",
            )

        if not self._identifiers_match(child_identifier, parent_identifier):
            raise NotFoundException(
                message=f"Relationship mismatch: '{self._child_name}' does not belong to '{self._parent_name}'.",
            )

        return await next_handler(*args, **kwargs)

    @staticmethod
    def _identifiers_match(left: Any, right: Any) -> bool:
        return BelongsToMiddleware._normalise_identifier(left) == BelongsToMiddleware._normalise_identifier(right)

    @staticmethod
    def _normalise_identifier(value: Any) -> Any:
        if isinstance(value, ObjectId):
            return value

        if value is None:
            return None

        if isinstance(value, bytes):
            value = value.decode()

        if isinstance(value, str):
            try:
                return ObjectId(value)
            except (InvalidId, TypeError):
                return value

        return value

