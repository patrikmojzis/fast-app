from typing import Optional, Dict, Type, List
import importlib
from fast_app import Event, EventListener

def autodiscover_events() -> Optional[Dict[Type[Event], List[Type[EventListener]]]]:
    """
    Autodiscover events configuration from app/event_provider.py.
    Loads `events` variable from the module.
    
    Returns:
        Dictionary of events to listeners mapping, or None if not found
    """
    try:
        event_provider_module = importlib.import_module("app.event_provider")
        
        if hasattr(event_provider_module, 'events'):
            events = getattr(event_provider_module, 'events')
            if isinstance(events, dict):
                print("🎯 Found event configuration in app.event_provider")
                return events
            else:
                print("⚠️ Found 'events' in app.event_provider but it's not a dict")
        else:
            print("📭 No 'events' found in app.event_provider")
            
    except ImportError:
        print("📁 No app/event_provider.py found, skipping event autodiscovery")
    
    return None
