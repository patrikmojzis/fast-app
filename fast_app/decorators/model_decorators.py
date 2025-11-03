from functools import wraps
from typing import TYPE_CHECKING, Type, TypeVar

from fast_app.core.mixins.authorizable import Authorizable
from fast_app.core.mixins.routes_notifications import RoutesNotifications

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from fast_app import Policy, Observer

T = TypeVar('T')

def register_observer(observer_cls: type['Observer']):
    def decorator(model_cls):
        original_init = model_cls.__init__

        @wraps(original_init)
        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self.register_observer(observer_cls())

        model_cls.__init__ = new_init
        return model_cls
    return decorator


def register_policy(policy_cls: type['Policy']):
    def decorator(model_cls):
        model_cls.policy = policy_cls()
        return model_cls
    return decorator


def register_search_relation(field: str, model: str, search_fields: list[str]):
    def decorator(model_cls):
        relation = {
            "field": field,
            "model": model,
            "search_fields": search_fields
        }
        if not hasattr(model_cls, 'search_relations') or model_cls.search_relations is None:
            model_cls.search_relations = []
        model_cls.search_relations.append(relation)
        return model_cls
    return decorator


def authorizable(model_cls: Type[T]) -> Type[T]:
    """
    Decorator that adds Authorizable as a parent class to the model.
    
    For proper IDE type checking support use Authorizable mixin `class MyModel(Model, Authorizable):`.
    """
    # Check if Authorizable is already in the MRO to avoid duplicate inheritance
    if Authorizable in model_cls.__mro__:
        return model_cls
    
    # Create a new class that inherits from both the model and Authorizable
    new_class = type(
        model_cls.__name__,
        (model_cls, Authorizable),
        dict(model_cls.__dict__)
    )
    
    # Preserve the original module and qualname for proper identification
    new_class.__module__ = model_cls.__module__
    new_class.__qualname__ = model_cls.__qualname__
    
    return new_class


def notifiable(model_cls: Type[T]) -> Type[T]:
    """Decorator that adds RoutesNotifications as a parent class to the model."""
    # Check if RoutesNotifications is already in the MRO to avoid duplicate inheritance
    if RoutesNotifications in model_cls.__mro__:
        return model_cls
    
    # Create a new class that inherits from both the model and RoutesNotifications
    new_class = type(
        model_cls.__name__,
        (model_cls, RoutesNotifications),
        dict(model_cls.__dict__)
    )
    
    # Preserve the original module and qualname for proper identification
    new_class.__module__ = model_cls.__module__
    new_class.__qualname__ = model_cls.__qualname__
    
    return new_class
