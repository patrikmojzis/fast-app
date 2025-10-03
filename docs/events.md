# Events

Events decouple side effects from controllers and models. Instead of triggering actions directly (e.g., sending emails, logging, updating cache), dispatch events and let listeners handle them asynchronously via the queue.

## Why use events?

- **Decouple logic** — controllers remain focused on request handling; observers avoid business logic bloat
- **Asynchronous execution** — listeners run in background workers (async farm) without blocking responses
- **Testability** — test event dispatch separately from listener implementations
- **Extensibility** — add new listeners to existing events without modifying core code

## Generating events and listeners

Use the CLI to scaffold event and listener classes:

```bash
fast-app make event NewChatEvent
fast-app make listener GenerateChatTitle
```

Events land in `app/events/`, listeners in `app/listeners/`.

## Defining an event

Events extend `fast_app.Event` (a Pydantic model) and carry typed data:

```python
from bson import ObjectId
from fast_app import Event
from pydantic import Field


class NewChatEvent(Event):
    chat_id: ObjectId = Field(..., description="The ID of the chat")
```

Events are immutable data containers; keep them focused on a single domain action.

## Creating a listener

Listeners extend `fast_app.EventListener` and implement `async def handle(self, event)`:

```python
from typing import TYPE_CHECKING

from fast_app import EventListener

if TYPE_CHECKING:
    from app.events.new_chat_event import NewChatEvent


class GenerateChatTitle(EventListener):
    async def handle(self, event: "NewChatEvent") -> None:
        from app.models.chat import Chat

        chat = await Chat.find_by_id(event.chat_id)
        if not chat or not chat.input_history:
            return

        # Generate title using AI or logic
        title = generate_title_from_message(chat.input_history[0])
        await chat.update({"title": title})
```

Use `TYPE_CHECKING` imports to avoid circular dependencies while retaining type hints.

## Registering events

Wire events to listeners in `app/event_provider.py`:

```python
from typing import TYPE_CHECKING, Dict, List, Type

if TYPE_CHECKING:
    from fast_app import Event, EventListener

from app.events.new_chat_event import NewChatEvent
from app.events.new_user_message import NewUserMessage
from app.listeners.generate_chat_title import GenerateChatTitle
from app.listeners.new_message_listener import NewMessageListener


events: Dict[Type["Event"], List[Type["EventListener"]]] = {
    NewChatEvent: [GenerateChatTitle],
    NewUserMessage: [NewMessageListener],
}
```

The `events` dictionary maps each event class to a list of listeners. FastApp reads this during `import fast_app.boot` and configures the event system.

## Dispatching events

Call `dispatch(event_instance)` from anywhere in your application—controllers, observers, background jobs:

```python
from fast_app.core.events import dispatch
from app.events.new_chat_event import NewChatEvent


async def create_chat():
    chat = await Chat.create({"user_id": user.id})
    await dispatch(NewChatEvent(chat_id=chat.id))
    return ChatResource(chat)
```

### How dispatch works

1. `dispatch(event)` serializes the event and enqueues each registered listener via `fast_app.core.queue.queue`.
2. If `QUEUE_DRIVER=async_farm`, listeners execute on worker processes managed by `fast-app work`.
3. If `QUEUE_DRIVER=sync`, listeners run immediately in-process (useful for tests or lightweight deployments).

Context variables (`fast_app.core.context.context`) are preserved, so listeners have access to the same user/locale/etc. that was active when the event was dispatched.

### Immediate execution

For tests or synchronous flows, use `dispatch_now(event)` to await all listeners without queueing:

```python
from fast_app.core.events import dispatch_now

await dispatch_now(UserRegistered(user_id="123"))
```

This blocks until every listener completes.

## Tips

- Keep events focused on a single domain action; split complex flows into multiple events.
- Use listeners for side effects (emails, notifications, analytics) rather than core business logic.
- Test event dispatch by asserting the event was queued; test listeners by invoking `listener.handle(event)` directly.
- Combine with observers for model-specific hooks; use events for cross-cutting or multi-step workflows.

Events give you a clean, testable pattern for decoupling application behavior from request handling.
