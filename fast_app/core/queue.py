import asyncio
import inspect
import os
from typing import Any, Callable


def queue(func: Callable[..., Any], *args, **kwargs) -> None:
    driver = os.getenv("QUEUE_DRIVER", "sync").lower()

    if driver == "sync":
        if inspect.iscoroutinefunction(func):
            asyncio.create_task(func(*args, **kwargs))
        else:
            func(*args, **kwargs)
        return

    if driver == "async_farm":
        # Publish to RabbitMQ jobs queue with TTL and context preservation.
        try:
            from fast_app.integrations.async_farm.publisher import enqueue_callable
        except Exception as e:
            raise ValueError("async_farm driver requires aio-pika installed") from e

        enqueue_callable(func, *args, **kwargs)
        return

    raise ValueError(f"Unsupported QUEUE_DRIVER: {driver}")