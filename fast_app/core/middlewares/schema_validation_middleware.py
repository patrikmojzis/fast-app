from __future__ import annotations

from inspect import signature
from typing import Any, Awaitable, Callable, Optional, Type

from pydantic import BaseModel
from quart import g

from fast_app.contracts.middleware import Middleware
from fast_app.core.api import validate_query, validate_request


class SchemaValidationMiddleware(Middleware):
    """Auto-validate and inject Pydantic/FastValidation schemas.

    - If the handler has a parameter annotated with a `BaseModel` (or Schema),
      this middleware will detect the request method:
        - For HTTP GET/DELETE/HEAD/OPTIONS: validate_query(schema)
        - For POST/PUT/PATCH: validate_request(schema)
      and inject the instantiated, validated schema model as the argument.

    - For PATCH, we exclude unset fields to avoid overriding with None. This is
      achieved via `partial=True` in validators, yielding instance.model_dump(exclude_unset=True)
      that `validate_*` already stores in g.validated/g.validated_query and returns.

    This middleware is a no-op if the handler does not declare a schema-typed
    parameter. It does not create any overhead in that case.
    """

    async def handle(self, next_handler: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:  # noqa: D401
        sig = signature(next_handler)

        # Find first parameter typed as a Pydantic BaseModel (or subclass)
        schema_param_name: Optional[str] = None
        schema_type: Optional[Type[BaseModel]] = None
        for name, param in sig.parameters.items():
            ann = param.annotation
            try:
                if isinstance(ann, type) and issubclass(ann, BaseModel):
                    schema_param_name = name
                    schema_type = ann  # type: ignore[assignment]
                    break
            except Exception:
                continue

        if schema_param_name is None or schema_type is None:
            return await next_handler(*args, **kwargs)

        # Determine HTTP method from globals (request context is present in HTTP middleware chain)
        from quart import request

        method = request.method.upper()
        partial = method == "PATCH"

        if method in {"GET", "DELETE", "HEAD", "OPTIONS"}:
            validated = await validate_query(schema_type, partial=partial)
        else:
            validated = await validate_request(schema_type, partial=partial)

        new_kwargs = dict(kwargs)
        new_kwargs[schema_param_name] = validated
        # Do not remove any existing kwargs; keep composability

        return await next_handler(*args, **new_kwargs)


