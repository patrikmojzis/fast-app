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
        target: Union[Callable, 'Model', type], 
        ability: Optional[str] = None
    ) -> bool:
        """
        Check if the user can perform an action.
        
        Args:
            target: Policy function, model instance, or model class
            ability: Ability name (required when target is model instance/class)
            
        Returns:
            bool: True if user can perform the action
        """
        # Case 1: Direct policy function
        if callable(target) and not inspect.isclass(target):
            return await target(self)
            
        # Case 2: Model instance or class
        if ability is None:
            raise ValueError("Ability name is required when target is a model instance or class")
            
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
        before_result = await policy.before(self, ability)
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
            return await policy_method(self)
    
    async def cannot(
        self, 
        target: Union[Callable, 'Model', type], 
        ability: Optional[str] = None
    ) -> bool:
        """
        Check if the user cannot perform an action.
        
        Args:
            target: Policy function, model instance, or model class
            ability: Ability name (required when target is model instance/class)
            
        Returns:
            bool: True if user cannot perform the action
        """
        return not await self.can(target, ability)
    
    async def authorize(
        self, 
        target: Union[Callable, 'Model', type], 
        ability: Optional[str] = None
    ) -> None:
        """
        Authorize user to perform an action. Raises HttpException if not authorized.
        
        Args:
            target: Policy function, model instance, or model class
            ability: Ability name (required when target is model instance/class)
            
        Raises:
            ForbiddenException: If user is not authorized (403)
        """
        if not await self.can(target, ability):
            # Generate meaningful error message
            if callable(target) and not inspect.isclass(target):
                action_name = target.__name__
                model_name = "resource"
            else:
                action_name = ability or "perform action on"
                if inspect.isclass(target):
                    model_name = target.__name__
                else:
                    model_name = target.__class__.__name__
                    
            raise ForbiddenException(
                error_type="insufficient_privileges", 
                message=f"Insufficient privileges to {action_name} {model_name}"
            )