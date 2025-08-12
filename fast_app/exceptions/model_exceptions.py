from typing import Optional

from fast_app.exceptions.common_exceptions import AppException


class ModelException(AppException):
    def __init__(self,
        message: str,
        *,
        http_status_code: Optional[int] = None
    ):
        super().__init__(message, http_status_code=http_status_code)

class ModelNotFoundException(ModelException):
    def __init__(self, model_name: str):
        super().__init__(f"Model '{model_name}' not found", http_status_code=404)