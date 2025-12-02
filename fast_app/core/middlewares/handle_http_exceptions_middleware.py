import logging
import os
from typing import Any, Callable, Awaitable

from fast_app.contracts.middleware import Middleware
from fast_app.exceptions import HttpException, ServerErrorException, ModelException
from fast_app.exceptions.common_exceptions import AppException


class HandleHttpExceptionsMiddleware(Middleware):
    """Middleware for handling exceptions for HTTP requests."""

    async def handle(self, next_handler: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        try:
            return await next_handler(*args, **kwargs)
        except ModelException as e:
            return HttpException(status_code=e.http_status_code, message=e.message).to_response()
        except HttpException as e:
            return e.to_response()
        except AppException as e:
            logging.exception("Application exception while handling request", exc_info=e)
            if os.getenv("ENV") == "debug":
                raise e

            return e.to_response()
        except Exception as e:
            logging.exception("Unhandled exception while handling request", exc_info=e)
            if os.getenv("ENV") == "debug":
                raise e

            return ServerErrorException().to_response()
