import json
import importlib
import asyncio
import os
import socketio
from typing import TYPE_CHECKING, AsyncGenerator, Any, Optional, Union

from fast_app.utils.broadcast_utils import (
    transform_broadcast_data,
    get_broadcast_ons,
)
from fast_app.decorators.deprecated_decorator import deprecated


if TYPE_CHECKING:
    from fast_app.contracts.broadcast_event import BroadcastEvent
    from fast_app.contracts.websocket_event import WebsocketEvent
    from quart import Websocket


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
    redis_url = f"redis://{os.getenv("REDIS_HOST", "localhost")}:{os.getenv("REDIS_PORT", 6379)}/{os.getenv("REDIS_SOCKETIO_DB", 11)}"
    mgr = socketio.AsyncRedisManager(redis_url)
    await asyncio.gather(*(mgr.emit(
        event.get_event_name(), 
        payload, 
        room=broadcast_on.get("room"), 
        namespace=broadcast_on.get("namespace")
        ) for broadcast_on in broadcast_ons))
    
    return True