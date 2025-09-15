from socketio.exceptions import ConnectionRefusedError
from fast_app import (
    Middleware,
    get_bearer_auth_token,
    decode_token,
    ACCESS_TOKEN_TYPE,
)
from fast_app.exceptions import AuthException, UnauthorisedException
from app.models.auth import Auth
from bson import ObjectId
from datetime import datetime
import asyncio
from socketio import AsyncServer, AsyncNamespace

async def authenticate(sio: AsyncServer | AsyncNamespace, sid: str, environ: dict, auth_headers: dict) -> None:
    access_token = auth_headers.get("token")
    if not access_token:
        raise ConnectionRefusedError("No access token provided")

    try:
        payload = decode_token(access_token, token_type=ACCESS_TOKEN_TYPE)
    except AuthException:
        raise ConnectionRefusedError("Invalid access token")

    auth = await Auth.find_one({'_id': ObjectId(payload.get("sid")), 'is_revoked': {"$ne": True}})
    if not auth:
        raise ConnectionRefusedError("Invalid access token")
    
    user = await auth.user()
    if not user:
        raise ConnectionRefusedError("Invalid access token")
    
    user, auth = await asyncio.gather(
        user.update({'last_seen_at': datetime.now()}),
        auth.update({'last_used_at': datetime.now()}),
    )

    # Save into the GLOBAL session (accessible from server handlers),
    # and ensure we don't overwrite by saving both keys at once.
    server = sio.server if isinstance(sio, AsyncNamespace) else sio
    await server.save_session(sid, {"user": user, "auth": auth})