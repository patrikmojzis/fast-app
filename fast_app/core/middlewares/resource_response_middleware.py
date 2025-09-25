from typing import Any, Callable, Awaitable

from quart import has_request_context

from fast_app.contracts.middleware import Middleware
from fast_app.contracts.resource import Resource


class ResourceResponseMiddleware(Middleware):
    """Converts returned Resource instances into HTTP responses.

    If a controller returns a Resource (instead of calling to_response()),
    this middleware will convert it by awaiting to_response().
    No-op for non-HTTP contexts and non-Resource results.
    """

    async def handle(self, next_handler: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        result = await next_handler(*args, **kwargs)
        if has_request_context() and isinstance(result, Resource):
            return await result.to_response()
        return result


