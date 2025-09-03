import asyncio

from quart import websocket

from fast_app import redis_broadcast_client, WebsocketEvent, relay_broadcasts_to_websocket

async def receive_loop():
    while True:
        raw_message = await websocket.receive()
        ws_event = WebsocketEvent.model_validate_json(raw_message)
        # await handle(event)

async def handle_ws():
    await websocket.accept()
    if not await authenticate():
        await websocket.close(code=1008, reason='Authentication failed')

    await asyncio.gather(
        receive_loop(),
        relay_broadcasts_to_websocket(websocket, "your_channel_name"),  # relays events sent with fast_app.broadcast() to the websocket
        return_exceptions=True
    )
