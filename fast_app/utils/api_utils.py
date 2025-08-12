from typing import get_origin, get_args, Union, List

from quart import request


def is_list_type(annotation: object) -> bool:
    """Return True if the annotation represents a (possibly Optional) list type."""
    origin = get_origin(annotation)
    if origin in (list, List):
        return True
    if origin is Union:
        return any(get_origin(arg) in (list, List) for arg in get_args(annotation))
    return False

def collect_list_values(param_name: str) -> list[str]:
    """Collect list-like values from query string for a given name.

    Supports both repeated keys and the common key[] style. Also accepts a
    single CSV value (e.g. "a,b,c").
    """
    # Repeated keys: ?tag=a&tag=b
    values: list[str] = request.args.getlist(param_name)
    # key[] style: ?tag[]=a&tag[]=b
    values += request.args.getlist(f"{param_name}[]")
    if not values:
        return []
    # If any value contains commas, split and flatten
    split_values: list[str] = []
    for raw in values:
        if "," in raw:
            split_values.extend([part.strip() for part in raw.split(",") if part.strip() != ""])
        else:
            split_values.append(raw)
    return split_values