import os
import inspect
from typing import Any, Callable, Awaitable
from functools import wraps

from quart import jsonify
from fast_app.common.middleware import Middleware
from fast_app.exceptions.http_exceptions import HttpException, ServerErrorException
from fast_app.exceptions.common_exceptions import AppException
from fast_app.exceptions.model_exceptions import ModelException


class HandleExceptionsMiddleware(Middleware):
    """Middleware for handling exceptions across the application"""
    
    async def handle(self, next_handler: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        try:
            return await next_handler(*args, **kwargs)
        except HttpException as e:
            return e.to_response()
        except AppException as e:
            return e.to_response()
        except Exception as e:
            if os.getenv("ENV") == "debug":
                raise e

            return ServerErrorException().to_response()
