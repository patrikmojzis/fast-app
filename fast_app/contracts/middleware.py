from abc import ABC, abstractmethod
from functools import wraps
from typing import Callable, Any, Awaitable


class Middleware(ABC):
    """Abstract base class for all middleware"""
    
    @abstractmethod
    async def handle(self, next_handler: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        """
        Handle the middleware logic
        
        Args:
            next_handler: The next handler in the chain
            *args, **kwargs: Arguments passed to the handler
            
        Returns:
            The response from the middleware chain
        """
        pass
    
    def __call__(self, func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        """Make the middleware callable as a decorator"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.handle(func, *args, **kwargs)
        return wrapper


