from typing import TYPE_CHECKING, Callable, List, Type, cast

from quart import Quart

from fast_app.contracts.middleware import Middleware
from fast_app.core.middlewares.handle_exceptions_middleware import HandleExceptionsMiddleware
from fast_app.core.middlewares.model_binding_middleware import ModelBindingMiddleware
from fast_app.core.middlewares.resource_response_middleware import ResourceResponseMiddleware
from fast_app.core.middlewares.schema_validation_middleware import SchemaValidationMiddleware

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


def resolve_middleware(middleware: Middleware | Type[Middleware] | Callable) -> Middleware | Callable:
    if isinstance(middleware, type) and issubclass(middleware, Middleware):
        return middleware()  # type: ignore[call-arg]
    return middleware  # type: ignore[return-value]


def split_route_middlewares_by_phase(
    middlewares: list[Middleware | Type[Middleware] | Callable] | None,
) -> tuple[list[Middleware | Callable], list[Middleware | Callable], list[Middleware | Callable]]:
    pre_binding: list[Middleware | Callable] = []
    pre_validation: list[Middleware | Callable] = []
    post_validation: list[Middleware | Callable] = []

    for middleware in middlewares or []:
        resolved = resolve_middleware(middleware)
        phase = getattr(resolved, "phase", "post_validation")
        if phase == "pre_binding":
            pre_binding.append(cast(Middleware | Callable, resolved))
        elif phase == "pre_validation":
            pre_validation.append(cast(Middleware | Callable, resolved))
        else:
            post_validation.append(cast(Middleware | Callable, resolved))

    return pre_binding, pre_validation, post_validation

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
        # 2) Route-specific pre-binding middlewares (user-defined)
        # 3) ModelBindingMiddleware
        # 4) Route-specific pre-validation middlewares (user-defined)
        # 5) SchemaValidationMiddleware
        # 6) Route-specific post-validation middlewares (user-defined, default)
        # 7) ResourceResponseMiddleware (last)
        pre_binding_middlewares, pre_validation_middlewares, post_validation_middlewares = split_route_middlewares_by_phase(route.middlewares)

        all_middlewares: list[Middleware | Type[Middleware] | Callable] = [
            HandleExceptionsMiddleware,
            *pre_binding_middlewares,
            ModelBindingMiddleware,
            *pre_validation_middlewares,
            SchemaValidationMiddleware,
            *post_validation_middlewares,
        ]
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
