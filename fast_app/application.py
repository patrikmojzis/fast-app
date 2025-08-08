from typing import Any, Dict, List, Type, TYPE_CHECKING

from fast_app.decorators.singleton_decorator import singleton

if TYPE_CHECKING:
    from fast_app import Event
    from fast_app.event_listener_base import EventListener


@singleton
class Application:
    """
    Singleton application container that holds event configuration and other app state.
    This serves as the central registry for events and their listeners.
    """
    
    def __init__(self):
        """Initialize the application container."""
        self._event_registry: Dict[Type['Event'], List[Type['EventListener']]] = {}
        self._are_events_configured = False
        self._boot_args: Dict[str, Any] = {}
    
    def configure_events(self, events: Dict[Type['Event'], List[Type['EventListener']]]) -> None:
        """
        Configure the event registry with event-to-listeners mappings.
        
        Args:
            events: Dictionary mapping Event classes to lists of EventListener classes
        """
        self._event_registry = events
        self._are_events_configured = True
        
        # Log configuration
        total_listeners = sum(len(listeners) for listeners in events.values())
        print(f"🎯 Configured {len(events)} event(s) with {total_listeners} listener(s)")
        
        for event_class, listeners in events.items():
            listener_names = [listener.__name__ for listener in listeners]
            print(f"   {event_class.__name__} → {', '.join(listener_names)}")
    
    def get_listeners_for_event(self, event_class: Type['Event']) -> List[Type['EventListener']]:
        """
        Get all listeners registered for a specific event class.
        
        Args:
            event_class: The event class to get listeners for
            
        Returns:
            List of EventListener classes
        """
        return self._event_registry.get(event_class, [])
    
    def are_events_configured(self) -> bool:
        """Check if the application has been configured with events."""
        return self._are_events_configured
    
    def get_all_events(self) -> Dict[Type['Event'], List[Type['EventListener']]]:
        """Get the complete event registry."""
        return self._event_registry.copy()
    
    def reset(self) -> None:
        """Reset the application state (useful for testing)."""
        self._event_registry.clear()
        self._boot_args.clear()
        self._are_events_configured = False

    def set_boot_args(self, **kwargs) -> None:
        """Set the boot arguments for the application."""
        self._boot_args = kwargs

    def get_boot_args(self) -> Dict[str, Any]:
        """Get the boot arguments for the application."""
        return self._boot_args

    def is_booted(self) -> bool:
        """Check if the application has been booted."""
        return len(self._boot_args.keys()) > 0