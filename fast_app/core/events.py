from typing import TYPE_CHECKING

from fast_app.core.queue import queue
from fast_app.utils.event_utils import get_event_listeners, process_event_listener

if TYPE_CHECKING:
    from fast_app.contracts.event import Event


def dispatch(event: 'Event') -> None:
    """
    Dispatch an event to all its registered listeners via background queue.
    
    Args:
        event: The event instance to dispatch
    """
    listeners, event_name = get_event_listeners(event)
    
    if listeners is None:
        return
    
    print(f"🚀 Dispatching {event_name} to {len(listeners)} listener(s)")
    
    # Queue each listener for background processing
    for listener_class in listeners:
        queue(process_event_listener, listener_class, event)


async def dispatch_now(event: 'Event') -> None:
    """
    Dispatch an event to all its registered listeners immediately (synchronous).
    
    This is useful for events that need immediate processing or in testing scenarios.
    
    Args:
        event: The event instance to dispatch
    """
    listeners, event_name = get_event_listeners(event)
    
    if listeners is None:
        return
    
    print(f"⚡ Dispatching {event_name} immediately to {len(listeners)} listener(s)")
    
    # Process each listener immediately
    for listener_class in listeners:
        await process_event_listener(listener_class, event)