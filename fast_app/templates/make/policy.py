from typing import TYPE_CHECKING, Optional

from fast_app import Policy

if TYPE_CHECKING:
    from fast_app import Model


class NewClass(Policy):
    async def before(self, ability: str, authorizable: 'Model') -> Optional[bool]:
        """Return True to grant, False to deny, None to continue to method-specific checks."""
        return None

    # Define methods like: async def view(self, model: 'Model', authorizable: 'User') -> bool: ...
