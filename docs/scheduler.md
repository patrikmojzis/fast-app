## scheduler

Simple distributed scheduler using Redis locks.

### API
- **run_scheduler(jobs)**: forever loop that acquires per-job lock and enqueues job via `queue()` once per interval.
Scheduler ticks are aligned to a monotonic deadline and automatically catch up after delays to avoid cumulative drift.

Job spec: `{ "run_every_s": int, "function": callable, "identifier": optional[str] }`. Identifier defaults to `module:qualname`.

### Example
```python
from fast_app.core.scheduler import run_scheduler
import asyncio

async def do_work():
    ...

asyncio.run(run_scheduler([
  {"run_every_s": 60, "function": do_work},
]))
```

