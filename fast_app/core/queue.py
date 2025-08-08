import asyncio
import contextvars
import inspect
import os
from typing import Callable

from redis import Redis
from rq import Queue

from fast_app.config import REDIS_QUEUE_DB
from fast_app.application import Application

rq = Queue(
    name=os.getenv("RQ_QUEUE_NAME", "default"),
    connection=Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=REDIS_QUEUE_DB
    )
)

def queue(func, *args, **kwargs):
    q_worker = os.getenv('QUEUE_DRIVER', "sync").lower()

    if q_worker == 'sync':
        if inspect.iscoroutinefunction(func):
            asyncio.create_task(func(*args, **kwargs))
        else:
            func(*args, **kwargs)
    elif q_worker == 'rq':
        # Capture current context for both sync and async execution
        ctx = contextvars.copy_context()
        app = Application()

        if inspect.iscoroutinefunction(func):
            rq.enqueue(run_async, ctx, app, func, *args, **kwargs)
        else:
            rq.enqueue(run_sync, ctx, app, func, *args, **kwargs)


def run_async(ctx: contextvars.Context, app: Application, func: Callable, *args, **kwargs):
    """
    Transform and run async functions in the queue worker with preserved context.
    
    Ensures the application is properly configured and context is restored
    before running the function.
    """
    # Preserves the application state
    if app.is_booted():
        from fast_app.app_provider import boot
        boot(**app.get_boot_args())
    
    # Run the function within the captured context
    def run_in_context():
        return asyncio.run(func(*args, **kwargs))
    
    # Execute with the original context (preserves ContextVars like locale)
    ctx.run(run_in_context)


def run_sync(ctx: contextvars.Context, app: Application, func: Callable, *args, **kwargs):
    """
    Transform and run sync functions in the queue worker with preserved context.
    
    Ensures the application is properly configured and context is restored
    before running the function.
    """
    # Preserves the application state
    if app.is_booted():
        from fast_app.app_provider import boot
        boot(**app.get_boot_args())
    
    # Execute with the original context (preserves ContextVars like locale)
    ctx.run(func, *args, **kwargs)
