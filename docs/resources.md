# Resources

Resources transform models into API-friendly payloads. They give you a dedicated layer to enrich responses, preload relationships, and keep controllers slim.

## Generating a resource

Use the CLI to scaffold a new resource:

```bash
fast-app make resource Stock
```

The generator creates `app/http_files/resources/stock_resource.py` with a class stub inheriting from `fast_app.contracts.resource.Resource` (or your local `ResourceBase`).

## Implementing `to_dict`

Every resource must implement `async def to_dict(self, data: Model) -> dict`. This method receives a single model instance and returns the serializable representation. Resolve relationships or perform async lookups before returning the payload.

```python
from fast_app import Resource


class StockResource(Resource):
    async def to_dict(self, stock):
        return {
            "_id": stock.id,
            "name": stock.name,
            "rep": RepResource(stock.rep()),
        }
```

Resources can return nested resources or lists; the base class resolves any nested `Resource` instances and awaits them concurrently.

## Returning resources from controllers

Controllers can return a resource instance directly. `ResourceResponseMiddleware` (automatically applied by `register_routes`) calls `to_response()` and serializes the payload.

```python
# Route.get("/stocks/<stock_id>")
async def show(stock: Stock):
    return StockResource(stock)
```

Pass a list of models to return multiple records: `return StockResource(await Stock.find({...}))`. The base class handles gathering each item’s `to_dict` concurrently.

Resources provide an elegant, testable layer between domain models and API responses, making it easy to evolve your response structure without touching controllers.


