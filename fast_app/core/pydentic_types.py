"""
Reusable Pydantic v2 field types for common values (ObjectId, date, datetime).

Usage:

    from typing import Optional
    from pydantic import ConfigDict
    from fast_app.core.schema import Schema
    from fast_app.core.pydentic_types import ObjectIdField, DateField, DateTimeField

    class MySchema(Schema):
        # Required when using bson.ObjectId as a field type
        model_config = ConfigDict(arbitrary_types_allowed=True)

        _id: Optional[ObjectIdField] = None
        birthday: DateField
        created_at: DateTimeField

These annotated types:
- Accept convenient inputs (e.g., strings) and coerce them to proper Python types
- Serialize to JSON-friendly forms (ObjectId/date/datetime -> string)
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Annotated, Optional

from bson import ObjectId
from pydantic import PlainSerializer
from pydantic.functional_validators import BeforeValidator


def _to_object_id(value: object) -> Optional[ObjectId]:
    if value is None or isinstance(value, ObjectId):
        return value  # type: ignore[return-value]
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    raise ValueError("Invalid ObjectId")


def _to_date(value: object) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        s = value.strip()
        try:
            return date.fromisoformat(s)
        except ValueError:
            # Fallback: allow full datetime strings by converting to date
            if "T" in s or " " in s:
                s_norm = s.replace("Z", "+00:00")
                try:
                    return datetime.fromisoformat(s_norm).date()
                except ValueError:
                    pass
    raise ValueError("Invalid date")


def _to_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        s = value.strip()
        # Support trailing 'Z' (UTC) which fromisoformat doesn't parse directly
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            pass
    raise ValueError("Invalid datetime")


ObjectIdField = Annotated[
    ObjectId,
    BeforeValidator(_to_object_id),
    PlainSerializer(lambda v: str(v) if v is not None else None),
]

DateField = Annotated[
    date,
    BeforeValidator(_to_date),
    PlainSerializer(lambda v: v.isoformat() if v is not None else None),
]

DateTimeField = Annotated[
    datetime,
    BeforeValidator(_to_datetime),
    PlainSerializer(lambda v: v.isoformat() if v is not None else None),
]


__all__ = [
    "ObjectIdField",
    "DateField",
    "DateTimeField",
]


