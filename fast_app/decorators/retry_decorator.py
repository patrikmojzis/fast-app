import asyncio
import functools
import time
from typing import List, Type, Union, Callable, Any, Awaitable


def retry(
    retryable_errors: List[Type[Exception]], 
    max_retries: int = 3, 
    delay: Union[int, float] = 1.0,
    backoff_multiplier: float = 2.0
) -> Callable:
    """
    Decorator for retrying function calls when specific exceptions occur.
    
    :param retryable_errors: List of exception types that should trigger a retry
    :param max_retries: Maximum number of retry attempts (default: 3)
    :param delay: Initial delay between retries in seconds (default: 1.0)
    :param backoff_multiplier: Multiplier for exponential backoff (default: 1.0 for no backoff)
    :return: Decorated function that retries on specified errors
    """
    def decorator(func: Callable) -> Callable:
        async def _execute_with_retry(executor_func: Callable[[], Awaitable[Any]]) -> Any:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await executor_func()
                except Exception as e:
                    last_exception = e
                    
                    if not any(isinstance(e, error_type) for error_type in retryable_errors):
                        raise
                    
                    if attempt < max_retries:
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff_multiplier
            
            raise last_exception

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            return await _execute_with_retry(lambda: func(*args, **kwargs))

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if not any(isinstance(e, error_type) for error_type in retryable_errors):
                        raise
                    
                    if attempt < max_retries:
                        time.sleep(current_delay)
                        current_delay *= backoff_multiplier
            
            raise last_exception

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator 