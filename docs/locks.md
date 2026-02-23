# Locks

Use Redis locks when only one instance of a task should run at a time (pollers, cron jobs, sync loops).

## API

- `redis_lock(key, ttl_s, redis_client=None, redis_url=None, decode_responses=True)`
- `RedisDistributedLock`

Lock acquisition uses Redis `SET key token NX EX ttl` and release is token-safe with Lua, so one worker does not release another worker's lock.

## Redis URL resolution

If you do not pass `redis_url`, FastApp resolves in this order:

1. `REDIS_LOCK_URL`
2. `REDIS_SCHEDULER_URL`
3. `REDIS_CACHE_URL`

If none are set, `redis_lock(...)` raises a `RuntimeError` requiring explicit configuration.

If you pass `redis_client`, that client is used directly.

## Basic example

```python
from fast_app.core import redis_lock

async def run_job():
    async with redis_lock("my:job:lock", ttl_s=60) as lock:
        if not lock.acquired:
            return {"status": "skipped", "reason": "locked"}

        # run work only when lock is held
        return {"status": "ok"}
```

## Mail poller example

```python
from fast_app.core import redis_lock

_LOCK_KEY = "mail_poller:bank_email:lock"

async def run_mail_poller(config):
    async with redis_lock(_LOCK_KEY, ttl_s=config.lock_ttl_sec) as lock:
        if not lock.acquired:
            logger.info("Skipping mail poller run: another instance already holds lock.")
            return {"status": "skipped", "reason": "locked"}

        stats = await _run_poller(config)
        logger.info("Mail poller finished: %s", stats)
        return {"status": "ok", **stats}
```

## Reusing an existing Redis connection

```python
from redis import asyncio as aioredis
from fast_app.core import redis_lock

redis_client = aioredis.Redis.from_url("redis://localhost:6379/11", decode_responses=True)

async with redis_lock("my:job:lock", ttl_s=30, redis_client=redis_client) as lock:
    if lock.acquired:
        await do_work()
```
