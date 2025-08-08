import json
import pytest

from fast_app.core.broadcasting import broadcast
from fast_app.contracts.broadcast_event import BroadcastEvent
from fast_app.utils.broadcast_utils import redis_broadcast_client


class SampleBroadcast(BroadcastEvent):
    msg: str
    async def broadcast_on(self):
        return "test-channel"


@pytest.mark.asyncio
async def test_broadcast_websocket_event():
    pubsub = redis_broadcast_client.pubsub()
    await pubsub.subscribe("test-channel")
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
        await pubsub.unsubscribe("test-channel")
        await pubsub.aclose()
