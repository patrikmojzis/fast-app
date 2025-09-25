import asyncio
from datetime import datetime
from typing import Any, Callable, Awaitable

from app.models.auth import Auth
from bson import ObjectId
from quart import g

from fast_app import (
    Middleware,
    get_bearer_auth_token,
    decode_token,
    ACCESS_TOKEN_TYPE,
)
from fast_app.exceptions import AuthException, UnauthorisedException


class AuthMiddleware(Middleware):
    """Authenticate the user using JWT access tokens and save to g context"""

    async def handle(self, next_handler: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        # Get bearer token from request header
        token = get_bearer_auth_token()
        if not token:
            raise UnauthorisedException()

        # Decode and validate JWT access token
        try:
            payload = decode_token(token, token_type=ACCESS_TOKEN_TYPE)
        except AuthException:
            raise UnauthorisedException()

        # Find Auth by session ID
        auth = await Auth.find_one({'_id': ObjectId(payload.get("sid")), 'is_revoked': {"$ne": True}})
        if not auth:
            raise UnauthorisedException()
            
        # Get user from database
        user = await auth.user()
        if not user:
            raise UnauthorisedException()
            
        # Update last seen timestamp
        user, auth = await asyncio.gather(
            user.update({'last_seen_at': datetime.now()}),
            auth.update({'last_used_at': datetime.now()}),
        )
            
        # Store user and auth in g context
        g.user = user
        g.auth = auth
            
        return await next_handler(*args, **kwargs)
