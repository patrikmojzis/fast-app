import functools
import inspect
import warnings

def _deprecate_class(cls, message):
    """Helper function to deprecate a class."""
    original_init = cls.__init__

    @functools.wraps(original_init)
    def new_init(self, *args, **kwargs):
        warnings.warn(
            f"Instantiating deprecated class {cls.__name__}.{message}",
            category=DeprecationWarning,
            stacklevel=2
        )
        original_init(self, *args, **kwargs)

    cls.__init__ = new_init
    return cls

def deprecated(reason=None):
    """
    Decorator to mark functions, methods, or classes as deprecated.

    Usage:
    @deprecated  # No message, no parentheses
    @deprecated()  # No message
    @deprecated("Use NewClass instead.")  # With message
    """
    # Allow using @deprecated without parentheses
    if callable(reason) and not isinstance(reason, type):
        # @deprecated used without arguments on a function
        return deprecated()(reason)
    elif isinstance(reason, type):
        # @deprecated used without arguments on a class
        return _deprecate_class(reason, None)

    def decorator(obj):
        message = f" {reason}" if reason else ""

        if isinstance(obj, type):
            # It's a class
            return _deprecate_class(obj, message)
        elif inspect.iscoroutinefunction(obj):
            # It's an async function
            @functools.wraps(obj)
            async def async_wrapper(*args, **kwargs):
                warnings.warn(
                    f"Call to deprecated function {obj.__name__}.{message}",
                    category=DeprecationWarning,
                    stacklevel=2
                )
                return await obj(*args, **kwargs)

            return async_wrapper
        else:
            # It's a regular function
            @functools.wraps(obj)
            def wrapper(*args, **kwargs):
                warnings.warn(
                    f"Call to deprecated function {obj.__name__}.{message}",
                    category=DeprecationWarning,
                    stacklevel=2
                )
                return obj(*args, **kwargs)

            return wrapper

    return decorator