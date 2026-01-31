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
pip install "git+https://github.com/patrikmojzis/fast-app"
```

3) Scaffold a new project

```bash
fast-app init
```

4) Configure .env

```bash
cp .env.example .env
```

5) Run the API

```bash
fast-app serve          # runs hypercorn from app.modules.asgi.app:app
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
        return {
            "name": item.name
        }

class ItemSchema(Schema):
    name: ShortStr

async def create_item(data: ItemSchema):
    item = await Item.create(data.model_dump())
    return ItemResource(item)

app = Quart(__name__)
routes = [
    Route.post("/item", create_item),
]
register_routes(app, routes)
```

**Note:** Every Python entry point must import `fast_app.boot` first to initialize logging, environment, and autodiscovery. See [Quick Start](quick_start.md) for details.