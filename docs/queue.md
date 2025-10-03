# Queue

FastApp's queue abstraction lets you defer work to background processes. Use it for tasks that don't need immediate execution—sending emails, processing uploads, generating reports, or triggering notifications—so your API responses stay fast.

## Drivers

The queue supports two execution modes controlled by the `QUEUE_DRIVER` environment variable:

- **sync** (default) — executes the function immediately in-process. Useful for development or small deployments where background workers aren't needed.
- **async_farm** — enqueues jobs to RabbitMQ and executes them on worker processes managed by the async farm supervisor.

```bash
export QUEUE_DRIVER=async_farm
```

## Basic usage

Call `queue(func, *args, **kwargs)` to schedule a function. Both sync and async callables are supported.

```python
from fast_app.core.queue import queue

async def send_welcome_email(user_id: str):
    user = await User.find_by_id(user_id)
    await email_service.send(user.email, "Welcome!")

# Enqueue the task
await queue(send_welcome_email, user_id="66f2d3...")
```

The function signature must be importable (defined at module level with a dotted path). Lambdas and nested functions won't work with `async_farm`.

## Timeouts

When using `async_farm`, you can specify soft and hard timeouts via special kwargs:

```python
await queue(
    process_large_report,
    report_id="abc123",
    __soft_timeout_s=300,   # warn after 5 minutes
    __hard_timeout_s=600,   # force kill after 10 minutes
)
```

- **Soft timeout** — logs a warning and cancels the asyncio task wrapper, but the underlying work may continue until the hard timeout.
- **Hard timeout** — forcibly terminates the worker process after the specified duration.

These kwargs are stripped before the function receives its arguments.

## Running workers

To process queued jobs with `async_farm`, start the supervisor:

```bash
fast-app work          # production
fast-app work --tui    # development with live dashboard
```

The supervisor spawns worker processes, scales them based on queue depth, and monitors heartbeats. See the [Async Farm](async_farm.md) documentation for configuration details.

## Context propagation

When using `async_farm`, the current request context (from `fast_app.core.context.context`) is serialized and restored inside the worker. This means queued jobs have access to the same user, locale, or other context variables that were active when the job was enqueued.

```python
from fast_app.core.context import context

context.set("user_id", user.id)
await queue(audit_action, action="login")

# Inside the worker, the job can access:
# context.get("user_id") → same user ID
```

## Requirements

`async_farm` mode requires:

- **RabbitMQ** — configure via `RABBITMQ_URL` (defaults to `amqp://guest:guest@localhost:5672/`)
- **aio-pika** — installed as part of FastApp's dependencies

For more on worker management, scaling, and diagnostics, consult the [Async Farm documentation](async_farm.md).
