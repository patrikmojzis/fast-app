from typing import Optional
from quart import jsonify
from fast_app.utils.serialisation import serialise, get_exception_error_type


class HttpException(Exception):
    def __init__(self, status_code, *, error_type=None, message=None, data=None):
        super().__init__(message)
        self._message = message
        self._error_type = error_type or get_exception_error_type(self)
        self._status_code = status_code
        self._data = data

    def dict(self):
        return {
            "error_type": self._error_type,
            "message": self._message,
            "data": self._data
        }

    @property
    def status_code(self):
        return self._status_code

    @property
    def error_type(self):
        return self._error_type

    def to_response(self):
        return jsonify(serialise(self.dict())), self.status_code

class UnauthorisedException(HttpException):
    def __init__(self, **kwargs):
        super().__init__(
            status_code=401,
            **kwargs
        )

class ServerErrorException(HttpException):
    def __init__(self, **kwargs):
        super().__init__(
            status_code=500,
            **kwargs
        )

class UnprocessableEntityException(HttpException):
    def __init__(self, **kwargs):
        super().__init__(
            status_code=422,
            **kwargs
        )

class ForbiddenException(HttpException):
    def __init__(self,  **kwargs):
        super().__init__(
            status_code=403,
            **kwargs
        )

class TooManyRequestsException(HttpException):
    def __init__(self, **kwargs):
        super().__init__(
            status_code=429,
            **kwargs
        )

class NotFoundException(HttpException):
    def __init__(self, **kwargs):
        super().__init__(
            status_code=404,
            **kwargs
        )