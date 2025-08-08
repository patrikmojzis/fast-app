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

# Core imports for easy access
from .database.mongo import *
from .cron import *
from .decorators import *
from .exceptions import *
from .model_base import *
from .resource_base import *
from .notification_base import *
from .notification_channel_base import *
from .observer_base import *
from .policy_base import *
from .common.localization import __, set_locale, get_locale, trans, trans_choice