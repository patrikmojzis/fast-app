from typing import TYPE_CHECKING, Callable, List, Type
from fast_app.contracts.middleware import Middleware
from fast_app.core.middlewares.handle_exceptions_middleware import HandleExceptionsMiddleware
from quart import Quart

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
    """Register routes with the Quart application (HTTP and WebSocket)."""
    # Flatten all routes
    flattened_routes = []
    for route in routes:
        flattened_routes.extend(route.flatten())
    
    # Register each route with the app
    for route in flattened_routes:
        if route.handler is None:
            continue  # Skip group routes without handlers
            
        # Always add handle_exceptions as the first middleware
        all_middlewares = [HandleExceptionsMiddleware]
        if route.middlewares:
            all_middlewares.extend(route.middlewares)
        
        # Apply middleware chain to the handler
        wrapped_handler = apply_middleware_chain(route.handler, all_middlewares)
        
        # Register the route with Quart (HTTP vs WS)
        if getattr(route, 'is_websocket', False):
            # Register websocket via decorator-style API to avoid relying on private add_* APIs
            app.websocket(route.path)(wrapped_handler)
        else:
            app.add_url_rule(
                rule=route.path,
                endpoint=None,  # Let Quart auto-generate endpoint names
                view_func=wrapped_handler,
                methods=route.methods
            )