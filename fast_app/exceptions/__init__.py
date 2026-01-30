"""Custom exceptions for FastApp applications."""

from .apple_auth_exceptions import (
    AppleAuthError,
    AppleServerError,
    ApplePublicKeyNotFoundError,
    AppleInvalidSignatureError,
    AppleTokenExpiredError,
    AppleTokenRevokeError,
)
from .auth_exceptions import (
    AuthException,
    InvalidTokenTypeException,
    InvalidTokenException,
    TokenExpiredException,
)
from .common_exceptions import (
    AppException,
    ValidationRuleException,
    DatabaseNotInitializedException,
    EnvMissingException,
    EnvInvalidException,
)
from .google_auth_exceptions import (
    GoogleAuthError,
    GoogleServerError,
    GoogleInvalidTokenError,
    GoogleUnauthorizedError,
    GoogleApiError,
)
from .http_exceptions import (
    HttpException,
    UnauthorizedException,
    UnauthorisedException,
    ServerErrorException,
    UnprocessableEntityException,
    ForbiddenException,
    TooManyRequestsException,
    NotFoundException,
)
from .model_exceptions import (
    ModelException,
    ModelNotFoundException,
)

__all__ = [
    # apple
    "AppleAuthError",
    "AppleServerError",
    "ApplePublicKeyNotFoundError",
    "AppleInvalidSignatureError",
    "AppleTokenExpiredError",
    "AppleTokenRevokeError",
    # common
    "AppException",
    "ValidationRuleException",
    "DatabaseNotInitializedException",
    "EnvMissingException",
    "EnvInvalidException",
    # google
    "GoogleAuthError",
    "GoogleServerError",
    "GoogleInvalidTokenError",
    "GoogleUnauthorizedError",
    "GoogleApiError",
    # http
    "HttpException",
    "UnauthorizedException",
    "UnauthorisedException",
    "ServerErrorException",
    "UnprocessableEntityException",
    "ForbiddenException",
    "TooManyRequestsException",
    "NotFoundException",
    # model
    "ModelException",
    "ModelNotFoundException",
    # auth
    "AuthException",
    "InvalidTokenTypeException",
    "InvalidTokenException",
    "TokenExpiredException",
]
