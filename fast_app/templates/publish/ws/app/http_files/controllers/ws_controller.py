import asyncio

from quart import websocket

from fast_app.core.broadcasting import WebsocketEvent, redis_broadcast_client


async def receive_loop():
    while True:
        raw_message = await websocket.receive()
        ws_event = WebsocketEvent.model_validate_json(raw_message)
        # await handle(event)

async def send_loop():
    pubsub = redis_broadcast_client.pubsub()
    await pubsub.subscribe([])
    try:
        async for message in pubsub.listen():
            if message['type'] == 'message':
                await websocket.send(message['data'])
    finally:
        await pubsub.close()

async def handle_ws():
    await websocket.accept()
    if not await authenticate():
        await websocket.close(code=1008, reason='Authentication failed')

    await asyncio.gather(
        receive_loop(),
        send_loop(),
        return_exceptions=True
    )
