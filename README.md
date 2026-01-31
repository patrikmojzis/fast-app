# FastApp

Pragmatic, Laravel‑flavoured toolkit for building backend APIs with Python.
Compose Quart (HTTP), fast‑validation (Pydantic‑style), and Motor (Mongo) to ship fast—without boilerplate.

## Why FastApp
- Contracts-based design and autodiscovery
- Async‑first: Quart + Motor
- Pydantic‑style validation via fast‑validation
- Batteries included: auth, queue, scheduler, notifications, broadcasting
- Elegant routing, middleware, models, and resources

## Install
```bash
pip install git+https://github.com/patrikmojzis/fast-app
```

## Hello API in 60 seconds
```python
import fast_app.boot  # Always first

from quart import Quart
from pydantic import constr
from fast_app import Route, Schema, Model, Resource
from fast_app.utils.routing_utils import register_routes
from fast_app.core.pydantic_types import ShortStr

class Item(Model):
    name: str

class ItemResource(Resource):
    async def to_dict(self, item: Item):
        return {"name": item.name}

class ItemSchema(Schema):
    name: ShortStr

async def create_item(data: ItemSchema):
    item = await Item.create(data.validated)
    return ItemResource(item)

app = Quart(__name__)
register_routes(app, [
    Route.post("/item", create_item),
])
```

## CLI (essentials)
- `fast-app init` – scaffold a new project
- `fast-app make <type> <Name>` – generate models, schemas, resources, middleware, …
- `fast-app serve` – start the asgi (debug)
- `fast-app work` – work queue, events
- `fast-app migrate` / `fast-app seed`

## Docs & Links
- Docs: `mkdocs serve`
- Repo: [github.com/patrikmojzis/fast-app](https://github.com/patrikmojzis/fast-app)
- License: MIT
