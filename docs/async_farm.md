# Async Farm Workers

The async farm handles background job execution. Operators launch it with `fast-app work` in production, or with `fast-app work --tui` / `fast-app work --verbose` during development to get live diagnostics.

## System Overview

Async farm is a RabbitMQ-backed worker pool with three core components:

- **Supervisor** (`fast_app.integrations.async_farm.supervisor.AsyncFarmSupervisor`) — manages queue connections, spawns worker processes, and scales the pool.
- **Worker** (`fast_app.integrations.async_farm.worker.AsyncFarmWorker`) — consumes jobs from `async_farm.jobs`, executes callables, and streams status back.
- **Publisher API** (`fast_app.integrations.async_farm.publisher.AsyncFarmPublisher`) — enqueues jobs by serialising the target callable plus arguments.

Internally, job messages carry the dotted import path of the callable (`func_path`), positional/keyword arguments, optional request context, and soft/hard timeout headers. The worker dynamically imports the callable, restores context, and executes it (async or sync via `asyncio.to_thread`). stdout/stderr/log output is captured and sent back to the supervisor.

### RabbitMQ contracts

| Purpose | Default | Override via |
| --- | --- | --- |
| Broker URL | `amqp://guest:guest@localhost:5672/` | `RABBITMQ_URL` |
| Jobs queue | `async_farm.jobs` | `ASYNC_FARM_JOBS_QUEUE` |
| Supervisor → Worker exchange (fanout) | `async_farm.supervisor` | `ASYNC_FARM_CONTROL_EXCHANGE` |
| Worker → Supervisor exchange (direct) | `async_farm.worker` | `ASYNC_FARM_WORKER_EXCHANGE` |

Workers declare exclusive control queues bound to the fanout exchange so they can receive shutdown or snapshot requests. Supervisors consume a dedicated queue for heartbeat and task events.

## Running the Supervisor

The CLI wrapper instantiates `AsyncFarmSupervisor`, boots the FastApp container, and enters several async loops:

- `spawn_worker()` — starts new worker processes (forked via `multiprocessing.Process`).
- `heartbeat_loop()` — periodically broadcasts heartbeats to workers, ensuring they stay connected.
- `scaling_loop()` — inspects queue depth vs available capacity and scales worker count up/down within configured bounds.
- `keep_alive_loop()` — handles graceful shutdown, sending `shutdown` commands and joining worker processes with a grace period.
- `monitor_workers_heartbeat_loop()` — watches for stale heartbeats and terminates hung workers.

### Scaling heuristics

- Maintain at least `MIN_WORKERS` live processes (default 1).
- Cap the pool at `MAX_WORKERS` (default 10) to avoid runaway costs.
- Check queue length every `SCALE_CHECK_INTERVAL_S` seconds (default 1).
- Scale up in batches of `SCALE_UP_BATCH_SIZE` (default 2) when backlog exceeds aggregate capacity (`prefetch_per_worker × alive workers`).
- Scale down by terminating idle workers in batches of `SCALE_DOWN_BATCH_SIZE` (default 1) when load is light.

All values hydrate from environment variables at supervisor start. Tweaking them lets you optimise for latency or resource usage.

### Shutdown lifecycle

1. Request shutdown (signal handler or CLI exit).
2. Publish `shutdown` control message with a grace period (`WORKER_SHUTDOWN_GRACE_S`, default 15s).
3. Wait for worker processes to exit normally (`await_processes_death`).
4. Terminate remaining workers, then force-kill if necessary.
5. Close AMQP channels cleanly.

Workers reciprocate by cancelling their job consumers, draining in-flight tasks (bounded by the largest soft timeout), and recording completion snapshots.

## Worker Execution Model

Each worker keeps a bounded number of concurrent tasks (`PREFETCH_PER_WORKER`, default 10). For every message:

1. Wrap it in a `Task` (loads args, deadlines, context snapshot).
2. Register lifecycle callbacks for success/failure/timeouts.
3. Execute the callable (async natively or offloaded to a thread).
4. Capture stdout/stderr/logging and attach to the task snapshot.
5. Ack the message once callbacks finish.

Timeout handling:

- **Soft timeout** — marks the task as `soft_timeout`, cancels the asyncio wrapper, and notifies the supervisor, but lets the underlying work finish until the hard timeout.
- **Hard timeout** — publishes an event, ack’s the job, records the logs, and requests worker shutdown (followed by a forced exit after a 2-minute safety window).

### Supervisor watchdog

Workers track the last heartbeat from the supervisor. If it stalls longer than `7 × HEARTBEAT_INTERVAL_S`, the worker self-terminates to avoid orphaned consumers.

## Publishing Jobs

Use `AsyncFarmPublisher` (or the convenience helpers in your application) to enqueue work:

```python
publisher = AsyncFarmPublisher()
await publisher.publish(
    func_path="app.jobs.send_welcome_email",
    args=(user_id,),
    kwargs={"urgent": True},
    context_snapshot=context.snapshot(),
    soft_timeout_s=10,
    hard_timeout_s=60,
)
```

Jobs are pickled, optionally compressed, and durable. Consumers must stay compatible with the message schema; deploy new workers before enqueuing messages that rely on new code paths.

## Operational Tips

- **Monitoring** — Run `fast-app work --tui` to launch the textual dashboard (`SupervisorTUI`). It displays live worker status, task logs, and lets you request snapshots.
- **Logging** — `--verbose` keeps supervisor prints enabled. In production, rely on structured logging forwarded from workers.
- **Graceful deploys** — set `WORKER_SHUTDOWN_GRACE_S` to cover your longest soft timeout. Rolling restarts ensure no job is dropped mid-flight.
- **Backpressure** — tune `PREFETCH_PER_WORKER` to balance throughput vs fairness. High values increase parallelism but can starve slow tasks.
- **Isolation** — each worker process bootstraps FastApp (`fast_app.boot`) before executing tasks, so application singletons and bindings are fresh per process.
- **Failure recovery** — periodic heartbeats and supervisor watchdogs terminate zombie workers. RabbitMQ redelivers unacked messages when a worker shuts down.

## Environment Configuration Summary

```
MIN_WORKERS=1
MAX_WORKERS=10
PREFETCH_PER_WORKER=10
SCALE_UP_BATCH_SIZE=2
SCALE_DOWN_BATCH_SIZE=1
SCALE_CHECK_INTERVAL_S=1.0
WORKER_SHUTDOWN_GRACE_S=15
HEARTBEAT_INTERVAL_S=1
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
ASYNC_FARM_JOBS_QUEUE=async_farm.jobs
ASYNC_FARM_CONTROL_EXCHANGE=async_farm.supervisor
ASYNC_FARM_WORKER_EXCHANGE=async_farm.worker
TASK_HISTORY_MAX=300
```

Values may be overridden per deployment. The CLI reads them at process start, so restart the supervisor after changing config.


