from typing import Any, Awaitable, Callable

from fast_app.contracts.middleware import Middleware
from fast_app.core.model_batch_cache import ModelBatchCache


class ModelBatchCacheMiddleware(Middleware):
    """Initialize the batch cache store in the request's root context.

    Child tasks spawned by ``asyncio.gather`` (e.g. in Resource resolution)
    inherit the shared store, enabling cross-task batching.  The store is
    reset at the end of the request.
    """

    phase = "pre_binding"

    async def handle(self, next_handler: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        ModelBatchCache.ensure_active()
        try:
            return await next_handler(*args, **kwargs)
        finally:
            ModelBatchCache.reset()
