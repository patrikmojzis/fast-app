## Environment configuration (.env)

This project reads configuration from environment variables. For local development, use `.env.debug`. For production or generic usage, use `.env` or your platform's environment manager. Docker uses `.env.docker` with `docker-compose.yml`.

### How env files are loaded
- Local dev: `ENV=debug` causes the loader to try `.env.debug` first, then `.env` (`fast_app/utils/env_utils.configure_env`).
- Non‑debug or explicit file: you can pass an explicit file to the loader; otherwise rely on real environment variables.
- Debug mode effects: extra console logging and more verbose HTTP error output.

Minimal required to run the app (without Docker):
```env
ENV=debug
MONGO_URI=mongodb://localhost:27017
SECRET_KEY=change-me
```

Optionally set:
```env
DB_NAME=fast-app         # defaults to "db"
LOG_LEVEL=DEBUG          # defaults to INFO
```

### Variables by area

#### Application and logging
- `ENV` (debug|test|prod): controls debug behaviors (console logging, verbose errors). Default: `debug` in loader logic.
- `LOG_LEVEL` (CRITICAL|ERROR|WARNING|INFO|DEBUG|NOTSET): root logger level. Default: `INFO`.
- Localization:
  - `LOCALE_DEFAULT` (default `en`)
  - `LOCALE_FALLBACK` (default `en`)
  - `LOCALE_PATH` (default `<project>/lang`)

#### Database (MongoDB)
- `MONGO_URI` (required): Mongo connection string. Used in `fast_app/database/mongo.py`.
- `DB_NAME` (optional): DB name for normal runs. Default: `db`.
- Testing support:
  - `TEST_ENV` (flag): when set, test DB is used.
  - `TEST_DB_NAME` (optional): test DB name. Default: `test_db`.

#### JWT/Auth
- `SECRET_KEY` (required): JWT signing key. Enforced by runtime checks.
- `AUTH_JWT_ALGORITHM` (optional): Default `HS256`.
- `ACCESS_TOKEN_LIFETIME` (seconds, optional): Default `900` (15 min).
- `REFRESH_TOKEN_LIFETIME` (seconds, optional): Default `604800` (7 days).

#### Redis (host/port shared)
- `REDIS_CACHE_URL` (optional): Default `redis://localhost:6379/15`.
- `REDIS_SOCKETIO_URL` (optional): Default `redis://localhost:6379/14`.
- `REDIS_DATABASE_CACHE_URL` (optional): Default `redis://localhost:6379/13`.
- `REDIS_SCHEDULER_URL` (optional): Default `redis://localhost:6379/12`.
- `REDIS_LOCK_URL` (optional): Dedicated distributed lock Redis URL. If not set, lock APIs fall back to `REDIS_SCHEDULER_URL`, then `REDIS_CACHE_URL`. If none are set, lock APIs raise a runtime configuration error.

#### Queue
- `QUEUE_DRIVER` (optional): `sync` or `async_farm`. Default: `sync`.
- `RABBITMQ_URL` (optional): RabbitMQ connection for async_farm. Default: `amqp://guest:guest@localhost:5672/`.
- `ASYNC_FARM_JOBS_QUEUE` (optional): Job queue name. Default: `async_farm.jobs`.
- `SOFT_TIMEOUT_S` (optional): Default soft timeout for queued jobs.
- `HARD_TIMEOUT_S` (optional): Default hard timeout for queued jobs.

#### Email notifications
- `MAIL_DRIVER` (optional): `log` (default), `smtp`, or `smtp2go`.
- If `smtp`:
  - `MAIL_SERVER`
  - `MAIL_PORT`
  - `MAIL_LOGIN`
  - `MAIL_PASSWORD`
  - `MAIL_FROM`
- If `smtp2go`:
  - `MAIL_FROM`
  - `SMTP2GO_API_KEY`

#### Log watcher integrations
- Slack: `SEND_LOG_ERRORS_SLACK_WEBHOOK_URL` (optional). Includes current `ENV` in messages.
- Telegram: `SEND_LOG_ERRORS_TELEGRAM_BOT_TOKEN`, `SEND_LOG_ERRORS_TELEGRAM_CHAT_ID` (optional).

#### Auth integrations
- Google: `GOOGLE_CLIENT_ID` (optional, token verification).
- Apple: `APPLE_CLIENT_ID`, `APPLE_TEAM_ID`, `APPLE_KEY_ID`, `APPLE_P8_KEY` (optional; required if Apple auth is enabled).

#### Push notifications
- Expo: `EXPO_AUTHORIZATION_TOKEN` (optional).

### Docker Compose variables
`fast_app/templates/project_structure/docker-compose.yml` reads from `.env.docker` and inlines some values:
- `APP_NAME`: used for container and network naming. Default: `fast_app`.
- `MAP_ASGI_PORT`: host→container port mapping for API (default host `8000`).
- Containers set `REDIS_HOST=redis` internally; you usually don’t override this inside the compose network.
 - Redis and RabbitMQ ports are not published to the host by default (internal-only).

 

### Recommended example files

Local development (`.env.debug`):
```env
ENV=debug
MONGO_URI=mongodb://localhost:27017
SECRET_KEY=dev-secret-key-not-for-production

# Optional (uncomment as needed)
# DB_NAME=fast-app
# LOG_LEVEL=DEBUG
# REDIS_HOST=localhost
# REDIS_PORT=6379
# QUEUE_DRIVER=sync           # or async_farm
# RABBITMQ_URL=amqp://guest:guest@localhost:5672/
# AUTH_JWT_ALGORITHM=HS256
# ACCESS_TOKEN_LIFETIME=900
# REFRESH_TOKEN_LIFETIME=604800
# LOCALE_DEFAULT=en
# LOCALE_FALLBACK=en
# LOCALE_PATH=
# MAIL_DRIVER=log             # or smtp or smtp2go
# MAIL_SERVER=
# MAIL_PORT=
# MAIL_LOGIN=
# MAIL_PASSWORD=
# MAIL_FROM=
# SMTP2GO_API_KEY=
# SEND_LOG_ERRORS_SLACK_WEBHOOK_URL=
# SEND_LOG_ERRORS_TELEGRAM_BOT_TOKEN=
# SEND_LOG_ERRORS_TELEGRAM_CHAT_ID=
# GOOGLE_CLIENT_ID=
# APPLE_CLIENT_ID=
# APPLE_TEAM_ID=
# APPLE_KEY_ID=
# APPLE_P8_KEY=
# EXPO_AUTHORIZATION_TOKEN=
```

Docker (`.env.docker`):
```env
APP_NAME=fast_app
MAP_ASGI_PORT=8000

# App/runtime variables are also read inside containers via env_file
# e.g., MONGO_URI, SECRET_KEY, etc.
```

### Notes
- Keep secrets like `SECRET_KEY`, credentials, and webhooks out of version control.
- Use the smallest possible `.env.*` files: required keys only; refer back to this page for all optional settings.
