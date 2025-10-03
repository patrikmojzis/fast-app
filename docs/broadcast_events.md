# Broadcast Events

Broadcast events describe the payload delivered to clients and the rooms that should receive it. They extend `fast_app.contracts.broadcast_event.BroadcastEvent`, which itself inherits from the base `Event` contract.

## Generating an event

```bash
fast-app make broadcast_event UpdateChat
```

This creates `app/socketio/events/update_chat.py`. Keep events under `app/socketio/events/` so autodiscovery and imports remain tidy.

## Defining an event

```python
from typing import TYPE_CHECKING, Union

from fast_app import BroadcastEvent
from app.http_files.resources.chat_resource import ChatResource
from app.socketio.rooms.chat_room import ChatRoom
from app.models.chat import Chat

if TYPE_CHECKING:
    from fast_app import Room


class UpdateChat(BroadcastEvent):
    chat: Chat

    async def broadcast_on(self) -> Union[str, "Room"]:
        return ChatRoom(self.chat.id)

    async def broadcast_as(self):
        return ChatResource(self.chat)
```

Key methods:

- `broadcast_on()` — return a room string, a `Room` instance, or a list of either. The helper `fast_app.utils.broadcast_utils.get_broadcast_ons` normalizes to `{room, namespace}` pairs.
- `broadcast_when()` — override to conditionally skip broadcasting; default returns `True`.
- `broadcast_as()` — transform the payload. Returning a Resource automatically serializes through `Resource.dump()`; Pydantic models (`model_dump`) are supported as well.

## Emitting events

Call `await broadcast(event_instance)` from anywhere in your application (controllers, observers, background jobs). Example:

```python
from fast_app.core.broadcasting import broadcast
from app.socketio.events.update_chat import UpdateChat


async def notify_chat_updated(chat: Chat) -> None:
    await broadcast(UpdateChat(chat=chat))
```

Internally, `broadcast` checks `broadcast_when()`, resolves rooms via `broadcast_on()`, transforms the payload, and emits through a Redis Socket.IO manager.

## Tips

- Use resources to keep event payloads consistent with your HTTP API.
- Broadcast from observers or domain services to notify clients about model changes without duplicating logic.
- Namespaces default to `/`; pass a `Room` with a custom namespace if you need separation.
- Combine with async farm workers to broadcast from background jobs (the Redis manager handles fan-out across processes).

Broadcast events decouple real-time delivery from controller logic, ensuring clients stay in sync with minimal effort.


