from fast_app.policy_base import Policy
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from fast_app.model_base import Model


class Policy(Policy):

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

    # Add other policy methods here