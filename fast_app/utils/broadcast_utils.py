import os
from typing import TYPE_CHECKING

import redis.asyncio as redis

from fast_app.contracts.websocket_event import WebsocketEvent

if TYPE_CHECKING:
    from fast_app.contracts.broadcast_event import BroadcastEvent


redis_broadcast_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"), 
    port=int(os.getenv("REDIS_PORT", 6379)), 
    db=int(os.getenv("REDIS_BROADCAST_DB", 3))
)

async def convert_broadcast_event_to_websocket_event(event: 'BroadcastEvent') -> WebsocketEvent:
    """Transform broadcast data into a WebsocketEvent."""
    data = await event.broadcast_as()

    if isinstance(data, WebsocketEvent):
        return data
    
    event_type = event.get_event_type()
    
    if hasattr(data, "dump"):  # If is resource
        return WebsocketEvent(type=event_type, data=await data.dump())
    
    return WebsocketEvent(type=event_type, data=data)