from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Union

from fast_app.utils.serialisation import serialise
from fast_app.contracts.event import Event

if TYPE_CHECKING:
    from fast_app.contracts.broadcast_channel import BroadcastChannel
    from fast_app.contracts.websocket_event import WebsocketEvent
    from fast_app.contracts.resource import Resource

class BroadcastEvent(Event):
    """
    Base class for all broadcast events.

    Define event data fields in pydantic way.
    """

    @abstractmethod
    async def broadcast_on(self, *args, **kwargs) -> Union[str, 'BroadcastChannel']:
        """
        Get the channel to broadcast the event on.
        """
        pass

    async def broadcast_when(self, *args, **kwargs) -> bool:
        """
        Check if the event should be broadcast.
        """
        return True

    async def broadcast_as(self, *args, **kwargs) -> Union[dict, 'WebsocketEvent', 'Resource', Any]:
        """
        Get the data to broadcast.
        """
        return serialise(self.model_dump())
