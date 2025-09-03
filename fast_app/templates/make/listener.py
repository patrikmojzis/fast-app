from typing import TYPE_CHECKING
from fast_app import EventListener

if TYPE_CHECKING:
    from fast_app import Event


class NewClass(EventListener):

    async def handle(self, event: 'Event') -> None:
        pass
