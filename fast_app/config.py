import os

# Redis database assignments for the application
# Queue jobs - RQ and other background tasks
REDIS_QUEUE_DB = int(os.getenv("REDIS_QUEUE_DB", 15))

# General application cache
REDIS_CACHE_DB = int(os.getenv("REDIS_CACHE_DB", 14))

# Mongo cache for query results
REDIS_DATABASE_CACHE_DB = int(os.getenv("REDIS_DATABASE_CACHE_DB", 13))

# Redis database for broadcasting events (e.g. websockets)
REDIS_BROADCAST_DB = int(os.getenv("REDIS_BROADCAST_DB", 12))

# Redis database for cron scheduler state
REDIS_CRON_DB = int(os.getenv("REDIS_CRON_DB", 11))