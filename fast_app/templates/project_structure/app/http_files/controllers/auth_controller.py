from datetime import datetime
from typing import Optional

from quart import request, g, jsonify, Response
from bson import ObjectId

from app.models.user import User
from app.models.auth import Auth
from app.http_files.middlewares.auth_middleware import protected_route
from fast_app.exceptions.http_exceptions import HttpException, UnauthorisedException
from app.http_files.schemas.auth_refresh_schema import AuthRefreshSchema
from fast_app.core.api import validate_request, get_client_ip
from app.http_files.resources.auth_resource import AuthResource


# async def login():
#     """
#     Login endpoint - creates a new refresh token for the user.
#     """
#     await validate_request(AuthLoginSchema)
#     user = await login_user(**g.validated)
    
#     auth = await Auth.create({
#         'user_id': user.id,
#         # 'identifier': request.headers.get('X-Device-Id'),  # Optional custom device ID or login source
#     })
    
#     return await AuthResource(auth).to_response()
    

async def refresh():
    """
    Refresh token endpoint - exchanges refresh token for new access token.
    """
    await validate_request(AuthRefreshSchema)

    auth = await Auth.find_one({'refresh_token': g.validated.get('refresh_token'), 'is_revoked': {"$ne": True}})
    if not auth:
        raise UnauthorisedException()
    
    new_auth = await Auth.create({
        'user_id': auth.user_id,
        # 'identifier': request.headers.get('X-Device-Id'),  # Optional custom device ID or login source
    })

    await auth.revoke()  # Revoke the old refresh token
    
    return await AuthResource(new_auth).to_response()


async def logout():
    """
    Logout endpoint - revokes the current refresh token.
    """
    await g.get('auth').revoke()

    return Response(status=204)


async def logout_all():
    """
    Logout from all devices - revokes all refresh tokens for the user.
    """
    await g.get('auth').revoke_all()

    return Response(status=204)


