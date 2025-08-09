import json
import pytest

from fast_app.core.broadcasting import broadcast, publish_to_channel
from fast_app.contracts.broadcast_event import BroadcastEvent
from fast_app.utils.broadcast_utils import redis_broadcast_client


class SampleBroadcast(BroadcastEvent):
    msg: str

    async def broadcast_on(self):
        return "broadcast-channel"


@pytest.mark.asyncio
async def test_broadcast_and_publish():
    # Test broadcasting of event object
    pubsub = redis_broadcast_client.pubsub()
    await pubsub.subscribe("broadcast-channel")
    try:
        await broadcast(SampleBroadcast(msg="hi"))
        message = None
        for _ in range(5):
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)
            if message:
                break
        assert message is not None
        payload = json.loads(message["data"])
        assert payload["data"]["msg"] == "hi"
    finally:
        await pubsub.unsubscribe("broadcast-channel")
        await pubsub.aclose()

    # Test publishing raw dict
    pubsub = redis_broadcast_client.pubsub()
    await pubsub.subscribe("direct-channel")
    try:
        await publish_to_channel("direct-channel", {"msg": "hello"})
        message = None
        for _ in range(5):
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)
            if message:
                break
        assert message is not None
        payload = json.loads(message["data"])
        assert payload["msg"] == "hello"
    finally:
        await pubsub.unsubscribe("direct-channel")
        await pubsub.aclose()
