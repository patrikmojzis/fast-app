# Fast App

Fast App is an async, Laravel-inspired toolkit for building HTTP APIs on Quart + Motor (MongoDB). It ships a batteries-included core (routes, schemas, models, resources, middleware, events) with optional extras like queues, scheduling, broadcasting, notifications, storage, and a CLI.

## Requirements

- Python 3.12+
- MongoDB (required)
- Optional: Redis (cache/socket.io/scheduler), RabbitMQ (`async_farm` queue)

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install "git+https://github.com/patrikmojzis/fast-app"
fast-app init
fast-app serve
```

Then open `http://localhost:8000`.

## Next steps

- Start with the Getting Started section in the sidebar
- Review Routes, Schemas, Models, and Resources to build your API
- See Hosting when you are ready to deploy
