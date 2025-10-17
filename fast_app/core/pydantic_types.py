"""
Reusable Pydantic v2 field types for common values (ObjectId, date, datetime).

Usage:

    from typing import Optional
    from pydantic import ConfigDict
    from fast_validation import Schema
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
from typing import Annotated, Any, Optional

from bson import ObjectId
from pydantic import PlainSerializer, StringConstraints, WithJsonSchema
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


def _extract_json(value: Any) -> Any:
    # Accept dict/list directly, or JSON-parse strings; otherwise return as-is
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        import json

        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    return value


def _to_int(value: object) -> int:
    # Coerce common representations to int, rejecting non-integral floats and booleans
    if isinstance(value, bool):
        raise ValueError("Invalid integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        raise ValueError("Invalid integer")
    if isinstance(value, str):
        s = "".join(value.split())  # Remove all whitespace
        try:
            return int(s)
        except (TypeError, ValueError):
            pass
    raise ValueError("Invalid integer")


JSONField = Annotated[
    Any,
    BeforeValidator(_extract_json),
]

ObjectIdField = Annotated[
    ObjectId,
    BeforeValidator(_to_object_id),
    # Help pydantic infer JSON schema for serialization, and treat as string
    PlainSerializer(
        lambda v: str(v) if v is not None else None,
        return_type=str,
        when_used="json",
    ),
    # Provide JSON Schema for both validation and serialization modes
    WithJsonSchema({"type": "string", "pattern": "^[0-9a-fA-F]{24}$"}, mode="validation"),
    WithJsonSchema({"type": "string", "pattern": "^[0-9a-fA-F]{24}$"}, mode="serialization"),
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


IntFromStrField = Annotated[
    int,
    BeforeValidator(_to_int),
]

ShortStr = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=255,
    )
]


__all__ = [
    "JSONField",
    "ObjectIdField",
    "DateField",
    "DateTimeField",
    "IntFromStrField",
    "ShortStr",
]


