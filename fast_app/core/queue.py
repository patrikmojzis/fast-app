import asyncio
import inspect
import logging
import os
from typing import Any, Callable


async def queue(func: Callable[..., Any], *args, **kwargs) -> None:
    driver = os.getenv("QUEUE_DRIVER", "sync").lower()

    if driver == "sync":
        logging.debug("[QUEUE] Executing function sync")
        if inspect.iscoroutinefunction(func):
            asyncio.create_task(func(*args, **kwargs))
        else:
            func(*args, **kwargs)
        return

    if driver == "async_farm":
        logging.debug("[QUEUE] Executing function with async farm")
        # Publish to RabbitMQ jobs queue with TTL and context preservation.
        try:
            from fast_app.integrations.async_farm.publisher import enqueue_callable
        except Exception as e:
            raise ValueError("async_farm driver requires aio-pika installed") from e

        await enqueue_callable(func, *args, **kwargs)
        return

    raise ValueError(f"Unsupported QUEUE_DRIVER: {driver}")