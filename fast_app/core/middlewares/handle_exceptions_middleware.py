from typing import Any, Callable, Awaitable

from quart import has_request_context, has_websocket_context

from fast_app.contracts.middleware import Middleware
from fast_app.core.middlewares.handle_http_exceptions_middleware import HandleHttpExceptionsMiddleware
from fast_app.core.middlewares.handle_websocket_exceptions_middleware import HandleWebsocketExceptionsMiddleware


class HandleExceptionsMiddleware(Middleware):
    """Delegates to HTTP or WebSocket exception middleware based on context."""

    def __init__(self) -> None:
        self.http_handler = HandleHttpExceptionsMiddleware()
        self.ws_handler = HandleWebsocketExceptionsMiddleware()

    async def handle(self, next_handler: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        if has_request_context():
            return await self.http_handler.handle(next_handler, *args, **kwargs)
        if has_websocket_context():
            return await self.ws_handler.handle(next_handler, *args, **kwargs)
        raise Exception("Requires request or websocket context.")
