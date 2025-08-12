from typing import Optional

from fast_app.exceptions.http_exceptions import HttpException
from fast_app.utils.serialisation import get_exception_error_type


class AppException(Exception):
    def __init__(self,
        message: str,
        *,
        http_status_code: Optional[int] = None,
        error_type: Optional[str] = None,
        data: Optional[dict] = None
    ):
        """
        Universal exception, which can be converted to a HTTP response, if caught by the handle_exceptions_middleware.

        Args:
            message: The error message.
            http_status_code: The HTTP status code to return.
            error_type: The error type to return (if not provided, it will be inferred from the exception class name).
            data: The data to return.
        """
        self.message = message
        self.http_status_code = http_status_code
        self.error_type = error_type or get_exception_error_type(self)
        self.data = data
        super().__init__(message)

    def to_http_exception(self):
        return HttpException(status_code=self.http_status_code, error_type=self.error_type, message=self.message, data=self.data)

    def to_response(self):
        return self.to_http_exception().to_response()

class ValidationRuleException(ValueError):
    """
    Distinct validation error raised by schema ValidatorRules.

    This is intentionally different from Pydantic's ValidationError so callers
    can distinguish between field-shape/type errors (Pydantic) and post-parse
    rule errors (e.g., existence checks, cross-field constraints, DB lookups).
    """

    def __init__(
        self,
        message: str,
        *,
        loc: tuple[str, ...] | None = None,
        error_type: str = "value_error",
        errors: list[dict] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.loc = loc or tuple()
        self.error_type = error_type
        self.errors = errors

class DatabaseNotInitializedException(RuntimeError):
    def __init__(self):
        super().__init__("Database is not initialized.")

class EnvMissingException(ValueError):
    def __init__(self, env_name: str):
        super().__init__(f"[ENV MISSING] Missing required environment variable: `{env_name}`")

class EnvInvalidException(ValueError):
    def __init__(self, env_name: str, value: str = None, supported_values: list[str] = None):
        message = f"[ENV INVALID] Invalid environment variable: `{env_name}`"
        if value:
            message += f" (value: `{value}`) "
        if supported_values:
            message += f" (supported values: {', '.join(supported_values)})"
        super().__init__(message)