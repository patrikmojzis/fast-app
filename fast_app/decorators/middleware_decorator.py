from typing import Type, Callable, Union
from functools import wraps
import inspect
from fast_app.contracts.middleware import Middleware


def middleware(middleware_class_or_instance: Union[Type[Middleware], Middleware]):
    """
    Decorator to apply a middleware class or instance to a controller method
    
    Usage:
        @middleware(EtagMiddleware)  # Class
        async def my_controller_method():
            return jsonify({"data": "example"})
            
        @middleware(EtagMiddleware())  # Instance
        async def my_controller_method():
            return jsonify({"data": "example"})
    """
    def decorator(func: Callable) -> Callable:
        # Check if it's a class or instance
        if inspect.isclass(middleware_class_or_instance):
            # It's a class, check inheritance and instantiate
            if not issubclass(middleware_class_or_instance, Middleware):
                raise TypeError(f"{middleware_class_or_instance} must inherit from Middleware")
            middleware_instance = middleware_class_or_instance()
        else:
            # It's an instance, check if it's the right type
            if not isinstance(middleware_class_or_instance, Middleware):
                raise TypeError(f"{middleware_class_or_instance} must be an instance of Middleware")
            middleware_instance = middleware_class_or_instance
        
        return middleware_instance(func)
    
    return decorator