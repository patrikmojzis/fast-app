from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional, Union

from quart import g

from fast_app.contracts.middleware import Middleware
from fast_app.exceptions.http_exceptions import UnauthorisedException


class AuthorizeMiddleware(Middleware):
    """Authorize the current user against a policy before executing the handler.

    Usage examples:
        - Instance ability (after ModelBindingMiddleware binds `post`):
            @middleware(AuthorizeMiddleware("post", "update"))
            async def update_post(post: Post):
                ...

        - Class ability:
            @middleware(AuthorizeMiddleware(Post, "create"))
            async def create_post():
                ...

        - Custom policy callable (no ability string):
            @middleware(AuthorizeMiddleware(lambda user: user.is_admin()))
            async def admin_only():
                ...
    """

    def __init__(
        self,
        target: Union[str, type, Callable[..., Awaitable[bool]]],
        ability: Optional[str] = None,
    ) -> None:
        self._target = target
        self._ability = ability

    async def handle(
        self,
        next_handler: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        user = g.get("user")
        if not user:
            raise UnauthorisedException()

        # Resolve target if it is a kwarg reference
        resolved_target: Union[type, Callable[..., Awaitable[bool]], Any]
        if isinstance(self._target, str):
            if self._target not in kwargs:
                raise ValueError(
                    f"AuthorizeMiddleware: target kwarg '{self._target}' not found in handler arguments"
                )
            resolved_target = kwargs[self._target]
        else:
            resolved_target = self._target

        await user.authorize(resolved_target, self._ability)

        return await next_handler(*args, **kwargs)


