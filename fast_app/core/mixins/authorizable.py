import inspect
from typing import Union, Callable, Optional, TYPE_CHECKING

from fast_app.exceptions.http_exceptions import ForbiddenException

if TYPE_CHECKING:
    from fast_app import Model
    from fast_app import Policy


class Authorizable:
    """
    Mixin class that adds authorization capabilities to models.
    Provides can(), cannot(), and authorize() methods.
    """
    
    async def can(
        self, 
        ability: str,
        target: Union['Model', type]
    ) -> bool:
        """
        Check if the user can perform an action.
        
        Args:
            ability: Ability name (required when target is model instance/class)
            target: Policy function, model instance, or model class
            
        Returns:
            bool: True if user can perform the action
        """            
        # Get the model class
        if inspect.isclass(target):
            model_cls = target
            model_instance = None
        else:
            model_cls = target.__class__
            model_instance = target
            
        # Get the policy for this model
        policy = getattr(model_cls, 'policy', None)
        if not policy:
            # If no policy, default to deny
            return False
            
        # Call the before method first
        before_result = await policy.before(ability, self)
        if before_result is not None:
            return before_result
            
        # Try to get the policy method
        policy_method = getattr(policy, ability, None)
        if not policy_method or not callable(policy_method):
            # If method doesn't exist, default to deny
            return False
            
        # Call the policy method with appropriate parameters
        if model_instance is not None:
            # Instance: pass instance as first param, user as second
            return await policy_method(model_instance, self)
        else:
            # Class: pass user as first param only
            return await policy_method(None, self)
    
    async def cannot(
        self, 
        ability: str,
        target: Union['Model', type]
    ) -> bool:
        """
        Check if the user cannot perform an action.
        
        Args:
            ability: Ability name (required when target is model instance/class)
            target: Policy function, model instance, or model class
            
        Returns:
            bool: True if user cannot perform the action
        """
        return not await self.can(ability, target)
    
    async def authorize(
        self, 
        ability: str,
        target: Union['Model', type],
    ) -> None:
        """
        Authorize user to perform an action. Raises HttpException if not authorized.
        
        Args:
            ability: Ability name (required when target is model instance/class)
            target: Policy function, model instance, or model class
            
        Raises:
            ForbiddenException: If user is not authorized (403)
        """
        if not await self.can(ability, target):
            action_name = ability or "perform action on"
            if inspect.isclass(target):
                model_name = target.__name__
            else:
                model_name = target.__class__.__name__
                    
            raise ForbiddenException(
                error_type="insufficient_privileges", 
                message=f"Insufficient privileges to {action_name} {model_name}"
            )