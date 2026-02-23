"""Core utilities re-exported for convenient access.

These modules provide the always-on fundamentals of the framework.
"""

from fast_validation import Schema, ValidatorRule

from .api import (
    get_client_ip,
    get_mongo_filter_from_query,
    validate_request,
    validate_query,
    get_bearer_token,
    list_paginated,
    search_paginated,
    paginate
)
from .broadcasting import broadcast
from .cache import Cache
from .context import context, define_key, ContextKey
from .events import dispatch, dispatch_now
from .jwt_auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    ACCESS_TOKEN_LIFETIME,
    REFRESH_TOKEN_LIFETIME,
    ACCESS_TOKEN_TYPE,
)
from .localization import __, set_locale, get_locale, trans, trans_choice
from .lock import RedisDistributedLock, redis_lock
from .queue import queue
from .stopwatch import Stopwatch
from .storage import Storage
from .validation_rules.exists_validator_rule import ExistsValidatorRule

__all__ = [
    # api
    "get_client_ip",
    "get_mongo_filter_from_query",
    "validate_request",
    "validate_query",
    "get_bearer_token",
    "list_paginated",
    "search_paginated",
    "paginate",
    # broadcasting/events
    "broadcast",
    "dispatch",
    "dispatch_now",
    # jwt
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "ACCESS_TOKEN_LIFETIME",
    "REFRESH_TOKEN_LIFETIME",
    "ACCESS_TOKEN_TYPE",
    # localization
    "__",
    "set_locale",
    "get_locale",
    "trans",
    "trans_choice",
    # queue/simple controller/stopwatch
    "queue",
    "Stopwatch",
    # storage
    "Storage",
    # validation rules
    "ExistsValidatorRule",
    # context
    "context",
    "define_key",
    "ContextKey",
    # schemas
    "Schema",
    "ValidatorRule",
    # cache
    "Cache",
    # distributed lock
    "RedisDistributedLock",
    "redis_lock",
]
