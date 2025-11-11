from typing import Any, Callable, Mapping, Optional, Union, List

from pydantic import BaseModel, Field, ConfigDict

from fast_app.contracts.middleware import Middleware
from fast_app.utils.serialisation import to_snake_case


class Route(BaseModel):
    path: str = Field(..., description="The path of the route")
    handler: Optional[Callable] = Field(default=None, description="The handler of the route")
    methods: Optional[list[str]] = Field(default=None, description="The methods of the route")
    middlewares: Optional[list[Union[Middleware, Callable]]] = Field(default=None, description="The middlewares of the route")
    prefix: Optional[str] = Field(default="", description="The prefix for route groups")
    routes: Optional[list['Route']] = Field(default=None, description="Nested routes for groups")

    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def __init__(self, **data):
        super().__init__(**data)
        # Ensure routes is always a list for groups
        if self.routes is None and self.handler is None:
            self.routes = []
    
    # HTTP method class methods
    @classmethod
    def get(cls, path: str, handler: Callable, middlewares: Optional[List[Union[Middleware, Callable]]] = None) -> 'Route':
        return cls(path=path, handler=handler, methods=["GET"], middlewares=middlewares)
    
    @classmethod
    def post(cls, path: str, handler: Callable, middlewares: Optional[List[Union[Middleware, Callable]]] = None) -> 'Route':
        return cls(path=path, handler=handler, methods=["POST"], middlewares=middlewares)
    
    @classmethod
    def patch(cls, path: str, handler: Callable, middlewares: Optional[List[Union[Middleware, Callable]]] = None) -> 'Route':
        return cls(path=path, handler=handler, methods=["PATCH"], middlewares=middlewares)
    
    @classmethod
    def delete(cls, path: str, handler: Callable, middlewares: Optional[List[Union[Middleware, Callable]]] = None) -> 'Route':
        return cls(path=path, handler=handler, methods=["DELETE"], middlewares=middlewares)
    
    @classmethod
    def put(cls, path: str, handler: Callable, middlewares: Optional[List[Union[Middleware, Callable]]] = None) -> 'Route':
        return cls(path=path, handler=handler, methods=["PUT"], middlewares=middlewares)

    @classmethod
    def options(cls, path: str, handler: Callable, middlewares: Optional[List[Union[Middleware, Callable]]] = None) -> 'Route':
        return cls(path=path, handler=handler, methods=["OPTIONS"], middlewares=middlewares)
    
    @classmethod
    def head(cls, path: str, handler: Callable, middlewares: Optional[List[Union[Middleware, Callable]]] = None) -> 'Route':
        return cls(path=path, handler=handler, methods=["HEAD"], middlewares=middlewares)
    
    # Route grouping method
    @classmethod
    def group(cls, prefix: str = "", routes: Optional[List['Route']] = None, middlewares: Optional[List[Union[Middleware, Callable]]] = None) -> 'Route':
        """Create a route group with prefix, routes, and middlewares"""
        return cls(
            path="",  # Groups don't have individual paths
            prefix=prefix,
            routes=routes or [],
            middlewares=middlewares
        )
    
    @classmethod
    def resource(
        cls,
        path: str,
        controller: Any,
        *,
        middlewares: Optional[List[Union[Middleware, Callable]]] = None,
        controller_methods: Optional[Mapping[str, str]] = None,
        parameter: Optional[str] = None,
    ) -> 'Route':
        """Create a CRUD resource group for a controller."""

        action_definitions = (
            ("index", ["GET"], False),
            ("show", ["GET"], True),
            ("store", ["POST"], False),
            ("destroy", ["DELETE"], True),
            ("update", ["PATCH"], True),
        )

        prefix, param_name = cls._prepare_resource_context(path, parameter)

        method_overrides = {
            key.lower(): value for key, value in (controller_methods or {}).items()
        }

        routes: List['Route'] = []
        for action, methods, needs_identifier in action_definitions:
            attribute_name = method_overrides.get(action, action)
            handler = getattr(controller, attribute_name, None)

            if handler is None or not callable(handler):
                controller_name = getattr(controller, "__name__", controller.__class__.__name__)
                raise AttributeError(
                    f"Controller '{controller_name}' is missing callable '{attribute_name}' for resource action '{methods}'."
                )

            route_path = "" if not needs_identifier else f"/<{param_name}>"

            routes.append(
                cls(
                    path=route_path,
                    handler=handler,
                    methods=methods,
                )
            )

        return cls.group(prefix=prefix, routes=routes, middlewares=middlewares)

    def flatten(self, parent_prefix: str = "", parent_middlewares: Optional[List[Union[Middleware, Callable]]] = None) -> List['Route']:
        """Flatten route groups into individual routes"""
        parent_middlewares = parent_middlewares or []
        
        # If this is a regular route (has handler), return it with applied prefix and middlewares
        if self.handler is not None:
            full_path = parent_prefix.rstrip('/') + '/' + self.path.lstrip('/')
            full_path = full_path.replace('//', '/').rstrip('/') or '/'
            
            combined_middlewares = parent_middlewares + (self.middlewares or [])
            
            return [self.model_copy(update={
                'path': full_path,
                'middlewares': combined_middlewares if combined_middlewares else None
            })]
        
        # If this is a group, process all nested routes
        flattened = []
        if self.routes:
            current_prefix = parent_prefix.rstrip('/') + '/' + (self.prefix or '').lstrip('/')
            current_prefix = current_prefix.replace('//', '/').rstrip('/') or '/'
            
            current_middlewares = parent_middlewares + (self.middlewares or [])
            
            for route in self.routes:
                flattened.extend(route.flatten(current_prefix, current_middlewares))
        
        return flattened

    @classmethod
    def _prepare_resource_context(cls, path: str, parameter: Optional[str]) -> tuple[str, str]:
        segments = [segment for segment in path.split('/') if segment]
        prefix = '/' + '/'.join(segments) if segments else '/'
        slug = segments[-1] if segments else ''

        if parameter is not None:
            param_candidate = parameter.strip("<> ")
            param_name = to_snake_case(param_candidate) or param_candidate
        else:
            base = to_snake_case(slug) or 'resource'
            param_name = base if base.endswith('_id') else f"{base}_id"

        if not param_name:
            param_name = 'resource_id'

        return prefix, param_name
