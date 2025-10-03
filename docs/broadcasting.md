# Broadcasting Basics

FastApp ships with a Socket.IO-compatible broadcasting layer. Events are serialized through Redis and delivered to connected clients using rooms and namespaces. This guide explains the moving parts and how to wire them together.

## Core pieces

- **Broadcast events** (`app/socketio/events/`) — subclasses of `fast_app.contracts.broadcast_event.BroadcastEvent`. They define the payload and channel.
- **Rooms** (`app/socketio/rooms/`) — subclasses of `fast_app.contracts.room.Room`. They resolve room identifiers and enforce access control.
- **Namespaces** (`app/socketio/namespaces/`) — Socket.IO namespaces (usually `AsyncNamespace`) decorated with `@register_room` so the framework knows which rooms to expose.
- **Broadcast function** — `fast_app.core.broadcasting.broadcast(event)` transforms the event into JSON (resources supported) and emits it to Redis.

Recommended structure (mirrors the sample project):

```
app/
  socketio/
    common/
      authentication.py
    events/
      update_chat.py
    rooms/
      chat_room.py
    namespaces/
      global_namespace.py
```

## Redis and Socket.IO

FastApp uses `socketio.AsyncRedisManager` under the hood. Configure the manager through `REDIS_SOCKETIO_URL` (defaults to `redis://localhost:6379/14`). Each `broadcast()` call emits to all rooms defined by the event’s `broadcast_on()` method. Clients subscribe by connecting to the namespace/room combination.

## Flow overview

1. Client connects to a namespace; `on_connect` authenticates and stores user details in the Socket.IO session.
2. Client joins rooms by emitting events handled by your namespace/room combination.
3. Server-side code triggers a `BroadcastEvent` (e.g., inside a controller or observer) and calls `await broadcast(event)`.
4. Redis manager emits to every subscribed worker; workers forward to connected clients.

## Setting up the structure

Before building individual events and rooms, scaffold the base Socket.IO structure:

```bash
fast-app publish socketio
```

This copies the recommended folder layout into your project:

- `app/modules/asgi/socketio.py` — Socket.IO server initialization
- `app/socketio/common/authentication.py` — authentication helper
- `app/socketio/namespaces/global_namespace.py` — default namespace stub
- `app/socketio/events/` — placeholder for broadcast events
- `app/socketio/rooms/` — placeholder for room classes

Once the structure is in place, use CLI generators to add individual components:

```bash
fast-app make room ChatRoom
fast-app make broadcast_event UpdateChat
```

The generators populate the directories with minimal stubs ready for customization.

With these pieces in place, broadcasting becomes a matter of instantiating events and calling `broadcast()`. The following sections dive into room definitions and event classes in more detail.


