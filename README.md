# FastApp

A Laravel-inspired package for rapid Python application development. FastApp provides a collection of reusable components that you commonly need when starting new Python projects.

## Features

- **Database**: MongoDB integration utilities
- **Decorators**: Caching, retry, singleton, deprecation, ETag support
- **Exceptions**: Standard HTTP, database, and authentication exceptions
- **HTTP Resources**: Base classes for REST API resources
- **Models**: Base model classes with common functionality
- **Notifications**: Notification system with multiple channels (email, chat, telegram)
- **Observers**: Observer pattern implementation for model events
- **Policies**: Policy-based authorization
- **Utilities**: Various helpers for queuing, caching, logging, ORM, and more

## Installation

```bash
pip install fast-app
```

Or for development:

```bash
pip install -e .
```

## Quick Start

```python
from fast_app import *
from fast_app.models import Model
from fast_app.decorators import cached, retry
from fast_app.exceptions import HttpException

# Use base model
class User(Model):
    pass

# Use decorators
@cached(ttl=300)
@retry(max_attempts=3)
def get_user_data(user_id):
    # Your logic here
    pass

# Use exceptions
raise HttpException(status_code=404, message="User not found")
```

## Components

### Database
MongoDB integration with connection management and utilities.

### Decorators
- `@cached` - Caching decorator with TTL support
- `@retry` - Retry decorator for error handling
- `@singleton` - Singleton pattern implementation
- `@deprecated` - Mark functions as deprecated
- `@etag` - HTTP ETag support

### Exceptions
- `HttpException` - Standard HTTP errors
- `DatabaseNotInitializedExceptionException` - Database connectivity errors
- `UnauthorisedException` - Authentication/authorization errors

### Models
Base model classes with common functionality like validation, serialization, and database operations.

### Notifications
Multi-channel notification system supporting:
- Email notifications
- Chat notifications  
- Telegram notifications
- Custom channel implementations

### Observers
Observer pattern for model events:
- Model created/updated/deleted events
- Custom event handling
- Async observer support

### Policies
Policy-based authorization system for controlling access to resources.

### Utilities
- **API Utils**: REST API helpers
- **Cache**: Caching utilities and MongoDB cache
- **Logging**: Structured logging helpers
- **Queue**: Background job queue utilities
- **Query Builder**: MongoDB query builder
- **ORM**: Object-relational mapping utilities
- **Mail**: Email sending utilities

## Philosophy

FastApp follows Laravel's philosophy of "Convention over Configuration" and provides:

1. **Elegant Syntax**: Clean, expressive code that's easy to read and write
2. **Rapid Development**: Get started quickly with pre-built components
3. **Flexible Architecture**: Extend and customize components as needed
4. **DRY Principle**: Don't repeat yourself - reuse common patterns
5. **Performance Optimized**: Built-in caching, retry mechanisms, and optimizations

## Usage Examples

### Using Decorators

```python
from fast_app.decorators import cached, retry

@cached(ttl=600)  # Cache for 10 minutes
def expensive_operation():
    # Your expensive logic here
    return result

@retry(max_attempts=3, delay=1.0)
def unreliable_api_call():
    # API call that might fail
    return api_response
```

### Using Models

```python
from fast_app.models import Model

class Product(Model):
    def __init__(self, name, price):
        self.name = name
        self.price = price
        super().__init__()
    
    def validate(self):
        if self.price < 0:
            raise ValueError("Price must be positive")
```

### Using Notifications

```python
from fast_app.notifications import Notification
from fast_app.notification_channels import MailChannel

class OrderNotification(Notification):
    def __init__(self, order):
        self.order = order
    
    def via(self):
        return [MailChannel()]
    
    def to_mail(self):
        return {
            'subject': f'Order #{self.order.id} confirmed',
            'body': f'Your order has been confirmed.'
        }
```

### Using Policies

```python
from fast_app.policies import Policy

class OrderPolicy(Policy):
    def view(self, user, order):
        return user.id == order.user_id or user.is_admin
    
    def update(self, user, order):
        return user.id == order.user_id
```

## Contributing

FastApp is designed to be extended. Feel free to contribute new decorators, utilities, or improvements.

## License

MIT License. See LICENSE file for details.

## Changelog

### v0.1.0
- Initial release
- Core components extracted from SalesPanda project
- Database, decorators, exceptions, models, notifications, observers, policies, and utilities