from __future__ import annotations

import base64
import json
from typing import Any, Iterable

SAFE_SCALARS = (str, int, float, bool, type(None))

# Default operator allowlist (safe subset for typical querying)
DEFAULT_ALLOWED_OPS = {
    "$and", "$or", "$nor",
    "$eq", "$ne",
    "$gt", "$gte", "$lt", "$lte",
    "$in", "$nin",
    "$exists", "$regex", "$size", "$all", "$elemMatch",
}


def _try_parse_json(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        # Try URL-safe base64 wrapping JSON
        try:
            # Add padding if missing
            padding = '=' * (-len(value) % 4)
            raw = base64.urlsafe_b64decode(value + padding).decode("utf-8")
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001 - keep broad but contained
            raise ValueError("Invalid filter JSON (expected JSON object or base64-encoded JSON)") from exc


def _is_allowed_field(path: str, allowed_fields: set[str] | None) -> bool:
    if not allowed_fields:
        return True
    # allow dotted subpaths if top-level is allowed
    top = path.split(".", 1)[0]
    return path in allowed_fields or top in allowed_fields


def _sanitize(
    node: Any,
    *,
    allowed_ops: set[str],
    allowed_fields: set[str] | None,
) -> Any:
    if isinstance(node, SAFE_SCALARS):
        return node
    if isinstance(node, list):
        return [
            _sanitize(item, allowed_ops=allowed_ops, allowed_fields=allowed_fields)
            for item in node
        ]
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, value in node.items():
            if isinstance(key, str) and key.startswith("$"):
                if key not in allowed_ops:
                    raise ValueError(f"Operator not allowed: {key}")
                out[key] = _sanitize(value, allowed_ops=allowed_ops, allowed_fields=allowed_fields)
            else:
                if not isinstance(key, str):
                    raise ValueError("Invalid field name in filter (expected string)")
                if not _is_allowed_field(key, allowed_fields):
                    raise ValueError(f"Field not allowed: {key}")
                out[key] = _sanitize(value, allowed_ops=allowed_ops, allowed_fields=allowed_fields)
        return out
    raise ValueError("Unsupported value in filter (expected scalar, list, or object)")


def parse_user_filter(
    *,
    raw: str | None,
    allowed_fields: Iterable[str] | None = None,
    allowed_ops: Iterable[str] | None = None,
) -> dict:
    if not raw:
        return {}
    parsed = _try_parse_json(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Filter must be a JSON object (e.g. {\"status\":\"active\"})")
    ops = set(allowed_ops or DEFAULT_ALLOWED_OPS)
    fields = set(allowed_fields) if allowed_fields else None
    return _sanitize(parsed, allowed_ops=ops, allowed_fields=fields)

