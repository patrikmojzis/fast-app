from typing import TYPE_CHECKING, Union

from fast_app import BroadcastEvent

if TYPE_CHECKING:
    from fast_app import Room


class NewClass(BroadcastEvent):
    # Define event data fields in pydantic way
    # e.g.
    # name: str = Field(..., description="The name of the event")
    # description: str = Field(..., description="The description of the event")
    # ...
    # or define broadcast_as() 
    
    async def broadcast_on(self) -> Union[str, 'Room']:
        return 'room_name'


