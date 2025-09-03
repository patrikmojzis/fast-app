# FastApp

FastApp is a pragmatic, Laravel‑flavoured toolkit for building backend APIs with Python.
It composes Quart (HTTP), Pydantic (validation), and Motor (Mongo) so you can ship
features fast without wiring the same pieces every time.

## Quick start

1) Create and activate a virtualenv

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
```

2) Install FastApp

```bash
pip install "fast-app[dev]"
```

3) Scaffold a new project

```bash
fast-app init
```

4) Run a module

```bash
fast-app run api        # runs: python -m app.modules.asgi
# or
fast-app run scheduler  # runs: python -m app.modules.scheduler
```

## CLI overview

FastApp ships with a small CLI. Run `fast-app -h` to see commands.

- init: Generate a minimal project from templates
- make: Create files from templates (see below)
- publish: Copy optional feature modules into your app
- migrate / seed: Database scaffolding hooks (optional)
- run: Debug helper to run `app.modules.<module>` via `python -m`
- version: Print version

### fast-app make

Generate common building blocks from templates. Usage:

```bash
fast-app make <type> <Name>
```

Common types (see `fast_app/cli/make_command.py` for the full list):

- event, broadcast_event, websocket_event
- listener
- model
- notification, notification_channel
- observer, policy
- resource, schema, middleware, validator_rule
- factory, seeder, migration
- storage_driver

Examples:

```bash
fast-app make model User
fast-app make resource UserResource
fast-app make schema UserSchema
fast-app make middleware AuthMiddleware
fast-app make observer UserObserver
```

The generator creates missing parent directories automatically.

### fast-app publish

Copy optional feature modules into your project:

```bash
fast-app publish auth   # copies auth controllers, middleware, models, jobs
fast-app publish ws     # copies websocket controller
```
If you pass an unknown package, the CLI prints the list of available ones.

## Hello API in 60 seconds

```python
from quart import Quart, jsonify, g
from fast_app import Route
from fast_validation import Schema
from fast_app.core.api import validate_request
from fast_app.utils.routing_utils import register_routes

class ItemSchema(Schema):
    name: str

async def create_item():
    await validate_request(ItemSchema)
    return jsonify({"ok": True, "data": g.validated})

app = Quart(__name__)
routes = [
    Route.get("/ping", lambda: "pong"),
    Route.post("/items", create_item),
]
register_routes(app, routes)
```

## How things connect (contracts)

FastApp’s core abstractions live in `fast_app/contracts`. They interoperate like this:

- Route: Declarative HTTP route definition that points to a callable and optional middlewares
- Middleware: Request middleware with an async `handle(next_handler, ...)`
- Schema: Pydantic model describing and validating request data
- Resource: Transforms domain objects to serializable responses
- Model: Async ODM‑style model (Mongo/Motor) with CRUD helpers and hooks
- Policy: Authorization rules for a model/action
- Observer: Model lifecycle hooks (created/updated/deleted)
- Event / EventListener: App events and their listeners
- BroadcastEvent / BroadcastChannel: Realtime events via broadcasting layer
- Notification / NotificationChannel: Pluggable notification delivery
- ValidatorRule: Custom validation rules for request/query validation
- WebsocketEvent: Typed websocket events (if you enable ws)
- StorageDriver: Pluggable storage backends (e.g., disk, S3)

Typical request flow: Route → Middlewares → Controller/Handler → Schema validation → Model → Resource.

Ultra‑short examples:

Route and Middleware

```python
from fast_app import Route, Middleware

class SaveSomething(Middleware):
    async def handle(self, next_handler, *args, **kwargs):
        # ... pre
        res = await next_handler(*args, **kwargs)
        # ... post
        return res

routes = [
    Route.get("/ping", lambda: "pong", middlewares=[SaveSomething]),
]
```

Schema validation in a handler

```python
from quart import jsonify, g
from pydantic import BaseModel
from fast_app import validate_request, Schema

class ItemSchema(Schema):
    name: str

async def create_item():
    await validate_request(ItemSchema)
    return jsonify({"ok": True, "data": g.validated})
```

Model with hooks and policy/observer wiring (see autodiscovery in docs below)

```python
from fast_app import Model

class Item(Model):
    name: str
```

Events

```python
from fast_app import Event, EventListener

class UserRegistered(Event):
    user_id: str

class SendWelcomeEmail(EventListener):
    async def handle(self, event: UserRegistered):
        ...
```

## Core modules (fast_app/core)

The `core` package provides pragmatic building blocks you can use directly.

### simple_controller

Lightweight helpers for structuring HTTP handlers without heavy controllers.

### events

Event dispatch and convenient helpers. Pair with contracts `Event`/`EventListener`.

### localization

Tiny translation layer with graceful fallbacks.

```python
from fast_app.core.localization import __, set_locale, set_locale_path

