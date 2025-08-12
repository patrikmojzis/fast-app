import os
from typing import Any, Callable, Awaitable

from quart import websocket

from fast_app.contracts.middleware import Middleware
from fast_app.exceptions.common_exceptions import AppException
from fast_app.exceptions.http_exceptions import HttpException


class HandleWebsocketExceptionsMiddleware(Middleware):
    """Middleware for handling exceptions for WebSocket connections."""

    async def handle(self, next_handler: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        try:
            return await next_handler(*args, **kwargs)
        except HttpException as e:
            # Map HTTP status to a close code; use 4000-4999 app codes. Base 4400 for client errors, 4500 for server.
            status = e.status_code
            base = 4500 if status >= 500 else 4400
            code = base + (status % 100)
            reason = e.error_type or "error"
            # Close the WebSocket with code and reason
            await websocket.close(code=code, reason=reason)
            return None
        except AppException as e:
            if os.getenv("ENV") == "debug":
                raise e
            # If AppException carries an HTTP status, convert similarly
            status = e.http_status_code or 500
            base = 4500 if status >= 500 else 4400
            code = base + (status % 100)
            reason = e.error_type
            await websocket.close(code=code, reason=reason)
            return None
        except Exception as e:
            if os.getenv("ENV") == "debug":
                raise e
            await websocket.close(code=4500, reason="server_error")
            return None
