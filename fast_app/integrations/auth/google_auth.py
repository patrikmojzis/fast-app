"""Google Sign In integration for fast-app package."""

import os
from typing import Any, Dict, Optional, TypedDict
import hashlib

import aiohttp

from fast_app.common.cache import Cache
from fast_app.exceptions.google_auth_exceptions import (
    GoogleApiError,
    GoogleInvalidTokenError,
    GoogleServerError,
    GoogleUnauthorizedError,
)
from fast_app.exceptions.common_exceptions import EnvMissingException


class GoogleUserInfo(TypedDict):
    """Type definition for Google user info data."""
    
    id: str  # Google user ID
    email: str  # User email
    verified_email: bool  # Email verification status
    name: Optional[str]  # Full name
    given_name: Optional[str]  # First name
    family_name: Optional[str]  # Last name
    picture: Optional[str]  # Profile picture URL
    locale: Optional[str]  # User locale


async def sign_in(access_token: str) -> GoogleUserInfo:
    """
    Authenticate user with Google Sign In using access token.
    
    Args:
        access_token: The Google access token to verify.
        
    Returns:
        GoogleUserInfo: The user information from Google.
        
    Raises:
        GoogleServerError: If communication with Google server fails.
        GoogleInvalidTokenError: If access token is invalid.
        GoogleUnauthorizedError: If access token is unauthorized.
        GoogleApiError: If Google API returns an error.
    """
    
    # Try to get user info from cache first
    cache_key = f"google_user_info_{hashlib.sha256(access_token.encode()).hexdigest()}"
    cached_user_info = await Cache.get(cache_key)
    
    if cached_user_info is not None:
        return GoogleUserInfo(cached_user_info)
    
    # Fetch user info from Google API
    user_info = await _get_google_user_info(access_token)
    
    # Cache the user info for 30 minutes
    await Cache.set(cache_key, user_info, 30)
    
    return GoogleUserInfo(user_info)


async def revoke(access_token: str) -> None:
    """
    Revoke Google access token.
    
    Args:
        access_token: The Google access token to revoke.
        
    Raises:
        GoogleServerError: If communication with Google server fails.
        GoogleApiError: If token revocation fails.
    """    
    async with aiohttp.ClientSession() as session:
        revoke_url = f"https://oauth2.googleapis.com/revoke?token={access_token}"
        
        async with session.post(revoke_url) as response:
            if response.status == 200:
                # Successfully revoked
                return
            elif response.status == 400:
                # Token was already invalid or revoked
                raise GoogleInvalidTokenError("Token is invalid or already revoked")
            else:
                error_text = await response.text()
                raise GoogleApiError(f"Could not revoke Google access token: {error_text}")


async def validate_token(access_token: str) -> Dict[str, Any]:
    """
    Validate Google access token and get token information.
    
    Args:
        access_token: The Google access token to validate.
        
    Returns:
        Dict[str, Any]: Token information including scope, audience, etc.
        
    Raises:
        EnvMissingException: If required environment variables are not configured.
        GoogleServerError: If communication with Google server fails.
        GoogleInvalidTokenError: If access token is invalid.
        GoogleApiError: If Google API returns an error.
    """
    if not os.getenv("GOOGLE_CLIENT_ID"):
        raise EnvMissingException("GOOGLE_CLIENT_ID")
    
    async with aiohttp.ClientSession() as session:
        tokeninfo_url = f"https://oauth2.googleapis.com/tokeninfo?access_token={access_token}"
        
        async with session.get(tokeninfo_url) as response:
            if response.status == 200:
                token_info = await response.json()
                
                # Verify the audience (client ID) matches our app
                client_id = os.getenv("GOOGLE_CLIENT_ID")
                if token_info.get("aud") != client_id:
                    raise GoogleUnauthorizedError("Token audience does not match client ID")
                
                return token_info
            elif response.status == 400:
                raise GoogleInvalidTokenError("Invalid access token")
            else:
                error_text = await response.text()
                raise GoogleServerError(f"Could not validate Google access token: {error_text}")


async def _get_google_user_info(access_token: str) -> Dict[str, Any]:
    """
    Get Google user information using access token.
    
    Args:
        access_token: The Google access token.
        
    Returns:
        Dict[str, Any]: The user information from Google.
        
    Raises:
        GoogleServerError: If communication with Google server fails.
        GoogleInvalidTokenError: If access token is invalid.
        GoogleUnauthorizedError: If access token is unauthorized.
        GoogleApiError: If Google API returns an error.
    """
    async with aiohttp.ClientSession() as session:
        headers = {'Authorization': f'Bearer {access_token}'}
        
        async with session.get(
            'https://www.googleapis.com/userinfo/v2/me',
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 401:
                raise GoogleUnauthorizedError("Google access token is unauthorized")
            elif response.status == 400:
                raise GoogleInvalidTokenError("Google access token is invalid")
            else:
                error_text = await response.text()
                raise GoogleServerError(f"Unsuccessful request to Google API: {error_text}")