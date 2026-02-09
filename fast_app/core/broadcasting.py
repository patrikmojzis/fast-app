import asyncio
from typing import TYPE_CHECKING

from fast_app.utils.broadcast_utils import (
    transform_broadcast_data,
    get_broadcast_ons,
)
from fast_app.utils.socketio_mgr_singleton import get_sio_mgr

if TYPE_CHECKING:
    from fast_app.contracts.broadcast_event import BroadcastEvent


async def broadcast(event: 'BroadcastEvent') -> bool:
    """
    Broadcast an event on the configured rooms.
    
    Returns True if broadcast was successful, False otherwise.
    """
    # Guard: Should we broadcast?
    if not await event.broadcast_when():
        return False
    
    # Get the channel and verify permissions
    broadcast_ons = await get_broadcast_ons(await event.broadcast_on())
    if not broadcast_ons:
        return False
    
    # Prepare the event data
    payload = await transform_broadcast_data(await event.broadcast_as())
    
    # Publish to Redis
    mgr = await get_sio_mgr()
    results = await asyncio.gather(*(mgr.emit(
        event.get_event_name(), 
        payload, 
        room=broadcast_on.get("room"), 
        namespace=broadcast_on.get("namespace")
        ) for broadcast_on in broadcast_ons),
        return_exceptions=True)

    if errors := [r for r in results if isinstance(r, Exception)]:
        raise ExceptionGroup("Socket.IO broadcast failed", errors)

    return True