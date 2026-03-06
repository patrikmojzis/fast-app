"""
Reusable Pydantic v2 field types for common values (ObjectId, date, datetime).

Usage:

    from typing import Optional
    from pydantic import ConfigDict
    from fast_validation import Schema
    from fast_app.core.pydantic_types import ObjectIdField, DateField, DateTimeField, MongoDateField

    class MySchema(Schema):
        # Required when using bson.ObjectId as a field type
        model_config = ConfigDict(arbitrary_types_allowed=True)

        _id: Optional[ObjectIdField] = None
        birthday: DateField
        mongo_birthday: MongoDateField
        created_at: DateTimeField

These annotated types:
- Accept convenient inputs (e.g., strings) and coerce them to proper Python types
- Serialize to JSON-friendly forms (ObjectId/date/datetime -> string)
"""

from datetime import date, datetime, timezone
from typing import Annotated, Any, Optional

from bson import ObjectId
from pydantic import PlainSerializer, StringConstraints, WithJsonSchema
from pydantic.functional_validators import BeforeValidator


def _coerce_object_id(value: object) -> Optional[ObjectId]:
    if value is None or isinstance(value, ObjectId):
        return value  # type: ignore[return-value]
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    raise ValueError("Invalid ObjectId (expected 24-character hex string).")


def _coerce_date(value: object) -> date:
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
    raise ValueError("Invalid date (expected YYYY-MM-DD or ISO 8601 datetime).")


def _coerce_date_to_utc_datetime(value: object) -> datetime:
    # date → midnight UTC
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)

    # datetime → ensure UTC-aware
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    # string
    if isinstance(value, str):
        s = value.strip().replace("Z", "+00:00")

        # YYYY-MM-DD
        try:
            d = date.fromisoformat(s)
            return datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)
        except ValueError:
            pass

        # full datetime
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            pass

    raise ValueError("Invalid datetime/date (expected YYYY-MM-DD or ISO 8601)")


def _coerce_datetime(value: object) -> datetime:
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
    raise ValueError("Invalid datetime (expected ISO 8601, e.g. 2025-01-30T12:34:56Z).")


def _coerce_json(value: Any) -> Any:
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


def _coerce_int(value: object) -> int:
    # Coerce common representations to int, rejecting non-integral floats and booleans
    if isinstance(value, bool):
        raise ValueError("Invalid integer (expected whole number).")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        raise ValueError("Invalid integer (expected whole number).")
    if isinstance(value, str):
        s = "".join(value.split())  # Remove all whitespace
        try:
            return int(s)
        except (TypeError, ValueError):
            pass
    raise ValueError("Invalid integer (expected whole number).")


def _coerce_hex_color(value: object) -> str:
    if isinstance(value, str):
        color = value.strip()
        if not color:
            raise ValueError("Color must be a valid hex code (e.g. #FF5733).")
        if color.startswith("#"):
            color = color[1:]
        if len(color) not in (3, 6):
            raise ValueError("Color must be a valid hex code (e.g. #FF5733).")
        try:
            int(color, 16)
        except ValueError as exc:
            raise ValueError("Color must be a valid hex code (e.g. #FF5733).") from exc
        return f"#{color}"
    raise ValueError("Color must be a valid hex code (e.g. #FF5733).")


JSONField = Annotated[
    Any,
    BeforeValidator(_coerce_json),
]

ObjectIdField = Annotated[
    ObjectId,
    BeforeValidator(_coerce_object_id),
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
    BeforeValidator(_coerce_date),
    PlainSerializer(lambda v: v.isoformat() if v is not None else None, return_type=str, when_used="json"),
]

MongoDateField = Annotated[
    datetime,
    BeforeValidator(_coerce_date_to_utc_datetime),
    PlainSerializer(lambda v: v.isoformat() if v is not None else None, return_type=str, when_used="json"),
]

DateTimeField = Annotated[
    datetime,
    BeforeValidator(_coerce_datetime),
    PlainSerializer(lambda v: v.isoformat() if v is not None else None, return_type=str, when_used="json"),
]


IntFromStrField = Annotated[
    int,
    BeforeValidator(_coerce_int),
]

HexColorField = Annotated[
    str,
    BeforeValidator(_coerce_hex_color),
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
    "MongoDateField",
    "DateTimeField",
    "IntFromStrField",
    "HexColorField",
    "ShortStr",
]
