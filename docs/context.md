## Context

Central, typed runtime context built on Python ContextVars.

- Per-request/task values that are easy to set/get anywhere.
- Optional strong typing via `ContextKey[T]` returned by `define_key`.
- Safe cross-process propagation via a picklable snapshot (used by the queue worker automatically).

### Quick start

```python
from fast_app import context

# Use plain strings (no typing)
context.set("request_id", "req-42")
rid = context.get("request_id")

# Or define typed keys
from fast_app import define_key
UserId = define_key[int]("user_id", require_picklable=True)

context.set(UserId, 123)
uid: int | None = context.get(UserId)
```

### Defining keys vs. strings

- Strings work fine for small apps: `context.set("tenant", "local")`.
- `define_key[T](name, default=None, require_picklable=False)` is recommended for larger apps/libraries:
  - Strong typing on get/set
  - Per-key defaults
  - `require_picklable=True` to enforce cross-process propagation compatibility

### Picklability and propagation

Context values are propagated to worker processes by sending a pickled snapshot.

- Non-picklable values:
  - Normal keys: setting a non-picklable value emits a RuntimeWarning once per key; the value is omitted from snapshots.
  - `require_picklable=True` keys: setting a non-picklable value raises `TypeError` immediately.

```python
Socket = define_key("socket")  # normal key
context.set(Socket, object())   # warns once; won't propagate to workers

Strict = define_key("trace_id", require_picklable=True)
context.set(Strict, object())   # raises TypeError
```

### Snapshot and install

You usually don’t need this directly because the queue publisher/worker handle it for you. If you implement your own transport, use:

```python
from fast_app import context

snap = context.snapshot()  # picklable-only dict
# ... send snap to another process ...
context.install(snap)      # restore values in the target process
```

### Queue integration

When using the `async_farm` queue driver:

- The publisher includes `ctx_snapshot` (picklable-only) and app boot args in the job payload.
- The worker installs the snapshot and boots the app before running your callable.
- You don’t need to write any extra code; values you put in the context are available inside the worker.

```python
from fast_app import define_key, context
from fast_app.core.queue import queue

CorrelationId = define_key[str]("corr_id", require_picklable=True)
context.set(CorrelationId, "abc-123")

def do_work():
    from fast_app import context
    assert context.get("corr_id") == "abc-123"

await queue(do_work)
```

### API surface

- `define_key[T](name, default=None, require_picklable=False) -> ContextKey[T]`
- `context.set(key_or_name, value) -> None`
- `context.get(key_or_name, default=None)`
- `context.clear(*names) -> None` (no names = clear known keys back to defaults)
- `context.snapshot(picklable_only=True, include_defaults=True) -> dict[str, Any]`
- `context.install(mapping: dict[str, Any]) -> None`


