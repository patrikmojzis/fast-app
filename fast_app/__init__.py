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

__version__ = "0.1.0"
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
    WebsocketEvent,
    Command,
    Room,
    Seeder,
    Migration,
)
from .core import (
    get_client_ip,
    get_mongo_filter_from_query,
    validate_request,
    validate_query,
    get_bearer_auth_token,
    get_websocket_auth_token,
    get_request_auth_token,
    list_paginated,
    search_paginated,
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
)
from .decorators import (
    cached,
    deprecated,
    middleware,
    register_observer,
    register_policy,
    register_search_relation,
    authorizable,
    notifiable,
    retry,
    singleton,
)

from .app_provider import boot

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
    "WebsocketEvent",
    "Command",
    "Room",
    "Seeder",
    "Migration",
    # core
    "get_client_ip",
    "get_mongo_filter_from_query",
    "validate_request",
    "validate_query",
    "get_bearer_auth_token",
    "get_websocket_auth_token",
    "get_request_auth_token",
    "list_paginated",
    "search_paginated",
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
    "SimpleController",
    "Stopwatch",
    "Storage",
    "DiskStorage",
    "ExistsValidatorRule",
    "context",
    "define_key",
    "ContextKey",
    "Schema",
    "ValidatorRule",
    "Cache",
    # decorators
    "cached",
    "deprecated",
    "middleware",
    "register_observer",
    "register_policy",
    "register_search_relation",
    "authorizable",
    "notifiable",
    "retry",
    "singleton",    
    # app_provider
    "boot",
]
