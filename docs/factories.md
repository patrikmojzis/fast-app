# Factories

Factories give you a fast way to produce realistic model instances. They are perfect for tests, seeders, fixtures, or any scenario where you need repeatable sample data without hand‑crafting dictionaries every time.

## Generate a factory stub

Use the CLI to scaffold a factory:

```bash
fast-app make factory UserFactory
```

This command creates `app/db/factories/user_factory.py` with a class named `UserFactory`. As long as the class name follows the `<Model>Factory` pattern and lives in that directory, FastApp will discover it automatically during boot and register it on the matching model (`User.factory`).

> **Need a custom location or name?** Import `register_factory` from `fast_app.decorators` and attach your factory manually:
>
> ```python
> from fast_app.decorators import register_factory
> from app.db.factories.user_factory import UserFactory
>
> @register_factory(UserFactory)
> class User(Model):
>     ...
> ```

## Defining attributes

Inside your new factory, declare fields using the helper descriptors:

```python
from datetime import datetime, timezone

from fast_app.contracts.factory import Factory, Faker, Value, CallableAttribute, Function
from app.models.user import User


class UserFactory(Factory[User]):
    name = Faker("name")                   # uses the optional Faker dependency
    email = Faker("email")
    status = Value("active")               # always the same value
    nickname = CallableAttribute(lambda faker: f"{faker.color()}-fox")
    expires_at = Function(lambda: datetime.now(timezone.utc))
```

- `Faker(...)` pulls data from the Faker provider (install `fast-app[dev]` or add Faker to your project).
- `Value(...)` returns a constant every time.
- `CallableAttribute(...)` lets you compute values yourself. The callable receives the shared Faker instance (or `None` when Faker is not installed, if you pass `requires_faker=False`).
- `Function(...)` calls any function you give it—perfect for timestamps like `datetime.utcnow`.

Any keyword arguments you pass when calling the factory will override these defaults.

## Factory API at a glance

| Method | Description |
| ------ | ----------- |
| `User.factory.build(**overrides)` | Returns an *unsaved* model instance. Great for tests where you do not need the database. |
| `await User.factory.create(**overrides)` | Persists the model and returns the saved instance. |
| `await User.factory.seed(count, **overrides)` | Bulk insert `count` documents efficiently, returning the created instances. |
| `User.factory.count(n).build()` | Batch helper that repeats any factory call `n` times (`create` and `seed` also available). |
| `User.factory.with_related(...)` | Creates related models alongside the parent and fills foreign keys automatically. |

Every method accepts overrides, so `await User.factory.create(name="Jane Doe")` replaces only that attribute.

## Creating related models

Use `with_related` when a model depends on another document (e.g. `User` belongs to `Business`):

```python
class BusinessFactory(Factory[Business]):
    name = Faker("company")


class UserFactory(Factory[User]):
    name = Faker("name")
    email = Faker("email")

# Create a business and associate its _id with the new user
user = await User.factory.with_related(Business, {"name": "Acme Inc."}).create()
assert user.business_id is not None
```

Arguments:

- First parameter can be the related model class or its string name (`"business"`). FastApp resolves it using the same naming conventions as autodiscovery.
- Provide per-relation overrides in the second argument (e.g. to set a specific business name).
- Optional keywords:
  - `factory=` lets you specify an explicit factory if the model does not have one registered.
  - `foreign_key=` overrides the default `<collection>_id` field name.

`with_related` returns a fresh factory instance, so you can chain calls:

```python
await Order.factory \
    .with_related(Customer, {"email": "client@example.com"}) \
    .with_related("product", {"sku": "SKU-123"}) \
    .create()
```

## Tips & gotchas

- **Faker is optional.** If you rely on Faker-powered attributes, make sure the dependency is installed in the environment that runs the factory.
- **Factories live on the model.** Once registered, every model exposes a `.factory` attribute. You can still instantiate your factory class directly if you prefer.
- **Asynchronous by design.** `create`, `seed`, and any method that calls them are `async` because they interact with the database.
- **Bulk seeding respects fillable fields.** Factories automatically drop protected attributes (`_id`, `created_at`, `updated_at`) unless you supply them explicitly.

With a handful of declarations you get consistent, expressive data builders that fit seamlessly into tests, seeders, and prototypes. Happy scaffolding!
