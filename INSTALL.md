# FastApp Installation Guide

## Development Installation

From the `fast_app` directory:

```bash
# Install in development mode
pip install -e .

# Or install with dependencies
pip install -e . -r requirements.txt
```

## Production Installation

```bash
# Install from source
pip install git+https://github.com/salespanda/fast-app.git

# Or if published to PyPI
pip install fast-app
```

## Quick Test

```bash
# Run the example
python example.py

# Or test import
python -c "from fast_app import *; print('FastApp imported successfully!')"
```

## Usage in Your Project

```python
# In your project's requirements.txt
fast-app>=0.1.0

# In your Python code
from fast_app.decorators import cached, retry
from fast_app.models import Model
from fast_app.exceptions import HttpException

# Use the components...
```

## Package Contents

The FastApp package includes:

- **Database**: MongoDB utilities (`mongo.py`)
- **Decorators**: `@cached`, `@retry`, `@singleton`, `@deprecated`, `@etag`
- **Exceptions**: `HttpException`, `DatabaseNotInitializedExceptionException`, `UnauthorisedException`
- **HTTP**: `Resource` for REST APIs
- **Models**: `Model` for data models
- **Notifications**: Base classes for notification system
- **Observers**: Observer pattern implementation
- **Policies**: Authorization policy system
- **Utils**: API utilities, caching, logging, queuing, ORM, mail, etc.

