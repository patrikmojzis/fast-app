from typing import Any, Awaitable, Callable

from fast_app import Middleware


class NewClass(Middleware):
    async def handle(self, next_handler: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        return await next_handler(*args, **kwargs)


