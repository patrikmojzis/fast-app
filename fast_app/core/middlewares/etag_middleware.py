import hashlib
import json
from typing import Any, Callable, Awaitable

from quart import request, Response

from fast_app.contracts.middleware import Middleware


class EtagMiddleware(Middleware):
    """Middleware for handling ETags to enable HTTP caching"""
    
    async def handle(self, next_handler: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        # Call the original function
        response = await next_handler(*args, **kwargs)

        if response:
            res_string = json.dumps(await response.get_json())

            # Generate the ETag
            etag_value = hashlib.sha1(res_string.encode()).hexdigest()

            # Check if the ETag matches the one in the If-None-Match header
            if request.headers.get('If-None-Match') == etag_value:
                return Response(status=304)  # Not Modified

            # Add the ETag to the response headers
            response.headers['ETag'] = etag_value

        return response


