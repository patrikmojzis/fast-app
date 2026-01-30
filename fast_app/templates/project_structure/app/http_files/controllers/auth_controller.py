from app.http_files.resources.auth_resource import AuthResource
from app.http_files.schemas.auth_refresh_schema import AuthRefreshSchema
from app.models.auth import Auth
from app.models.user import User
from quart import g, Response

from fast_app.exceptions.http_exceptions import UnauthorizedException


# async def login(data: AuthLoginSchema):
#     """
#     Login endpoint - creates a new refresh token for the user.
#     """
#     user = await login_user(**g.validated)
    
#     auth = await Auth.create({
#         'user_id': user.id,
#         # 'identifier': request.headers.get('X-Device-Id'),  # Optional custom device ID or login source
#     })
    
#     return AuthResource(auth)
    

async def refresh(data: AuthRefreshSchema):
    """
    Refresh token endpoint - exchanges refresh token for new access token.
    """
    auth = await Auth.find_one({'refresh_token': data.refresh_token, 'is_revoked': {"$ne": True}})
    if not auth:
        raise UnauthorizedException()
    
    new_auth = await Auth.create({
        'user_id': auth.user_id,
        # 'identifier': request.headers.get('X-Device-Id'),  # Optional custom device ID or login source
    })

    await auth.revoke()  # Revoke the old refresh token
    
    return AuthResource(new_auth)


async def logout():
    """
    Logout endpoint - revokes the current refresh token.
    """
    await g.auth.revoke()

    return Response(status=204)


async def logout_all():
    """
    Logout from all devices - revokes all refresh tokens for the user.
    """
    await g.auth.revoke_all()

    return Response(status=204)

