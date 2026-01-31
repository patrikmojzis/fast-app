# API Helpers

`fast_app.core.api` provides validation, pagination, and filtering utilities to keep controllers clean. This module handles request/query parsing, Pydantic validation, async rule checks, and common pagination patterns.

## Request validation

### `validate_request(schema, *, partial=False)`

Parse and validate JSON request bodies. Returns the schema instance and stores the validated dictionary in `quart.g.validated`.

```python
from fast_app.core.api import validate_request
from quart import g

async def store(data: LeadSchema):
    # `data` is the schema instance, `data.validated` is the dict
    lead = await Lead.create(data.validated)
    return LeadResource(lead)
```

- Runs Pydantic field validation first.
- If the schema extends `fast_validation.Schema`, calls `await schema.validate(partial=partial)` to run async rules.
- Raises `UnprocessableEntityException` (422) on validation failure with sanitized error details.

### `validate_query(schema, *, partial=False)`

Parse and validate query parameters. Returns the schema instance and stores the validated dictionary in `g.validated_query`.

```python
from fast_app.core.api import validate_query

class LeadIndexFilter(Schema):
    source: Literal["direct", "eshop", "pharmacy"] | None = None
    rep_id: ObjectIdField | None = None
    is_highlighted: bool | None = None

    class Meta:
        rules = [
            Schema.Rule("$.rep_id", [ExistsValidatorRule(allow_null=True)]),
        ]

# Route.get("/lead", lead_controller.index)
async def index(filter: LeadIndexFilter):
    # filter is validated automatically
    return await list_paginated(Lead, LeadResource, filter=filter)
```

When you omit the model, `ExistsValidatorRule` infers it from the field name (e.g., `rep_id` → `Rep`).

The helper intelligently collects query parameters:

- Scalar fields: `?rep_id=abc123` → `{"rep_id": "abc123"}`
- List fields: `?tags=a&tags=b` or `?tags[]=a&tags[]=b` or `?tags=a,b,c` → all merged into a list
- Type coercion happens during Pydantic validation

## Pagination

FastApp includes three pagination helpers that return `{meta, data}` dictionaries ready for JSON serialization.

### `list_paginated(model, resource, *, filter=None, sort=None)`

Standard pagination with count + find. Accepts query parameters `page`, `per_page`, `sort_by`, `sort_direction`.

```python
from fast_app.core.api import list_paginated

async def index():
    return await list_paginated(Lead, LeadResource)
```

Meta response includes `total`, `current_page`, `per_page`, `last_page`, `skip`, `displaying`.

### `search_paginated(model, resource, *, filter=None, sort=None)`

Text search across model fields via `model.search()`. Requires query parameter `search` plus pagination params.

```python
async def search():
    return await search_paginated(Lead, LeadResource)
```

### `paginate(Model, Resource, *, filter=None, sort=None)`

Convenience wrapper: checks for `?search=...` and delegates to `search_paginated` or `list_paginated` accordingly.

```python
async def index():
    return await paginate(Lead, LeadResource)
```

## Filtering

### Schema-based filters

Pass a validated schema instance to `filter` to restrict results. The schema is converted to a dictionary (via `model_dump(exclude_unset=True)`) and merged with the base query.

```python
class LeadIndexFilter(Schema):
    source: Literal["direct", "eshop", "pharmacy", "distributor"] | None = None
    county_id: ObjectIdField | None = None
    is_highlighted: bool | None = None

    class Meta:
        rules = [
            Schema.Rule("$.county_id", [ExistsValidatorRule(allow_null=True)]),
        ]

async def index(filter: LeadIndexFilter):
    return await paginate(Lead, LeadResource, filter=filter)
```

Unset fields are excluded, so only provided filters apply.

### `get_mongo_filter_from_query(*, param_name="filter", allowed_fields=None, allowed_ops=None)`

Parse a JSON (or base64-JSON) Mongo filter from the query string with strict operator and field allowlists.

```python
from fast_app.core.api import get_mongo_filter_from_query

async def advanced_index():
    extra_filter = get_mongo_filter_from_query(
        allowed_fields=["name", "tags", "created_at"],
        allowed_ops=["$eq", "$in", "$gte", "$lte"],
    )
    return await list_paginated(Item, ItemResource, filter=extra_filter)
```

Clients can send complex queries:

```
?filter={"name":{"$in":["A","B"]},"created_at":{"$gte":"2024-01-01"}}
```

or base64-encoded for URL safety. The helper validates operators/fields and raises `UnprocessableEntityException` if disallowed constructs appear.

Default allowed operators include `$and`, `$or`, `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$nin`, `$exists`, `$regex`, `$size`, `$all`, `$elemMatch`.

## Request helpers

### `get_client_ip()`

Extract the client's IP address from `X-Forwarded-For`, `X-Real-IP`, or fallback to `request.remote_addr`. Useful for logging, rate limiting, or geolocation.

```python
from fast_app.core.api import get_client_ip

async def track():
    ip = get_client_ip()
    await log_access(ip)
```

### `get_bearer_token()`

Parse the `Authorization: Bearer <token>` header and return the token string, or `None` if absent.

```python
from fast_app.core.api import get_bearer_token

async def validate_custom_auth():
    token = get_bearer_token()
    if token:
        user = await verify_jwt(token)
```

Raises `AppException` if called outside a request context.

## Tips

- Use `partial=True` in `validate_request` / `validate_query` for PATCH endpoints to skip unset fields.
- Combine schema filters with `get_mongo_filter_from_query` for admin endpoints that need flexible querying.
- Pagination helpers run `model.count()` and `model.find()` concurrently via `asyncio.gather` for better performance.
- Schema-based filters leverage async rule validation, so you can enforce relational constraints (e.g., `ExistsValidatorRule`) before hitting the database.

With these helpers, controllers stay thin and focused on orchestration while validation and data fetching logic lives in reusable, testable utilities.
