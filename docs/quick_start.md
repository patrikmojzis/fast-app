# Quick Start

Get a FastApp project running in minutes. This guide walks you through installation, project setup, and your first endpoint.

## Installation

Create a virtual environment and install FastApp:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install "git+https://github.com/patrikmojzis/fast-app"
```

## Initialize a project

FastApp scaffolds a complete project structure with one command:

```bash
fast-app init
```

This creates:

```
app/
  app_config.py           # Optional application configuration
  models/                 # Domain models
  http_files/
    controllers/          # Request handlers
    resources/            # Response transformers
    schemas/              # Request validators
    middlewares/          # Custom middleware
    routes/
      api.py             # Route definitions
  modules/
    asgi/
      app.py             # ASGI entry point
```

## Understanding `import fast_app.boot`

Every Python entry point (ASGI servers, CLI scripts, worker processes) must import `fast_app.boot` as early as possible:

```python
import fast_app.boot  # Always first

from quart import Quart
# ... rest of your imports
```

This import:

- Reads `app/app_config.py` if present (optional) and applies configuration
- Sets up logging (console + file handlers)
- Loads environment variables from `.env` and `.env.{ENV}`
- Enables autodiscovery for observers, policies, and events when configured

### Configuring your app

The `app/app_config.py` file is **optional** but powerful. Use it to customize framework behavior:

```python
# app/app_config.py

autodiscovery = True  # Auto-register observers/policies based on naming conventions

events = {
    UserRegistered: [SendWelcomeEmail, CreateProfile],
}

storage_default_disk = "s3"
storage_disks = {
    "s3": {"driver": "s3", "bucket": "my-bucket"},
}

log_file_name = "custom.log"
```

Even without this file, `import fast_app.boot` handles logging and environment setup.

## Create your first route

Open `app/http_files/routes/api.py` and define routes:

```python
from fast_app import Route

async def ping():
    return {"message": "pong"}

routes = [
    Route.get("/ping", ping),
]
```

Register routes in `app/modules/asgi/app.py`:

```python
import fast_app.boot  # Always first

from quart import Quart
from fast_app.utils.routing_utils import register_routes
from app.http_files.routes.api import routes

app = Quart(__name__)
register_routes(app, routes)
```

## Run the development server

Start the API with auto-reload:

```bash
fast-app serve
```

Visit `http://localhost:8000/ping` to see your response.

## Core concepts

FastApp composes these building blocks:

- **Routes** — declarative HTTP definitions with middleware support
- **Schemas** — Pydantic validators with async rules
- **Models** — async ODM for MongoDB with observers and policies
- **Resources** — transform models into JSON responses
- **Controllers** — orchestrate validation, domain logic, and responses
- **Observers** — lifecycle hooks (on_created, on_updated, etc.)
- **Policies** — authorization rules enforced via middleware or manual checks
- **Events** — decouple side effects from controllers

Typical request flow: `Route → Middlewares → Controller → Schema → Model → Resource`

## Next steps

- Read [Routes](routes.md) to learn grouping, resource routes, and middleware
- Explore [Models](models.md) for database operations and relationships
- Check [Schemas](schemas.md) for validation patterns
- Review [API Helpers](api.md) for pagination and filtering utilities
- Set up [Queue](queue.md) for background jobs
- Configure [Broadcasting](broadcasting.md) for real-time features

FastApp follows Laravel-inspired conventions to keep your code organized and predictable. Dive into the sections above to unlock its full potential.
