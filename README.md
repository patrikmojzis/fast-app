# FastApp

FastApp is a small, Laravel-flavoured toolkit for building backend APIs with Python.  
It wraps Quart, Pydantic and Motor so you can start shipping features without wiring the same pieces every time.

## Quick Start

1. **Install**

   ```bash
   pip install fast-app
   ```

2. **Define a model and a route**

   ```python
   from quart import Quart, jsonify, g
   from pydantic import BaseModel
   from fast_app import Model, Route, Middleware, validate_request, get_client_ip
   from fast_app.utils.routing_utils import register_routes

   class Item(Model):
       name: str

   class ItemSchema(BaseModel):
       name: str

   class SaveIP(Middleware):
       async def handle(self, next_handler, *args, **kwargs):
           g.ip = get_client_ip()
           return await next_handler(*args, **kwargs)

   async def create_item():
       await validate_request(ItemSchema)
       item = await Item.create(g.validated)
       return jsonify({"id": str(item._id), "name": item.name, "ip": g.ip})

   app = Quart(__name__)
   routes = [
       Route.get("/ping", lambda: "pong"),
       Route.post("/items", create_item, middlewares=[SaveIP])
   ]
   register_routes(app, routes)
   ```

3. **Run**

   ```bash
   quart run
   ```

Requests to `POST /items` will validate the JSON body, run the middleware and persist a document to MongoDB.

## Core ideas

- **Routes** – declare HTTP and WebSocket endpoints with optional middleware.
- **Models** – asynchronous MongoDB models with `create`, `find` and friends.
- **Middleware** – classes wrapping handlers: authentication, caching, etc.
- **Validation** – `validate_request` stores data in `g.validated` for you to use.

See `templates/project_structure` for a full project scaffold.

## Environment

FastApp expects a few variables:

- `MONGO_URI` – MongoDB connection string
- `REDIS_URL` – Redis connection string
- `SECRET_KEY` – session/CSRF secret
- `APP_NAME` – application name

Example files live in `templates/project_structure/env.debug.example` and `env.docker.example`.

## Testing

Run the test suite with:

```bash
pytest -q
```

## License

MIT
