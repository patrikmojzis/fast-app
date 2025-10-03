# Routing

FastApp routes mirror the Laravel style you might know from PHP frameworks. Define declarative `Route` objects, then register them against your Quart application with `register_routes`. A typical project keeps these definitions in `app/http_files/routes/api.py` to keep HTTP wiring in one place.

## Declaring routes

Import the `Route` contract and compose a list of routes. Each HTTP verb has a convenience constructor:

- `Route.get(path, handler, middlewares=None)`
- `Route.post(...)`
- `Route.put(...)`
- `Route.patch(...)`
- `Route.delete(...)`
- `Route.options(...)`
- `Route.head(...)`

Handlers can be callables or coroutine functions. Middlewares accept either middleware classes implementing `fast_app.contracts.middleware.Middleware`, instances, or simple callables that wrap the handler.

```python
from fast_app import Route, ThrottleMiddleware
from app.http_files.controllers import ping_controller

routes = [
    Route.get("/ping", ping_controller.show),
    Route.post("/signup", auth_controller.register, [ThrottleMiddleware(limit=10, window_seconds=60)]),
]
```

## Route groups

Use `Route.group()` to share prefixes or middleware across nested routes. Groups can be nested arbitrarily, and you can mix `prefix` and `middlewares` arguments:

```python
from app.http_files.middlewares import AuthMiddleware, BusinessMiddleware

routes = [
    Route.group("/auth", routes=[
        Route.post("/dispatch", auth_controller.dispatch),
        Route.post("/exchange", auth_controller.exchange),
        Route.delete("/", auth_controller.logout, [AuthMiddleware]),
    ]),
    Route.group(
        middlewares=[AuthMiddleware, BusinessMiddleware],
        routes=[
            Route.get("/chat/history", chat_controller.get_history),
            # ... more nested routes
        ],
    ),
]
```

When you call `Route.group(prefix="/reports", routes=[...])`, all nested paths inherit the `/reports` prefix. Middleware declared on the group runs before route-specific middleware, and global middlewares such as `HandleExceptionsMiddleware` and `ResourceResponseMiddleware` are injected automatically when you register the routes.

## Resource routes

`Route.resource(path, controller)` generates a small CRUD route group. The controller must expose the following callables:

- `index` — list resources (`GET path/`)
- `show` — fetch a resource (`GET path/<id>`)
- `store` — create a resource (`POST path/`)
- `update` — update a resource (`PATCH path/<id>`)
- `destroy` — delete a resource (`DELETE path/<id>`)

Method names can be overridden by passing `controller_methods`. For example:

```python
Route.resource(
    "/lead",
    lead_controller,
    controller_methods={"update": "patch", "destroy": "soft_delete"},
)
```

If you prefer an alternate path parameter (defaults to `<lead_id>` based on the slug), supply `parameter="<slug>"`.

Because `Route.resource` returns a group, you can nest additional routes alongside it:

```python
routes = [
    Route.resource("/order", order_controller),
    Route.group("/order/<order_id>", routes=[
        Route.post("/attachment", order_controller.upload_attachments),
        Route.delete("/attachment/<file_id>", order_controller.remove_attachment),
    ]),
]
```

## Registering routes with Quart

Once your list is ready, register it with the Quart app. `register_routes` flattens groups, applies middleware ordering, and calls `app.add_url_rule` for every definition.

```python
from quart import Quart
from fast_app.utils.routing_utils import register_routes
from app.http_files.routes.api import routes

app = Quart(__name__)
register_routes(app, routes)

if __name__ == "__main__":
    app.run()
```

`register_routes` injects global middlewares in the following order: `HandleExceptionsMiddleware`, `ModelBindingMiddleware`, `SchemaValidationMiddleware`, user-specified middlewares, and finally `ResourceResponseMiddleware`. This ensures consistent request handling regardless of where your routes live.

## Recommended project structure

Keep HTTP routes close to controllers and schemas. A common layout:

```
app/
  http_files/
    routes/
      api.py          # Route list exported as `routes`
    controllers/
      auth_controller.py
      lead_controller.py
    middlewares/
      auth_middleware.py
```

Import `routes` from that module inside your Quart entry point (e.g., `app/modules/asgi/app.py`) to keep the route table declarative and discoverable.


