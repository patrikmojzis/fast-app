## scheduler

Simple distributed scheduler using Redis locks.

### API
- **run_scheduler(jobs)**: forever loop that acquires per-job lock and enqueues job via `queue()`.

Each job must define exactly one schedule mode:
- Interval (seconds): `{ "run_every_s": int, "function": callable, "identifier": optional[str] }`
- Interval (human-readable): `{ "run_every": str, "function": callable, "identifier": optional[str] }`
- Cron: `{ "cron": str, "function": callable, "timezone": optional[str], "identifier": optional[str] }`

Notes:
- `run_every` supports `ms`, `s`, `m`, `h`, `d`, `w` units (for example `"60s"`, `"1h30m"`, `"2d"`).
- Durations below 1 second are rejected.
- Cron uses 5 fields: `minute hour day month weekday`.
- Cron timezone defaults to `UTC` if not provided.

### Example
```python
from fast_app.core.scheduler import run_scheduler
import asyncio

async def every_minute():
    ...

async def at_midnight_utc():
    ...

async def weekend_midnight_prague():
    ...

asyncio.run(run_scheduler([
  {"run_every_s": 60, "function": every_minute},
  {"run_every": "1h30m", "function": every_minute},
  {"cron": "0 0 * * *", "function": at_midnight_utc},
  {"cron": "0 0 * * sat,sun", "timezone": "Europe/Prague", "function": weekend_midnight_prague},
]))
```
