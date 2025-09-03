from typing import TYPE_CHECKING, List, Type, Tuple, Optional

from fast_app.application import Application

if TYPE_CHECKING:
    from fast_app.contracts.event import Event
    from fast_app.contracts.event_listener import EventListener


def get_event_listeners(event: 'Event') -> Tuple[Optional[List[Type['EventListener']]], str]:
    """
    Get listeners for an event and validate application state.
    
    Args:
        event: The event instance
        
    Returns:
        Tuple of (listeners_list, event_name) or (None, event_name) if invalid
    """
    app = Application()
    event_name = event.get_event_name()
    
    if not app.are_events_configured():
        print("⚠️ Application not configured for events")
        return None, event_name
    
    listeners = app.get_listeners_for_event(type(event))
    
    if not listeners:
        print(f"📭 No listeners registered for {event_name}")
        return None, event_name
        
    return listeners, event_name


async def process_event_listener(listener_class: Type['EventListener'], event_instance: 'Event') -> None:
    """
    Process a single event listener with proper error handling.
    
    Args:
        listener_class: The EventListener class to instantiate and run
        event_instance: The event instance to pass to the listener
    """
    app = Application()
    
    if not app.are_events_configured():
        print("⚠️ Application not configured for events, skipping listener processing")
        return
    
    listener_name = listener_class.__name__
    event_name = event_instance.get_event_name()
    
    try:
        # Instantiate and process the listener
        listener = listener_class()
        await listener.handle(event_instance)
        
        print(f"✅ Processed {listener_name} for {event_name}")
        
    except Exception as e:
        print(f"❌ Error processing {listener_name} for {event_name}: {e}")
        # Re-raise to maintain error propagation
        raise