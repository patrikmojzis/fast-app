# Event configuration for the application
# This file defines the mapping between events and their listeners

from typing import TYPE_CHECKING, Dict, List, Type

if TYPE_CHECKING:
    from fast_app.event_base import Event
    from fast_app.event_listener_base import EventListener

# Define the events mapping
# Each event class can have multiple listeners
events: Dict[Type['Event'], List[Type['EventListener']]] = {
    # Example configuration:
    # UserRegisteredEvent: [
    #     SendWelcomeEmailListener,
    #     CreateUserProfileListener,
    # ],
}