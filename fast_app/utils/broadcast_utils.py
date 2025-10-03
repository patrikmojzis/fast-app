import os
import json
from typing import TYPE_CHECKING, Optional, Literal, Any, Union, TypedDict
import importlib

import redis.asyncio as redis

from fast_app.contracts.resource import Resource
from fast_app.utils.serialisation import serialise    
from fast_app.contracts.room import Room


async def transform_broadcast_data(data: Any) -> dict:
    """Transform broadcast data from Resource or BaseModel, otherwise return the data as is."""  
    if isinstance(data, Resource):  
        return await data.dump()

    if hasattr(data, "model_dump"):
        return data.model_dump()
    
    return data


class BroadcastOn(TypedDict):
    room: str
    namespace: Optional[str] = None

async def get_broadcast_ons(room: Union[str, 'Room', list[Union[str, 'Room']]]) -> list[BroadcastOn]:
    items = room if isinstance(room, list) else [room]
    broadcast_ons: list[BroadcastOn] = []

    for item in items:
        if isinstance(item, str):
            broadcast_ons.append({"room": item})
        else:
            broadcast_ons.append({"room": item.get_room_name(), "namespace": item.namespace})
    
    return broadcast_ons