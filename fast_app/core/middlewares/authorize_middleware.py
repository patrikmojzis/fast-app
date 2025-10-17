from __future__ import annotations

from typing import Any, Awaitable, Callable, Literal, Optional, Union

from quart import g

from fast_app.contracts.middleware import Middleware
from fast_app.core.context import ContextKey
from fast_app.exceptions.http_exceptions import UnauthorisedException
from fast_app import context


class AuthorizeMiddleware(Middleware):
    """Authorize the current authorizable instance (default: "user") against a policy before executing the handler.

    Usage examples:
        - Instance ability (after ModelBindingMiddleware binds `post`):
            @middleware(AuthorizeMiddleware("update", "post"))
            async def update_post(post: Post):
                ...

        - Class ability:
            @middleware(AuthorizeMiddleware("create", Post))
            async def create_post():
                ...
    """

    def __init__(
        self,
        ability: str,
        target: Union[str, type, Callable[..., Awaitable[bool]]],
        authorizible_key: str | ContextKey = "user",
        source: Literal["request_context", "app_context"] = "request_context",
    ) -> None:
        self._ability = ability
        self._target = target

    async def handle(
        self,
        next_handler: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if self.source == "request_context":
            authorizable = g.get(self.authorizible_key)
        else:
            authorizable = context.get(self.authorizible_key)

        if not authorizable:
            raise UnauthorisedException()

        # Resolve target if it is a kwarg reference
        resolved_target: Union[type, Any]
        if isinstance(self._target, str):
            if self._target not in kwargs:
                raise ValueError(
                    f"AuthorizeMiddleware: target kwarg '{self._target}' not found in handler arguments"
                )
            resolved_target = kwargs[self._target]
        else:
            resolved_target = self._target

        await authorizable.authorize(self._ability, resolved_target)

        return await next_handler(*args, **kwargs)


