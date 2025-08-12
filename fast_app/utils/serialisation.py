import re
from datetime import datetime

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


def get_exception_error_type(exception: Exception) -> str:
    return pascal_case_to_snake_case(exception.__class__.__name__.lower().replace('exception', ''))