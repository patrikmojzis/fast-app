from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fast_app.contracts.event import Event


class EventListener(ABC):
    """
    Base class for all event listeners.
    Event listeners handle the processing of events.
    """
    
    @abstractmethod
    async def handle(self, event: 'Event') -> None:
        """
        Handle the event. This method must be implemented by subclasses.
        """
        pass