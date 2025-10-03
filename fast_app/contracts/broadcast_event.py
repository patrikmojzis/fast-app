from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Optional, Union

from fast_app.utils.serialisation import pascal_case_to_snake_case, serialise, remove_suffix
from fast_app.contracts.event import Event

if TYPE_CHECKING:
    from fast_app.contracts.room import Room
    from fast_app.contracts.resource import Resource

class BroadcastEvent(Event):
    """
    Base class for all broadcast events.

    Define event data fields in pydantic way.
    """

    async def broadcast_on(self) -> Union[str, 'Room', list[Union[str, 'Room']]]:
        """
        Set the channel to broadcast the event on.
        """
        return remove_suffix(pascal_case_to_snake_case(self.__class__.__name__), "_event")

    async def broadcast_when(self) -> bool:
        """
        Add conditions if the event should broadcast.
        """
        return True

    async def broadcast_as(self) -> Optional[Union[dict, list, str, int, float, bool, 'Resource']]:
        """
        Modify how the event is broadcasted.
        """
        return self.model_dump()
