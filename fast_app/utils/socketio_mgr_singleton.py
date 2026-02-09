import asyncio
import os
from typing import Optional

import socketio

_redis_mgr: Optional[socketio.AsyncRedisManager] = None
_mgr_lock = asyncio.Lock()

def _redis_url() -> str:
    return os.getenv("REDIS_SOCKETIO_URL", "redis://localhost:6379/14")

async def get_sio_mgr() -> socketio.AsyncRedisManager:
    global _redis_mgr
    if _redis_mgr is not None:
        return _redis_mgr
    async with _mgr_lock:
        if _redis_mgr is None:
            _redis_mgr = socketio.AsyncRedisManager(_redis_url())
    return _redis_mgr