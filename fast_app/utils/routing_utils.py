from typing import TYPE_CHECKING, Callable, List, Type

from quart import Quart

from fast_app.contracts.middleware import Middleware
from fast_app.core.middlewares.handle_exceptions_middleware import HandleExceptionsMiddleware
from fast_app.core.middlewares.model_binding_middleware import ModelBindingMiddleware
from fast_app.core.middlewares.schema_validation_middleware import SchemaValidationMiddleware
from fast_app.core.middlewares.resource_response_middleware import ResourceResponseMiddleware

if TYPE_CHECKING:
    from fast_app.contracts.route import Route

def apply_middleware_chain(handler: Callable, middlewares: list[Middleware | Type[Middleware] | Callable]) -> Callable:
    """Apply a chain of middleware classes to a handler"""
    if not middlewares:
        return handler
    
    wrapped_handler = handler
    for middleware in reversed(middlewares):  # Apply middlewares in reverse order so they execute in correct order
        resolved_middleware: Callable
        # Allow passing middleware classes, instances, or plain callables
        if isinstance(middleware, type) and issubclass(middleware, Middleware):
            resolved_middleware = middleware()  # type: ignore[call-arg]
        else:
            resolved_middleware = middleware  # type: ignore[assignment]

        if isinstance(resolved_middleware, Middleware) or callable(resolved_middleware):
            wrapped_handler = resolved_middleware(wrapped_handler)  # type: ignore[misc]
        else:
            raise ValueError("Middleware must be a Middleware subclass/instance or a callable")
    
    return wrapped_handler

def register_routes(app: Quart, routes: List['Route']) -> None:
    """Register routes with the Quart application (HTTP only)."""
    # Flatten all routes
    flattened_routes = []
    for route in routes:
        flattened_routes.extend(route.flatten())
    
    # Register each route with the app
    for route in flattened_routes:
        if route.handler is None:
            continue  # Skip group routes without handlers
            
        # Always add handle_exceptions as the first middleware, resource conversion as the last
        # Global middlewares order:
        # 1) HandleExceptionsMiddleware (first)
        # 2) ModelBindingMiddleware
        # 3) SchemaValidationMiddleware
        # 4) Route-specific middlewares (user-defined)
        # 5) ResourceResponseMiddleware (last)
        all_middlewares = [HandleExceptionsMiddleware, ModelBindingMiddleware, SchemaValidationMiddleware]
        if route.middlewares:
            all_middlewares.extend(route.middlewares)
        # Ensure ResourceResponseMiddleware runs last to convert Resource -> Response
        all_middlewares.append(ResourceResponseMiddleware)
        
        # Apply middleware chain to the handler
        wrapped_handler = apply_middleware_chain(route.handler, all_middlewares)
        
        # Generate a unique endpoint per method+path to avoid collisions in tests
        endpoint_name = f"{wrapped_handler.__name__}:{','.join(sorted(route.methods or []))}:{route.path}"
        app.add_url_rule(
            rule=route.path,
            endpoint=endpoint_name,
            view_func=wrapped_handler,
            methods=route.methods
        )
