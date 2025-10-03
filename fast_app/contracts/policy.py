from abc import ABC
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from fast_app import Model

class Policy(ABC):
    
    async def before(self, ability: str, authorizable: 'Model') -> Optional[bool]:
        """
        Called before any policy method. If returns True, grants access.
        If returns False, denies access. If returns None, continues to policy method.
        
        Args:
            ability: The name of the policy method being called
            authorizable: The model instance being authorized (e.g. User)
            
        Returns:
            Optional[bool]: True to grant, False to deny, None to continue
        """
        return None


