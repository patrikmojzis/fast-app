import os
# General application cache
REDIS_CACHE_DB = int(os.getenv("REDIS_CACHE_DB", 15))

# Mongo cache for query results
REDIS_DATABASE_CACHE_DB = int(os.getenv("REDIS_DATABASE_CACHE_DB", 14))

# Redis database for broadcasting events (e.g. websockets)
REDIS_BROADCAST_DB = int(os.getenv("REDIS_BROADCAST_DB", 13))

# Redis database for scheduler state
REDIS_SCHEDULER_DB = int(os.getenv("REDIS_SCHEDULER_DB", 12))