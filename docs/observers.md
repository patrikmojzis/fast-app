# Observers

Observers let you hook into a model’s lifecycle (create, update, delete) without polluting the model itself. Each observer receives the model instance and can mutate it, halt the operation, or trigger side effects.

## Generating an observer

Scaffold a new observer with the CLI:

```bash
fast-app make observer LeadObserver
```

The generator creates `app/observers/lead_observer.py` with a class stub derived from `fast_app.contracts.observer.Observer`.

## Lifecycle hooks

The base contract defines six async hooks:

- `on_creating(model)` — runs before the model is inserted.
- `on_created(model)` — runs after insert completes.
- `on_updating(model)` — runs before an update.
- `on_updated(model)` — runs after update succeeds.
- `on_deleting(model)` — runs before deletion.
- `on_deleted(model)` — runs after deletion.

All hooks execute inside the model’s event loop context, so you can await other async calls.

## Relationship to models

Models keep track of observers via `model.register_observer(observer_instance)`. During lifecycle events, the model invokes the relevant hook on each registered observer. Dirty tracking (`model.clean`) records which fields changed; inside `on_creating`/`on_updating` you can inspect `model.clean` to see the old values.

```python
from fast_app.contracts.observer import Observer


class LeadObserver(Observer):
    async def on_creating(self, model):
        # Ensure name defaults before insertion
        if not model.name:
            model.name = "Unnamed"

    async def on_updating(self, model):
        previous_email = model.clean.get("email")
        if previous_email and previous_email != model.email:
            await audit_log(model.id, "email_changed", previous_email, model.email)
```

After `save()` completes, the model refresh resets `model.clean`, so dirty fields are only available during the hook execution.

## Auto-discovery and manual registration

When you import `import fast_app.boot`, the framework automatically discovers observers in `app/observers/` whose filenames and class names match your models (e.g., `lead_observer.py` with `LeadObserver`). The matching model registers the observer by default.

If an observer is not auto-registered, attach it manually with the `register_observer` decorator:

```python
from fast_app.decorators.model_decorators import register_observer
from app.observers.lead_observer import LeadObserver


@register_observer(LeadObserver)
class Lead(Model):
    ...
```

The decorator wraps the model’s `__init__` to register the observer instance every time the model is instantiated, ensuring hooks fire during persistence operations.

## Mutating models inside hooks

Because hook methods receive the concrete model instance, you can modify attributes before the database write happens. Common use cases include:

- Normalizing or casting incoming values (`model.email = model.email.lower()`).
- Setting default metadata (timestamps, slugs).
- Running cross-collection integrity checks.

Any changes made in `on_creating` or `on_updating` become part of the persisted payload. 

Observers provide a single place to centralize domain-side effects tied to persistence, keeping controllers and models lean.