set_locale("en")
__("messages.greeting", {"name": "Alice"}, default="Hello {name}")
```

Defaults use `./lang/<locale>.json`. Override at runtime with `set_locale_path(path)`.

### storage

Minimal storage facade with pluggable drivers. Two disks are available by default:

- local: `<cwd>/storage/local`
- public: `<cwd>/storage/public`

```python
from fast_app.core.storage import Storage

await Storage.put("uploads/file.txt", b"data")
exists = await Storage.exists("uploads/file.txt")
content = await Storage.get("uploads/file.txt")
resp = await Storage.download("uploads/file.txt", disk="local", inline=False)
```

You can register custom drivers and configure disks programmatically:

```python
from fast_app.core.storage import Storage
from fast_app.contracts.storage_driver import StorageDriver

class MemoryDriver(StorageDriver):
    ...

Storage.register_driver("memory", MemoryDriver)
Storage.configure({"mem": {"driver": "memory"}}, default_disk="mem")
```

### queue

Simple queue wrapper with two modes:

- sync (default): execute immediately in‑process
- rq: enqueue for RQ workers (set `QUEUE_DRIVER=rq`)

```python
from fast_app.core.queue import queue

def do_work():
    ...

queue(do_work)
```

### scheduler

Minimal scheduler using Redis for distributed locks.

```python
from fast_app.core.scheduler import run_scheduler

asyncio.run(run_scheduler([
    {"run_every_s": 60, "function": do_work},   # pass function reference, no parentheses
]))
```

### broadcasting

Helpers for broadcast channels and events. Pair with contracts `BroadcastEvent`/`BroadcastChannel`.

## Environment & Docker

Minimal environment to get started locally:

- MongoDB (for `Model`): set `MONGO_URL` (see your project’s settings)
- Redis (for queue/scheduler): `REDIS_HOST`, `REDIS_PORT`
- Queue mode: `QUEUE_DRIVER=sync` (default) or `QUEUE_DRIVER=rq`

Run via Docker in a generated project:

```bash
docker-compose up -d
```

The template maps `./storage/local` and `./storage/public` into the container and exposes the API port.

## Testing

Run all tests:

```bash
pytest
```

The template includes a `tests/conftest.py` starter.

## Boot process and autodiscovery

Call `boot()` at application startup to configure environment, logging, models and events.

```python
from fast_app.app_provider import boot

boot(
    autodiscovery=True,               # discover models/observers/policies and events
    events=None,                      # or pass {Event: [Listener, ...]}
    env_file_name=None,               # load .env-like file if provided
    storage_disks=None,               # programmatic Storage.configure
    storage_default_disk=None,
    storage_custom_drivers=None,      # {"gcs": GCSDriver}
)
```

What `boot()` does:
- Loads environment (when applicable) and sets up logging
- Autodiscovers models, and for each model tries to attach matching Observer/Policy by convention
- Configures the event system via provided `events` mapping or by discovering `app.event_provider.events`
- Registers built-in and custom storage drivers; optionally applies disk configuration
- Persists boot args in the Application singleton so queue workers can re‑boot with the same settings

Autodiscovery conventions (see `fast_app/utils/autodiscovery/model_autodiscovery.py`):
- Model `app/models/user.py` → class `User`
- Observer file `app/observers/user_observer.py` → class `UserObserver`
- Policy file `app/policies/user_policy.py` → class `UserPolicy`

If folders or files don’t exist, they’re skipped gracefully.

### Model decorators

Helpers in `fast_app/decorators/model_decorators.py` you can use explicitly or let autodiscovery wire for you:

- `@register_observer(ObserverClass)` — attaches an observer instance to a model
- `@register_policy(PolicyClass)` — sets `model.policy`
- `@register_search_relation(field, model, search_fields)` — adds cross‑model search relation metadata
- `@authorizable` — mixin that adds `Authorizable` capabilities to a model
- `@notifiable` — mixin that adds notification routing helpers

You can apply these manually, or rely on autodiscovery naming conventions to attach observers/policies automatically during `boot()`.

## Integrations (fast_app/integrations)

Optional batteries you can opt into:

- auth: helpers for Apple/Google auth
- middlewares: e.g. rate limiting
- notification_channels: mail, telegram, expo
- storage_drivers: e.g. S3 via boto3
- log_watcher: ship log errors to Slack/Telegram

## Project templates and publishable modules

- `templates/project_structure`: minimal runnable skeleton
- `templates/publish`: optional feature modules

Use `fast-app publish <module>` to copy selected features into your app.

## License

MIT
