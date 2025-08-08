from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from typing import TYPE_CHECKING, Any, Optional
import redis.asyncio as redis
import os
import time
from fast_app.contracts.broadcast_channel import BroadcastChannel
from fast_app.utils.broadcast_utils import (
    convert_broadcast_event_to_websocket_event,
    redis_broadcast_client,
)

if TYPE_CHECKING:
    from fast_app.contracts.broadcast_event import BroadcastEvent
    from fast_app.contracts.websocket_event import WebsocketEvent


async def broadcast_websocket_event(channel_name: str, websocket_event: 'WebsocketEvent') -> bool:
    """
    Direct method to broadcast a websocket event.
    
    Returns True if broadcast was successful, False otherwise.
    """
    await redis_broadcast_client.publish(
        channel_name, 
        websocket_event.model_dump_json()
    )


async def broadcast(event: 'BroadcastEvent') -> bool:
    """
    Broadcast an event through the configured channel.
    
    Returns True if broadcast was successful, False otherwise.
    """
    # Guard: Should we broadcast?
    if not await event.broadcast_when():
        return False
    
    # Get the channel
    channel = await event.broadcast_on()
    if not channel:
        return False
    
    # Verify channel permissions
    if isinstance(channel, BroadcastChannel) and not await channel.can_broadcast():
        return False
    
    # Prepare the event data
    websocket_event = await convert_broadcast_event_to_websocket_event(event)
    
    # Get channel name
    channel_name = (
        await channel.get_channel_name() 
        if isinstance(channel, BroadcastChannel) 
        else channel
    )
    
    # Publish to Redis
    await broadcast_websocket_event(channel_name, websocket_event)
    
    return True
