from typing import Any, Callable, Awaitable

from quart import has_request_context

from fast_app.contracts.middleware import Middleware
from fast_app.core.middlewares.handle_http_exceptions_middleware import HandleHttpExceptionsMiddleware


class HandleExceptionsMiddleware(Middleware):
    """Delegates to exception middleware based on context."""

    def __init__(self) -> None:
        self.http_handler = HandleHttpExceptionsMiddleware()

    async def handle(self, next_handler: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        if has_request_context():
            return await self.http_handler.handle(next_handler, *args, **kwargs)
        raise Exception("HandleExceptionsMiddleware requires a Quart request context.")
