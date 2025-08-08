from typing import Any, Callable, Awaitable

from quart import g

from fast_app.common.middleware import Middleware
from fast_app.common.api import get_client_ip
from fast_app.common.cache import Cache
from fast_app.exceptions.http_exceptions import TooManyRequestsException


class RateLimitMiddleware(Middleware):
    """Laravel-inspired rate limiting middleware"""
    
    def __init__(self, key: str, max_attempts: int = 60, decay_minutes: int = 1):
        """
        Args:
            key: Rate limiter key (e.g., 'login', 'api', 'send-message')
            max_attempts: Maximum attempts allowed
            decay_minutes: Minutes until attempts reset
        """
        self.key = key
        self.max_attempts = max_attempts
        self.decay_minutes = decay_minutes
    
    async def handle(self, next_handler: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        limiter_key = self._resolve_key()
        current = await Cache.get(limiter_key, 0)
        
        if current >= self.max_attempts:
            raise TooManyRequestsException(
                message=f'Too many attempts, try again in {self.decay_minutes} minute(s).'
            )
        
        await self._increment(limiter_key, current)
        return await next_handler(*args, **kwargs)
    
    def _resolve_key(self) -> str:
        """Resolve the rate limiter key with dynamic identifier"""
        identifier = getattr(g, 'user', None)
        if identifier:
            identifier = str(identifier.id)
        else:
            identifier = get_client_ip()
        
        return f"{self.key}:{identifier}"
    
    async def _increment(self, key: str, current: int) -> None:
        """Increment attempts for key"""
        if current == 0:
            await Cache.set(key, 1, expire_in_m=self.decay_minutes)
        else:
            await Cache.increment(key)