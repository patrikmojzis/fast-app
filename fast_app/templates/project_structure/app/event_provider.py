# Event configuration for the application
# This file defines the mapping between events and their listeners
#
# Useful commands:
# `fast-app make event <name>` to create a new event
# `fast-app make listener <name>` to create a new listener

from typing import TYPE_CHECKING, Dict, List, Type

if TYPE_CHECKING:
    from fast_app import Event
    from fast_app import EventListener

# Define the events mapping
# Each event class can have multiple listeners
events: Dict[Type['Event'], List[Type['EventListener']]] = {
    # Example configuration:
    # UserRegisteredEvent: [
    #     SendWelcomeEmailListener,
    #     CreateUserProfileListener,
    # ],
}