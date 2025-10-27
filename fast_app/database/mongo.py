import logging
import os
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from fast_app.exceptions import EnvMissingException
from fast_app.utils.mongo_utils import (
    DatabaseCacheFlusher,
    maybe_start_change_stream_watcher,
    stop_change_stream_watcher,
)

mongo: Optional[AsyncIOMotorClient] = None
db: Optional[AsyncIOMotorDatabase] = None

async def setup_mongo():
    global mongo, db
    # Get environment variables
    db_name = os.getenv('DB_NAME', 'db') if not os.getenv('TEST_ENV') else os.getenv('TEST_DB_NAME', 'test_db')

    if not os.getenv('MONGO_URI'):
        raise EnvMissingException("MONGO_URI")
        
    # Connect to MongoDB with DatabaseCacheFlusher attached
    mongo = AsyncIOMotorClient(
        os.getenv('MONGO_URI'),
        event_listeners=[DatabaseCacheFlusher()],
        tz_aware=True,
    )
    db = mongo[db_name]

    logging.debug(f"Connected to MongoDB database: {db_name}")

    # Optionally start DB change streams watcher for cross-process cache invalidation
    await maybe_start_change_stream_watcher(db)


async def get_mongo():
    global mongo
    if mongo is None:
        await setup_mongo()
    return mongo


async def get_db():
    global db
    if db is None:
        await setup_mongo()
    return db


async def clear():
    global mongo, db
    await stop_change_stream_watcher()
    mongo = None
    db = None

