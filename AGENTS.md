FastApp — Agent Quick Notes

- Purpose & scope: Async, Laravel‑inspired toolkit for HTTP APIs. Core: routes, schemas, models, resources, middleware, events; optional batteries: queue, scheduler, broadcasting, notifications, storage, CLI.
- Supported env: Python 3.12+, Quart, Motor (MongoDB). Optional: Redis (cache/socketio/scheduler), RabbitMQ (`async_farm` queue).
- Runtime deps: Minimal to run API: Mongo (`MONGO_URI`), `SECRET_KEY`. Optional: Redis, RabbitMQ.
- Config: `import fast_app.boot` first. Reads `.env`/`.env.{ENV}`; key vars: `MONGO_URI`, `SECRET_KEY`, `ENV`, `DB_NAME`, `QUEUE_DRIVER`, `REDIS_*`, `RABBITMQ_URL`. See `docs/enviroment.md`.
- Project layout: `app/http_files/{routes,controllers,schemas,resources,middlewares}`, `app/models`, optional `app/app_config.py`. Entry: `app/modules/asgi/app.py`. See `docs/quick_start.md`.
- Request lifecycle: `Route → middlewares → controller → schema/validation → model → resource`. Global middlewares include exception handling, model binding, schema validation, `ResourceResponseMiddleware`.
- Autodiscovery: Enabled by `boot()`/`app_config.py`. Auto-registers observers/policies/events by naming/location. See `fast_app/boot.py`.
- Models/DB: Async ODM over Motor. CRUD helpers, relationships (`belongs_to/has_one/has_many`), dirty tracking. See `docs/models.md`.
- Validation: Pydantic-style schemas; async rules via fast-validation; helpers: `validate_request`, `validate_query`. See `docs/api.md`.
- Resources: Implement `async to_dict(self, data)`; supports nested `Resource` resolution and JSON serialization. Auto JSON via middleware.
- Routing: `Route.get/post/...`, groups, `Route.resource` for CRUD; register with `register_routes(app, routes)`. See `docs/routes.md`.
- Queue: `queue(func, ...)` with drivers `sync` (default) or `async_farm` (RabbitMQ). Context propagates. See `docs/queue.md`.
- Scheduler: `run_scheduler([{run_every_s, function}])`, distributed via Redis locks. See `docs/scheduler.md`.
- Broadcasting: Redis + Socket.IO; define `BroadcastEvent`, `Room`, `Namespace`; emit via `broadcast(event)`. See `docs/broadcasting.md`.
- Events: `dispatch(event)` maps to listeners via config/autodiscovery; listeners run via queue. `dispatch_now` for sync. See `docs/events.md`.
- Notifications: Define `Notification` + channels; `send()` enqueues per channel. Built-ins: mail, Expo, Slack. See `docs/notifications.md`.
- Auth/JWT: `fast_app.core.jwt_auth` with ACCESS/REFRESH tokens; requires `SECRET_KEY`. Policies + `AuthorizeMiddleware` for authorization.
- Storage: `Storage` with named disks; built-ins registered at boot; S3 via driver. See `docs/storage.md`.
- CLI: `fast-app init | make | publish | migrate | seed | serve | work | exec | version`. See `docs/cli.md`.

First run (local):
1) `python -m venv .venv && source .venv/bin/activate && pip install "fast-app[dev]"`
2) `fast-app init`
3) Create `.env.debug` with `ENV=debug`, `MONGO_URI=...`, `SECRET_KEY=...`
4) `fast-app serve`

Tips:
- Always import `fast_app.boot` first in every entry (ASGI, workers, CLI).
- Prefer `validate_request`/`validate_query` + `Resource` for clean controllers.
- Use `QUEUE_DRIVER=sync` for tests; switch to `async_farm` with RabbitMQ in prod.
