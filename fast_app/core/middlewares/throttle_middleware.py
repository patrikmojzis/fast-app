from __future__ import annotations

from typing import Any, Awaitable, Callable

from quart import g

from fast_app.contracts.middleware import Middleware
from fast_app.core.api import get_client_ip
from fast_app.core.cache import Cache, r
from fast_app.exceptions.http_exceptions import TooManyRequestsException


class ThrottleMiddleware(Middleware):
    """Simple request throttling per identity (user or IP).

    Usage per route:
        Route.get('/path', handler, middlewares=[ThrottleMiddleware(limit=60, window_seconds=60)])

    - Identity is resolved as authenticated user id (``g.user.id``) if present,
      otherwise client IP from the current request.
    - Counter is stored in cache with an expiry of ``window_seconds``.
    - When the number of requests within the window exceeds ``limit``,
      a 429 Too Many Requests is raised.
    """

    def __init__(self, *, limit: int = 60, window_seconds: int = 60, key: str | None = None) -> None:
        self.limit = int(limit)
        self.window_seconds = int(window_seconds)
        # Optional logical key to scope different throttles on same route
        self.key = key or "default"

    async def handle(self, next_handler: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:  # noqa: D401
        cache_key = await self._build_cache_key()

        # Use native Redis integer counters to avoid pickle/INCR conflicts.
        count = await r.incr(cache_key)
        if count == 1:
            await r.expire(cache_key, max(int(self.window_seconds), 1))
        if count > self.limit:
            raise TooManyRequestsException(
                message=f"Too many requests. Try again in {max(self.window_seconds, 1)}s."
            )

        return await next_handler(*args, **kwargs)

    async def _build_cache_key(self) -> str:
        identifier = getattr(g, "user", None)
        if identifier is not None:
            # Support classes with id attribute as well as simple ids
            user_id = getattr(identifier, "id", None)
            identifier_str = str(user_id) if user_id is not None else str(identifier)
        else:
            identifier_str = get_client_ip()

        return f"throttle:{self.key}:{identifier_str}"

