from functools import wraps

from fast_app.core.stopwatch import Stopwatch

def stopwatch(func=None, *, logger=None):
    """
    Decorator that times the execution of a function using the Stopwatch class.
    
    Args:
        func: The function to be decorated (when used as @stopwatch)
        logger: Optional logger instance for logging timing results
    
    Example usage:
        @stopwatch
        def my_function():
            # Code to time
            pass
            
        # Or with logger
        @stopwatch(logger=my_logger)
        def my_function():
            # Code to time
            pass
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            sw = Stopwatch(logger=logger)
            try:
                result = f(*args, **kwargs)
                return result
            finally:
                sw.stop()
        return wrapper
    
    # Handle both @stopwatch and @stopwatch() syntax
    if func is None:
        return decorator
    else:
        return decorator(func)
