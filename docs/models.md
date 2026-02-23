# Models

FastApp models are lightweight typed models layered on top of Motor. They include change tracking, Mongo-friendly helpers, and Laravel-inspired relationships.

## Generating a model

Use the CLI to scaffold a new model. Naming convention: omit the `Model` suffix in both the class and filename.

```bash
fast-app make model User
```

This generates `app/models/user.py` with a `User` class stub. Add field annotations directly on the model class:

```python
from fast_app import Model

class User(Model):
    email: str
    name: str | None = None
```

Fields declared on the class become persisted attributes. Avoid suffixing the file or class with `Model`; FastApp handles that implicitly.

## Creating and saving

Instantiate the model and call `save()` to insert or update depending on whether `_id` is set:

```python
user = User(email="john@example.com", name="John")
await user.save()  # inserts a document and assigns user._id

# Update attributes and save again
user.name = "John Smith"
await user.save()  # triggers update and refreshes fields
```

Alternatively, use the convenience class methods:

```python
created = await User.create({"email": "jane@example.com", "name": "Jane"})
first = await User.first()   # returns first document
exists = await User.exists({"email": "jane@example.com"})   # True or False
```

## Reading and querying

The contract exposes familiar helpers:

- `User.find(query)` → list of `User`
- `User.find_one(query)` → single `User | None`
- `User.find_by_id(id)` → fetch by ObjectId or hex string
- `User.find_or_fail(query)` / `find_by_id_or_fail(id)` → raise `ModelNotFoundException` on absence
- `User.search(query)` → text search across fields and configured relations
- `User.scope()` → fluent query builder

Example:

```python
users = await User.find({"active": True}, sort=[("created_at", -1)])
maybe = await User.find_one({"email": "john@example.com"})
by_id = await User.find_by_id("66f2d3...")

if maybe:
    await maybe.update({"name": "John Updated"})

count = await User.count({"active": True})
```

## Relationships

Models include three helpers for simple relationships. Define async accessors on the model to make usage explicit and keep circular imports at bay.

```python
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from fast_app import Model

if TYPE_CHECKING:
    from app.models.lead import Lead


class User(Model):
    name: str

    async def lead(self) -> Optional['Lead']:
        from app.models.lead import Lead   # local import to avoid circular dependency
        return await self.has_one(Lead)


class Lead(Model):
    user_id: ObjectId

    async def user(self) -> Optional[User]:
        return await self.belongs_to(User)


user = await User.find_by_id(user_id)
lead = await user.lead()     # has_one helper under the hood
user = await lead.user()
```

- `belongs_to(parent_model, parent_key="_id", child_key="snake_case_model_name_id")`
- `has_one(child_model, parent_key="_id", child_key="snake_case_model_name_id")`
- `has_many(child_model, parent_key="_id", child_key="snake_case_model_name_id")`

Override `parent_key` or `child_key` for non-standard schemas. Example default: `ChatQuery` -> `chat_query_id`. Each helper automatically converts string IDs to `ObjectId` when `is_object_id` is `True` (default).
When you expose relationships as methods, use `TYPE_CHECKING` imports (as above) to keep type hints without triggering runtime import cycles.

## Change tracking and persistence

Setting attributes records dirty fields in `self.clean`. `save()` or `update()` writes only changed fields and updates `updated_at`. Successful operations trigger observer hooks and bump the collection cache version, which invalidates cached queries.

```python
user.set("name", "Alice")
await user.save()

await User.update_many({"active": False}, {"$set": {"active": True}})
```

Use `touch()` to bump the `updated_at` timestamp without modifying other fields.
