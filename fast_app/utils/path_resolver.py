from __future__ import annotations

from typing import Any, List


def resolve_path_expressions(data: Any, path_expr: str) -> List[tuple[tuple[str, ...], Any]]:
    """
    Resolve a minimal JSONPath-like expression against a dict.

    Supported syntax:
      - $.field
      - $.a.b.c
      - $.list[*]
      - Combinations like $.a.list[*].b

    Returns list of (loc_tuple, value) pairs.
    Missing paths return an empty list.
    """
    if not path_expr.startswith("$"):
        raise ValueError(f"Path must start with '$': {path_expr}")

    # Tokenize by '.' while preserving [*] suffixes
    tokens: List[str] = []
    for part in path_expr.split("."):
        if part == "$":
            continue
        tokens.append(part)

    results: List[tuple[tuple[str, ...], Any]] = [(tuple(), data)]

    for token in tokens:
        next_results: List[tuple[tuple[str, ...], Any]] = []
        if token.endswith("[*]"):
            key = token[:-3]
            for loc, current in results:
                if not isinstance(current, dict) or key not in current:
                    continue
                value = current[key]
                if isinstance(value, list):
                    for idx, item in enumerate(value):
                        # For schema validation, we report the key and index
                        next_results.append((loc + (key, str(idx)), item))
                else:
                    # Not a list; skip silently to keep behavior permissive
                    continue
        else:
            key = token
            for loc, current in results:
                if isinstance(current, dict) and key in current:
                    next_results.append((loc + (key,), current[key]))
                else:
                    continue
        results = next_results

    return results


