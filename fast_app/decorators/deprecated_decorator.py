import functools
import inspect
import warnings
from typing_extensions import deprecated as typing_deprecated

def _deprecate_class(cls, message):
    """Helper function to deprecate a class."""
    # Use typing_extensions.deprecated for type checking support
    deprecated_cls = typing_deprecated(message or "This class is deprecated")(cls)
    
    # Also add runtime warning on instantiation
    original_init = cls.__init__

    @functools.wraps(original_init)
    def new_init(self, *args, **kwargs):
        warnings.warn(
            f"Instantiating deprecated class {cls.__name__}.{message}",
            category=DeprecationWarning,
            stacklevel=2
        )
        original_init(self, *args, **kwargs)

    deprecated_cls.__init__ = new_init
    return deprecated_cls

def deprecated(reason=None):
    """
    Decorator to mark functions, methods, or classes as deprecated.
    
    This decorator:
    1. Emits runtime warnings when deprecated objects are used
    2. Adds type checking support via typing_extensions.deprecated

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
            # It's an async function - use typing_extensions.deprecated for type checking
            deprecated_func = typing_deprecated(reason or "This function is deprecated")(obj)
            
            # Also add runtime warning
            @functools.wraps(obj)
            async def async_wrapper(*args, **kwargs):
                warnings.warn(
                    f"Call to deprecated function {obj.__name__}.{message}",
                    category=DeprecationWarning,
                    stacklevel=2
                )
                return await obj(*args, **kwargs)

            # Replace the deprecated function with our wrapper that has both type checking and runtime warnings
            async_wrapper.__deprecated__ = deprecated_func.__deprecated__
            return async_wrapper
        else:
            # It's a regular function - use typing_extensions.deprecated for type checking
            deprecated_func = typing_deprecated(reason or "This function is deprecated")(obj)
            
            # Also add runtime warning
            @functools.wraps(obj)
            def wrapper(*args, **kwargs):
                warnings.warn(
                    f"Call to deprecated function {obj.__name__}.{message}",
                    category=DeprecationWarning,
                    stacklevel=2
                )
                return obj(*args, **kwargs)

            # Replace the deprecated function with our wrapper that has both type checking and runtime warnings
            wrapper.__deprecated__ = deprecated_func.__deprecated__
            return wrapper

    return decorator