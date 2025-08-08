from fast_app.exceptions.common_exceptions import AppException


class AuthException(AppException):
    def __init__(self, message: str):
        super().__init__(message, http_status_code=401)


class InvalidTokenTypeException(AuthException):
    def __init__(self, message: str = "Invalid token type") -> None:
        super().__init__(message)


class InvalidTokenException(AuthException):
    def __init__(self, message: str = "Invalid token") -> None:
        super().__init__(message)


class TokenExpiredException(AuthException):
    def __init__(self, message: str = "Token has expired") -> None:
        super().__init__(message)