# Rooms

Rooms encapsulate authorization and routing logic for Socket.IO channels. Each room subclass inherits from `fast_app.contracts.room.Room` and controls who can join and how a room identifier is derived.

## Generating a room

```bash
fast-app make room ChatRoom
```

The generator places a stub in `app/socketio/rooms/chat_room.py`. Align with the recommended folder layout (`app/socketio/rooms/` alongside `events/` and `namespaces/`).

## Anatomy of a room class

```python
from typing import Any, Optional, TYPE_CHECKING

from fast_app import Room
from app.models.chat import Chat

if TYPE_CHECKING:
    from app.models.user import User


class ChatRoom(Room):
    @classmethod
    async def extract_room_identifier(cls, session: Any, data: dict[str, Any]) -> str:
        if not data.get("chat_id"):
            raise ValueError("chat_id is required")
        return data["chat_id"]

    @classmethod
    async def can_join(cls, session: Any, data: dict[str, Any]) -> bool:
        user: Optional["User"] = session.get("user")
        if not user or not data.get("chat_id"):
            return False

        chat = await Chat.find_by_id(data["chat_id"])
        if not chat:
            return False

        return await user.can("access", chat)
```

- **Constructor** — room subclasses usually accept a domain identifier (e.g., `chat_id`) and pass it to `Room.__init__`. When you instantiate `ChatRoom(chat.id)` inside `broadcast_on()`, this value becomes the canonical room name.
- `extract_room_identifier` returns the actual room string (e.g., primary key). Use the Socket.IO session and incoming payload to determine context.
- `can_join` evaluates whether the current user can subscribe. Leverage policies via `user.can(...)` for granular control.

## Registering rooms with namespaces

Use `@register_room(RoomSubclass)` to attach rooms to a namespace. When clients join, the decorator ensures `extract_room_identifier` and `can_join` run.

```python
from socketio import AsyncNamespace
from fast_app.decorators.namespace_decorator import register_room
from app.socketio.rooms.chat_room import ChatRoom


@register_room(ChatRoom)
class GlobalNamespace(AsyncNamespace):
    def __init__(self) -> None:
        super().__init__("/")

    async def on_connect(self, sid, environ, auth):
        await authenticate(self, sid, environ, auth)
```

The namespace can expose `on_join_chat` or similar handlers that accept a payload containing `chat_id`. Registered rooms will enforce authorization.

## Tips

- Store authenticated user objects in the session during `on_connect` so room guards have access to policies.
- Mirror the constructor signature (`__init__(room_value)`) when instantiating the room class elsewhere; `extract_room_identifier` should return the same value so clients and server agree on the channel name.
- Raise descriptive errors in `extract_room_identifier` to surface client mistakes early.
- Keep room logic small; delegate heavy lifting (loading chat, verifying permissions) to models or services.

With rooms defined, client connections are filtered before they receive any broadcast events.


