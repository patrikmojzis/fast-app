"""
FastApp - A reusable package for rapid Python application development

This package provides core components commonly used across projects:
- Database utilities (MongoDB integration)  
- Decorators (caching, retry, singleton, etc.)
- Exceptions (HTTP, database, auth)
- HTTP resources and models
- Localization system (Laravel-inspired)
- Notification system
- Observer pattern implementation
- Policy pattern implementation
- Various utilities

Think of it as a Laravel-inspired package for Python applications.
"""

__version__ = "0.3.1"
__author__ = "Patrik Mojzis"
__email__ = "patrikm53@gmail.com"
__license__ = "MIT"
__url__ = "https://github.com/patrikmojzis/fast-app"

from .contracts import (
    BroadcastEvent,
    Event,
    EventListener,
    Middleware,
    Model,
    Notification,
    NotificationChannel,
    Observer,
    Policy,
    Resource,
    Route,
    StorageDriver,
    Command,
    Room,
    Seeder,
    Migration,
    Factory,
)
from .core import (
    get_client_ip,
    get_mongo_filter_from_query,
    validate_request,
    validate_query,
    get_bearer_token,
    list_paginated,
    search_paginated,
    paginate,
    broadcast,
    dispatch,
    dispatch_now,
    create_access_token,
    create_refresh_token,
    decode_token,
    ACCESS_TOKEN_LIFETIME,
    REFRESH_TOKEN_LIFETIME,
    ACCESS_TOKEN_TYPE,
    __,
    set_locale,
    get_locale,
    trans,
    trans_choice,
    queue,
    Stopwatch,
    Storage,
    ExistsValidatorRule,
    context,
    define_key,
    ContextKey,
    Schema,
    ValidatorRule,
    Cache,
    RedisDistributedLock,
    redis_lock,
)
from .decorators import (
    cached,
    deprecated,
    middleware,
    register_observer,
    register_policy,
    register_factory,
    register_search_relation,
    authorizable,
    notifiable,
    retry,
    singleton,
)
from .utils import (
    now,
    FileStorageValidator,
)

__all__ = [
    # contracts
    "BroadcastEvent",
    "Event",
    "EventListener",
    "Middleware",
    "Model",
    "Notification",
    "NotificationChannel",
    "Observer",
    "Policy",
    "Resource",
    "Route",
    "StorageDriver",
    "Command",
    "Room",
    "Seeder",
    "Migration",
    "Factory",
    # core
    "get_client_ip",
    "get_mongo_filter_from_query",
    "validate_request",
    "validate_query",
    "get_bearer_token",
    "list_paginated",
    "search_paginated",
    "paginate",
    "broadcast",
    "dispatch",
    "dispatch_now",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "ACCESS_TOKEN_LIFETIME",
    "REFRESH_TOKEN_LIFETIME",
    "ACCESS_TOKEN_TYPE",
    "__",
    "set_locale",
    "get_locale",
    "trans",
    "trans_choice",
    "queue",
    "Stopwatch",
    "Storage",
    "ExistsValidatorRule",
    "context",
    "define_key",
    "ContextKey",
    "Schema",
    "ValidatorRule",
    "Cache",
    "RedisDistributedLock",
    "redis_lock",
    # decorators
    "cached",
    "deprecated",
    "middleware",
    "register_observer",
    "register_policy",
    "register_factory",
    "register_search_relation",
    "authorizable",
    "notifiable",
    "retry",
    "singleton",    
    # utils
    "now",
    "FileStorageValidator",
]
