"""Authentication exceptions for fast-app package."""


class AppleAuthError(Exception):
    """Base exception for Apple authentication errors."""
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AppleServerError(AppleAuthError):
    """Exception raised when communication with Apple server fails."""
    
    def __init__(self, message: str = "Could not communicate with Apple server") -> None:
        super().__init__(message)


class ApplePublicKeyNotFoundError(AppleAuthError):
    """Exception raised when Apple public key is not found."""
    
    def __init__(self, message: str = "Apple public key not found") -> None:
        super().__init__(message)


class AppleInvalidSignatureError(AppleAuthError):
    """Exception raised when Apple JWT signature is invalid."""
    
    def __init__(self, message: str = "Apple JWT signature is invalid") -> None:
        super().__init__(message)


class AppleTokenExpiredError(AppleAuthError):
    """Exception raised when Apple JWT token has expired."""
    
    def __init__(self, message: str = "Apple JWT token has expired") -> None:
        super().__init__(message)


class AppleTokenRevokeError(AppleAuthError):
    """Exception raised when Apple token revocation fails."""
    
    def __init__(self, message: str = "Could not revoke Apple access token") -> None:
        super().__init__(message)