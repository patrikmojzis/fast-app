from typing import Any, Callable, Awaitable

from quart import Response, has_request_context, jsonify

from fast_app.contracts.middleware import Middleware
from fast_app.contracts.resource import Resource
from fast_app.utils.serialisation import serialise


class ResourceResponseMiddleware(Middleware):
    """Converts returned Resource instances into HTTP responses.

    If a controller returns a Resource (instead of calling to_response()),
    this middleware will convert it by awaiting to_response().
    No-op for non-HTTP contexts and non-Resource results.
    """

    async def handle(self, next_handler: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        result = await next_handler(*args, **kwargs)
        if has_request_context():
            if isinstance(result, Response):
                return result
            if isinstance(result, Resource):
                return await result.to_response()
            elif isinstance(result, (dict, list, str, int, float)):
                return jsonify(serialise(result))
            elif result is None:
                return Response(status=204)          

        return result


