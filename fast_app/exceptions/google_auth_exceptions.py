"""Google authentication exceptions for fast-app package."""


class GoogleAuthError(Exception):
    """Base exception for Google authentication errors."""
    
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class GoogleServerError(GoogleAuthError):
    """Exception raised when communication with Google server fails."""
    
    def __init__(self, message: str = "Could not communicate with Google server") -> None:
        super().__init__(message)


class GoogleInvalidTokenError(GoogleAuthError):
    """Exception raised when Google access token is invalid."""
    
    def __init__(self, message: str = "Google access token is invalid") -> None:
        super().__init__(message)


class GoogleUnauthorizedError(GoogleAuthError):
    """Exception raised when Google access token is unauthorized."""
    
    def __init__(self, message: str = "Google access token is unauthorized") -> None:
        super().__init__(message)


class GoogleApiError(GoogleAuthError):
    """Exception raised when Google API returns an error."""
    
    def __init__(self, message: str = "Google API returned an error") -> None:
        super().__init__(message)