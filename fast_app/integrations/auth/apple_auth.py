"""Apple Sign In integration for fast-app package."""

import os
import time
from datetime import datetime
from typing import Any, Dict, Optional, TypedDict

import aiohttp
import jwt
import jwt.algorithms

from fast_app.common.cache import Cache
from fast_app.exceptions.apple_auth_exceptions import (
    AppleInvalidSignatureError,
    ApplePublicKeyNotFoundError,
    AppleServerError,
    AppleTokenExpiredError,
    AppleTokenRevokeError,
)
from fast_app.exceptions.common_exceptions import EnvMissingException


class AppleJWTDecoded(TypedDict):
    """Type definition for Apple JWT decoded data."""
    
    iss: str  # Issuer
    aud: str  # Audience  
    exp: int  # Expiration time
    iat: int  # Issued at
    sub: str  # Subject (user identifier)
    email: str  # User email
    email_verified: Optional[str]  # Email verification status
    is_private_email: Optional[str]  # Private email indicator
    auth_time: Optional[int]  # Authentication time
    nonce_supported: Optional[bool]  # Nonce support indicator


def _check_apple_env_config() -> None:
    """
    Check if required Apple environment variables are configured.
    
    Raises:
        EnvMissingException: If any required environment variable is missing.
    """
    required_vars = [
        "APPLE_CLIENT_ID",
        "APPLE_TEAM_ID", 
        "APPLE_KEY_ID",
        "APPLE_P8_KEY"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise EnvMissingException(
            f"Missing required Apple environment variables: {', '.join(missing_vars)}"
        )

async def _generate_jwt() -> str:
    """
    Generate a JWT for Apple API authentication.
    
    Returns:
        str: The generated JWT token.
        
    Raises:
        EnvMissingException: If required environment variables are not configured.
    """
    _check_apple_env_config()
    
    payload = {
        'iss': os.getenv("APPLE_TEAM_ID"),
        'iat': int(time.time()) - 10,
        'exp': int(time.time()) + 120,
        'aud': 'https://appleid.apple.com',
        'sub': os.getenv("APPLE_CLIENT_ID")
    }
    
    return jwt.encode(
        payload,
        os.getenv("APPLE_P8_KEY"),
        algorithm='ES256',
        headers={'kid': os.getenv("APPLE_KEY_ID")}
    )

async def _get_apple_public_keys() -> Dict[str, Any]:
    """
    Get Apple public keys from cache or fetch from Apple server.
    
    Returns:
        Dict[str, Any]: The Apple public keys.
        
    Raises:
        AppleServerError: If communication with Apple server fails and keys are not cached.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://appleid.apple.com/auth/keys') as response:
                if response.status == 200:
                    keys = await response.json()
                    await Cache.set('apple_auth_keys', keys, 1440)  # Cache for 24 hours
                    return keys
                else:
                    raise AppleServerError(f"Apple server returned status {response.status}")
    except Exception as e:
        # If we can't fetch keys, try to get from cache
        if await Cache.exists('apple_auth_keys'):
            keys = await Cache.get('apple_auth_keys')
            if keys is not None:
                return keys
        
        # If no cached keys and we can't fetch new ones, raise the original error
        if isinstance(e, AppleServerError):
            raise e
        else:
            raise AppleServerError(f"Could not communicate with Apple server: {str(e)}")


async def sign_in(identity_token: str) -> AppleJWTDecoded:
    """
    Authenticate user with Apple Sign In.
    
    Args:
        identity_token: The Apple identity token to verify.
        
    Returns:
        AppleJWTDecoded: The decoded JWT data from Apple.
        
    Raises:
        EnvMissingException: If required environment variables are not configured.
        AppleServerError: If communication with Apple server fails.
        ApplePublicKeyNotFoundError: If Apple public key is not found.
        AppleInvalidSignatureError: If JWT signature is invalid.
        AppleTokenExpiredError: If JWT token has expired.
    """
    _check_apple_env_config()
    
    # Try to get Apple public keys from cache or fetch from Apple
    keys = await _get_apple_public_keys()
    
    # Find the matching public key
    token_header = jwt.get_unverified_header(identity_token)
    public_key = None
    
    for key in keys['keys']:
        if key['kid'] == token_header['kid']:
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
            break
    
    if public_key is None:
        raise ApplePublicKeyNotFoundError()
    
    # Decode and verify the JWT
    try:
        jwt_decoded: Dict[str, Any] = jwt.decode(
            identity_token, 
            public_key, 
            algorithms=['RS256'], 
            audience=os.getenv("APPLE_CLIENT_ID")
        )
    except jwt.exceptions.InvalidSignatureError:
        raise AppleInvalidSignatureError()
    
    # Check if token has expired
    expired_date = datetime.fromtimestamp(jwt_decoded['exp'])
    if expired_date < datetime.now():
        raise AppleTokenExpiredError()
    
    return AppleJWTDecoded(jwt_decoded)


async def revoke(authorization_code: str) -> None:
    """
    Revoke Apple access token.
    
    Args:
        authorization_code: The authorization code to revoke.
        
    Raises:
        EnvMissingException: If required environment variables are not configured.
        AppleTokenRevokeError: If token revocation fails.
    """
    _check_apple_env_config()
    
    client_secret = await _generate_jwt()
    
    async with aiohttp.ClientSession() as session:
        # Get access token
        token_data = {
            'client_id': os.getenv("APPLE_CLIENT_ID"),
            'client_secret': client_secret,
            'code': authorization_code,
            'grant_type': 'authorization_code',
        }
        
        async with session.post('https://appleid.apple.com/auth/token', data=token_data) as response:
            if response.status != 200:
                error_text = await response.text()
                raise AppleTokenRevokeError(f"Could not get Apple access token: {error_text}")
            
            token_response = await response.json()
        
        # Revoke the access token
        revoke_data = {
            'client_id': os.getenv("APPLE_CLIENT_ID"),
            'client_secret': client_secret,
            'token': token_response['access_token'],
            'token_type_hint': 'access_token'
        }
        
        async with session.post('https://appleid.apple.com/auth/revoke', data=revoke_data) as response:
            if response.status != 200:
                error_text = await response.text()
                raise AppleTokenRevokeError(f"Could not revoke Apple access token: {error_text}")