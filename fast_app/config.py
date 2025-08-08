import os

# Redis database assignments for the application
# Queue jobs - RQ and other background tasks
REDIS_QUEUE_DB = int(os.getenv("REDIS_QUEUE_DB", 0))

# General application cache
REDIS_CACHE_DB = int(os.getenv("REDIS_CACHE_DB", 1))

# Mongo cache for query results
REDIS_DATABASE_CACHE_DB = int(os.getenv("REDIS_DATABASE_CACHE_DB", 2))

# Redis database for broadcasting events (e.g. websockets)
REDIS_BROADCAST_DB = int(os.getenv("REDIS_BROADCAST_DB", 3))

# Redis database for cron scheduler state
REDIS_CRON_DB = int(os.getenv("REDIS_CRON_DB", 4))

# Storage configuration (drivers are registered separately)
STORAGE_DISKS = {
    "local": {
        "driver": "disk",
        "root": os.getenv("STORAGE_LOCAL_ROOT", os.path.join(os.getcwd(), "storage", "local")),
        "permissions": {
            "file": {"public": 0o644, "private": 0o600},
            "dir": {"public": 0o755, "private": 0o700},
        },
    },
    "public": {
        "driver": "disk",
        "root": os.getenv("STORAGE_PUBLIC_ROOT", os.path.join(os.getcwd(), "storage", "public")),
        "permissions": {
            "file": {"public": 0o644, "private": 0o600},
            "dir": {"public": 0o755, "private": 0o700},
        },
    },
    "boto3": {
        "driver": "boto3",
        "key": os.getenv("AWS_ACCESS_KEY_ID"),
        "secret": os.getenv("AWS_SECRET_ACCESS_KEY"),
        "region": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        "bucket": os.getenv("AWS_BUCKET"),
        "endpoint": os.getenv("AWS_ENDPOINT"),
    },
}

# Default storage disk
STORAGE_DEFAULT_DISK = os.getenv("STORAGE_DEFAULT_DISK", "local")

# Localization configuration
LOCALE_DEFAULT = os.getenv('LOCALE_DEFAULT', 'en')
LOCALE_FALLBACK = os.getenv('LOCALE_FALLBACK', 'en')
LOCALE_PATH = os.getenv('LOCALE_PATH', os.path.join(os.getcwd(), 'lang'))