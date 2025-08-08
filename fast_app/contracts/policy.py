from abc import ABC
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from fast_app import Model

class Policy(ABC):

    async def query(self, query: dict) -> dict:
        """
        Called by Model on all retrieval or count methods.
        This method is overridden by the child class to implement the actual policy logic.
        """
        return query
    
    async def before(self, user: 'Model', ability: str) -> Optional[bool]:
        """
        Called before any policy method. If returns True, grants access.
        If returns False, denies access. If returns None, continues to policy method.
        
        Args:
            user: The user model instance
            ability: The name of the policy method being called
            
        Returns:
            Optional[bool]: True to grant, False to deny, None to continue
        """
        return None


