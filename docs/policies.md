# Policies

Policies encapsulate authorization logic for a model. Pair them with the `Authorizable` mixin to give users (`can`, `cannot`, `authorize`) checks and wire them into middleware.

## Generating a policy

Use the CLI to scaffold a policy class:

```bash
fast-app make policy ChatPolicy
```

This command creates `app/policies/chat_policy.py` with a class inheriting from `fast_app.contracts.policy.Policy`.

## Structure of a policy

Each policy exposes async methods that return `True` or `False` for specific abilities. The optional `before` hook runs prior to any ability method—return `True` to short-circuit with a grant, `False` to deny outright, or `None` to fall through to the method-specific check.

```python
from typing import Optional, TYPE_CHECKING

from fast_app import Policy

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.chat import Chat


class ChatPolicy(Policy):
    async def before(self, ability: str, user: "User") -> Optional[bool]:
        if user.is_admin:
            return True
        return None

    async def access(self, chat: "Chat", user: "User") -> bool:
        return user.id == chat.created_by_user_id

    async def delete(self, chat: "Chat", user: "User") -> bool:
        return user.id == chat.created_by_user_id and not chat.archived
```

Define one method per ability (e.g., `view`, `update`, `delete`). Ability names are arbitrary strings, but should stay consistent with your controller usage.

## Wiring policies to models

Attach a policy to a model by importing it and setting the `policy` class attribute, or use the `Authorizable` helper decorator. Models that represent authenticated users should include the `Authorizable` mixin so they gain `can`, `cannot`, and `authorize` methods.

```python
from fast_app.core.mixins.authorizable import Authorizable
from fast_app.templates.make.policy import ChatPolicy


class User(Model, Authorizable):
    pass


class Chat(Model):
    policy = ChatPolicy()
```

`Authorizable.can(ability, target)` resolves the policy attached to the target model or class, runs the `before` hook, then invokes the ability method. `cannot` negates the result, and `authorize` raises `ForbiddenException` on failure.

## Using policies in routes

Apply `AuthorizeMiddleware` to protect endpoints declaratively. The middleware retrieves the current user from `quart.g`, resolves the target, and calls `user.authorize(ability, target)`.

```python
Route.group("/chat", middlewares=[AuthMiddleware], routes=[
    Route.post("/", chat_controller.store),
    Route.get("/", chat_controller.index),
    Route.post("/<chat_id>/message", chat_controller.message, [AuthorizeMiddleware("access", "chat")]),
    Route.post("/<chat_id>/feedback", chat_controller.feedback, [AuthorizeMiddleware("access", "chat")]),
    Route.get("/<chat_id>", chat_controller.show, [AuthorizeMiddleware("access", "chat")]),
    Route.delete("/<chat_id>", chat_controller.destroy, [AuthorizeMiddleware("access", "chat")]),
])
```

In this example, `ModelBindingMiddleware` converts `chat_id` into a `Chat` instance and stores it in the handler kwargs (`chat`). The middleware targets that argument by name and tests the `access` ability.

## Tips

- Use `before` to centralize global privileges (admins, owners) and let individual methods handle nuanced checks.
- Keep policies stateless—no database access—so they execute quickly. Fetch required context in controllers before calling `authorize`.
- When an ability applies to a model class rather than an instance (e.g., `create`), pass the class to `authorize` and accept `None` as the first parameter in your policy method.
- Combine policies with `Authorizable` checks in services or background jobs; you’re not limited to HTTP middleware.

Policies offer a clean separation between authorization rules and application logic, making it easy to audit and evolve access control.


