from __future__ import annotations

from functools import lru_cache
from inspect import signature
from typing import Any, Awaitable, Callable, NamedTuple, Optional, Type, TYPE_CHECKING

from bson import ObjectId

from fast_app.contracts.middleware import Middleware
from fast_app.exceptions import UnprocessableEntityException
from fast_app.utils.model_resolver import resolve_model_annotation

if TYPE_CHECKING:
    from fast_app.contracts.model import Model as ModelBase


class _BindingTarget(NamedTuple):
    param_name: str
    model_class: Type['ModelBase']
    id_key: str
    accepts_id_key: bool


@lru_cache(maxsize=None)
def _get_binding_plan(
    next_handler: Callable[..., Awaitable[Any]],
) -> tuple[_BindingTarget, ...]:
    params = signature(next_handler).parameters
    accepted_param_names = frozenset(params)
    bindings = tuple(
        _BindingTarget(param_name, model_class, f"{param_name}_id", f"{param_name}_id" in accepted_param_names)
        for param_name, param in params.items()
        if (model_class := resolve_model_annotation(param.annotation)) is not None
    )
    return bindings


class ModelBindingMiddleware(Middleware):
    """Auto-bind models based on typed handler parameters.

    For each handler parameter typed as a subclass of `Model`, this middleware
    will attempt to resolve an instance from a corresponding `<name>_id` kwarg
    (or the same-named kwarg if it's a string id) and inject it under the
    typed parameter name. It avoids any database work when the handler does not
    request model-typed parameters.

    Rules:
    - Only binds when the handler has a parameter annotated with a `Model` subclass.
    - Looks for `<param>_id` in the incoming kwargs; if found, uses it as the id.
    - Otherwise, if `<param>` exists and is a string, uses it as the id.
    - Keeps the original id kwarg only if the handler accepts it; otherwise removes it
      to prevent unexpected keyword errors.
    """

    async def handle(self, next_handler: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:  # noqa: D401
        if not kwargs:
            return await next_handler(*args, **kwargs)

        bindings = _get_binding_plan(next_handler)
        if not bindings:
            return await next_handler(*args, **kwargs)

        # Collect binding work to perform before invoking the handler
        updated_kwargs = dict(kwargs)

        for param_name, model_class, id_key, accepts_id_key in bindings:
            # Determine id source: prefer '<param>_id', else '<param>' if str
            id_value: Optional[str] = None
            if id_key in updated_kwargs and isinstance(updated_kwargs[id_key], (str, bytes)):
                id_value = updated_kwargs[id_key].decode() if isinstance(updated_kwargs[id_key], bytes) else updated_kwargs[id_key]
            elif param_name in updated_kwargs and isinstance(updated_kwargs[param_name], (str, bytes)):
                id_value = updated_kwargs[param_name].decode() if isinstance(updated_kwargs[param_name], bytes) else updated_kwargs[param_name]

            # If no id present, skip binding for this parameter
            if id_value is None:
                continue

            # If not valid ObjectId
            if not ObjectId.is_valid(id_value):
                source_key = id_key if id_key in updated_kwargs else param_name
                message = (
                    f"Invalid ObjectId for URL parameter '{source_key}': '{id_value}'. "
                    "Model binding expects a MongoDB ObjectId from the route parameter."
                )
                raise UnprocessableEntityException(error_type="invalid_object_id", message=message)

            # Resolve model instance
            instance = await model_class.find_by_id_or_fail(id_value)

            # Inject under the typed parameter name
            updated_kwargs[param_name] = instance

            # Drop the id kwarg if the handler does not accept it
            if id_key in updated_kwargs and not accepts_id_key:
                updated_kwargs.pop(id_key, None)

        return await next_handler(*args, **updated_kwargs)
