import os
import socketio

from app.socketio.namespaces.global_namespace import GlobalNamespace
from app.modules.asgi.cors import get_cors_origins

def create_socketio_app() -> socketio.AsyncServer:
    sio = socketio.AsyncServer(
        async_mode="asgi",
        cors_allowed_origins=get_cors_origins(),
        client_manager=socketio.AsyncRedisManager(os.getenv("SIO_REDIS_URL","redis://localhost:6379/0"))
    )

    sio.register_namespace(GlobalNamespace())

    return sio