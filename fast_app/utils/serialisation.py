import re
from datetime import datetime
from typing import Any

from bson import ObjectId


def serialise(val):
    if isinstance(val, ObjectId):
        return str(val)
    if isinstance(val, datetime):
        return val.isoformat()
    # insert serialisation here <start>

    # insert serialisation here <end>
    elif isinstance(val, list):
        return [serialise(item) for item in val]
    elif isinstance(val, dict):
        return {key: serialise(value) for key, value in val.items()}

    return val



def pascal_case_to_snake_case(pascal: type | str) -> str:
    """
    Convert a class name (CamelCase or PascalCase) to snake_case.

    Args:
        pascal: The class or class name as a string.

    Returns:
        str: The snake_case version of the class name.
    """
    if not isinstance(pascal, str):
        pascal = pascal.__name__
    # Insert underscores before capital letters, except at the start
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', pascal)
    snake = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    return snake


def snake_case_to_pascal_case(snake: str) -> str:
    """
    Convert snake_case to PascalCase.

    Args:
        snake: The snake_case string.

    Returns:
        str: The PascalCase version of the string.
    """
    components = snake.split('_')
    return ''.join(word.capitalize() for word in components)


def is_snake_case(name: str) -> bool:
    """
    Basic check whether a string looks like snake_case.

    Accepts lowercase letters and digits separated by single underscores.
    """
    return re.fullmatch(r"[a-z]+(?:_[a-z0-9]+)*", name) is not None


def is_pascal_case(name: str) -> bool:
    """
    Basic check whether a string looks like PascalCase.

    Accepts sequences starting with an uppercase letter and then alphanumerics.
    """
    return re.fullmatch(r"[A-Z][A-Za-z0-9]*", name) is not None


def get_exception_error_type(exception: Exception) -> str:
    return pascal_case_to_snake_case(exception.__class__.__name__.lower().replace('exception', ''))


def remove_suffix(text: str, suffix: str) -> str:
    """
    Remove an exact suffix from the given text if present.

    Unlike str.rstrip, this removes only the provided suffix once,
    not any combination of its characters.
    """
    if text.endswith(suffix):
        return text[: -len(suffix)]
    return text


def safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        iv = int(value)
    except Exception:
        return default
    if iv < minimum:
        return minimum
    if iv > maximum:
        return maximum
    return iv