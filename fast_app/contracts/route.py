from typing import Callable, Optional, Union, List
from pydantic import BaseModel, Field, ConfigDict
from fast_app.contracts.middleware import Middleware


class Route(BaseModel):
    path: str = Field(..., description="The path of the route")
    handler: Optional[Callable] = Field(default=None, description="The handler of the route")
    methods: Optional[list[str]] = Field(default=None, description="The methods of the route")
    middlewares: Optional[list[Union[Middleware, Callable]]] = Field(default=None, description="The middlewares of the route")
    prefix: Optional[str] = Field(default="", description="The prefix for route groups")
    routes: Optional[list['Route']] = Field(default=None, description="Nested routes for groups")
    is_websocket: bool = Field(default=False, description="Whether this route is a WebSocket route")

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

    # WebSocket route method
    @classmethod
    def websocket(
        cls,
        path: str,
        handler: Callable,
        middlewares: Optional[List[Union[Middleware, Callable]]] = None,
    ) -> 'Route':
        return cls(path=path, handler=handler, methods=None, middlewares=middlewares, is_websocket=True)
    
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