import os
import jwt
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, TypedDict, Literal
from bson import ObjectId

from fast_app.exceptions.common_exceptions import EnvMissingException
from fast_app.exceptions.auth_exceptions import InvalidTokenTypeException, TokenExpiredException, InvalidTokenException

# Token types
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"

# Token lifetimes (in seconds)
ACCESS_TOKEN_LIFETIME = int(os.getenv("ACCESS_TOKEN_LIFETIME", 60 * 15))  # 15 minutes
REFRESH_TOKEN_LIFETIME = int(os.getenv("REFRESH_TOKEN_LIFETIME", 60 * 60 * 24 * 7))  # 7 days
    
# JWT Algorithm
ALGORITHM = os.getenv("AUTH_JWT_ALGORITHM", "HS256")

class RefreshToken(TypedDict):
    sub: str | ObjectId  # User ID
    metadata: Optional[Dict[str, Any]]
    token_type: Literal[REFRESH_TOKEN_TYPE]
    iat: int
    exp: int

class AccessToken(TypedDict):
    sub: str | ObjectId  # User ID
    sid: str | ObjectId  # Auth ID
    metadata: Optional[Dict[str, Any]]
    token_type: Literal[ACCESS_TOKEN_TYPE]   
    iat: int
    exp: int

def _validate_env():
    if not os.getenv("SECRET_KEY"):
        raise EnvMissingException("SECRET_KEY")

def create_access_token(sub: str | ObjectId, sid: str | ObjectId, metadata: Dict[str, Any] = None) -> str:
    """
    Create a JWT access token for a user.
    
    Args:
        user_data: Dictionary containing user information
        
    Returns:
        JWT access token string
    """
    _validate_env()

    now = datetime.now(timezone.utc)
    
    payload: AccessToken = {
        "sub": str(sub),
        "sid": str(sid),
        "metadata": metadata,
        "token_type": ACCESS_TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ACCESS_TOKEN_LIFETIME)).timestamp()),
    }
    
    return jwt.encode(payload, os.getenv("SECRET_KEY"), algorithm=ALGORITHM)


def create_refresh_token(sub: str | ObjectId, metadata: Dict[str, Any] = None) -> str:
    """
    Create a JWT refresh token for a user.
    
    Args:
        user_id: User ID
        
    Returns:
        JWT refresh token string
    """
    _validate_env()

    now = datetime.now(timezone.utc)
    
    payload: RefreshToken = {
        "sub": str(sub),
        "metadata": metadata,
        "token_type": REFRESH_TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=REFRESH_TOKEN_LIFETIME)).timestamp()),
    }
    
    return jwt.encode(payload, os.getenv("SECRET_KEY"), algorithm=ALGORITHM)


def decode_token(token: str, token_type: Optional[Literal[ACCESS_TOKEN_TYPE, REFRESH_TOKEN_TYPE]] = None) -> AccessToken | RefreshToken:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT token string
        token_type: Expected token type (access/refresh), optional
        
    Returns:
        Decoded token payload
        
    Raises:
        InvalidTokenTypeException: If token type does not match the expected type
        TokenExpiredException: If token has expired
        InvalidTokenException: If token is invalid or malformed
    """
    _validate_env()

    try:
        payload = jwt.decode(
            token, 
            os.getenv("SECRET_KEY"), 
            algorithms=[ALGORITHM]
        )
        
        if token_type and payload.get("token_type") != token_type:
            raise InvalidTokenTypeException()
        
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenExpiredException()
    except jwt.InvalidTokenError:
        raise InvalidTokenException()