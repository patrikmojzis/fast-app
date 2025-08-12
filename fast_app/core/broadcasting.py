import json
from typing import TYPE_CHECKING

from fast_app.contracts.broadcast_channel import BroadcastChannel
from fast_app.utils.broadcast_utils import (
    convert_broadcast_event_to_websocket_event,
    redis_broadcast_client,
)

if TYPE_CHECKING:
    from fast_app.contracts.broadcast_event import BroadcastEvent


async def publish_to_channel(channel_name: str, data: 'WebsocketEvent | dict[str, Any]') -> None:
    """Publish either a websocket event or a dictionary to a channel."""
    payload = data.model_dump_json() if hasattr(data, "model_dump_json") else json.dumps(data)
    await redis_broadcast_client.publish(channel_name, payload)


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
    await redis_broadcast_client.publish(channel_name, websocket_event.model_dump_json())
    
    return True
