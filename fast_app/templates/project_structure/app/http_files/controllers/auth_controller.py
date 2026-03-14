from app.http_files.resources.auth_resource import AuthResource
from app.http_files.schemas.auth_refresh_schema import AuthRefreshSchema
from app.models.auth import Auth
from app.models.user import User
from pymongo import ReturnDocument
from quart import g, Response

from fast_app import decode_token, now
from fast_app.core.jwt_auth import REFRESH_TOKEN_TYPE
from fast_app.exceptions import AuthException
from fast_app.exceptions.http_exceptions import UnauthorizedException


# async def login(data: AuthLoginSchema):
#     """
#     Login endpoint - creates a new refresh token for the user.
#     """
#     user = await login_user(**data.validated)
    
#     auth = await Auth.create({
#         'user_id': user.id,
#         # 'identifier': request.headers.get('X-Device-Id'),  # Optional custom device ID or login source
#     })
    
#     return AuthResource(auth)
    

async def refresh(data: AuthRefreshSchema):
    """
    Refresh token endpoint - exchanges refresh token for new access token.
    """
    try:
        decode_token(data.refresh_token, token_type=REFRESH_TOKEN_TYPE)
    except AuthException:
        raise UnauthorizedException()

    coll = await Auth.collection_cls()
    refresh_token_hash = Auth.hash_refresh_token(data.refresh_token)

    async def _consume_refresh_token(query: dict) -> dict | None:
        final_query = await Auth.query_modifier(query, "find_one", Auth.collection_name())
        return await coll.find_one_and_update(
            final_query,
            {
                '$set': {'is_revoked': True},
                '$currentDate': {'updated_at': True},
            },
            return_document=ReturnDocument.BEFORE,
        )

    token_filters = {
        'is_revoked': {"$ne": True},
        '$or': [
            {'expires_at': None},
            {'expires_at': {'$gt': now()}},
        ],
    }
    raw_auth = await _consume_refresh_token({
        'refresh_token_hash': refresh_token_hash,
        **token_filters,
    })
    if raw_auth is None:
        # One-way compatibility path for sessions issued before refresh_token_hash existed.
        raw_auth = await _consume_refresh_token({
            'refresh_token': data.refresh_token,
            **token_filters,
        })
    if not raw_auth:
        raise UnauthorizedException()

    auth = Auth(**raw_auth)
    new_auth = await Auth.create({
        'user_id': auth.user_id,
        # 'identifier': request.headers.get('X-Device-Id'),  # Optional custom device ID or login source
    })
    
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
