import os

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import monitoring

from fast_app.utils.database_cache import DatabaseCache

mongo: AsyncIOMotorClient = None
db: AsyncIOMotorDatabase = None


class DatabaseCacheFlusher(monitoring.CommandListener):
    """
    Flushes the DatabaseCache when a command is executed.
    """

    def started(self, event):
        if event.command_name in ["insert", "update", "delete", "create", "findAndModify", "drop", "dropDatabase", "renameCollection"]:
            DatabaseCache.flush()

async def setup_mongo():
    global mongo, db
    # Get environment variables
    db_name = os.getenv('DB_NAME', 'db') if not os.getenv('TEST_ENV') else os.getenv('TEST_DB_NAME', 'test_db')

    if not os.getenv('MONGO_URI'):
        raise ValueError("Set environment variable `MONGO_URI`")
        
    # Connect to MongoDB
    mongo = AsyncIOMotorClient(os.getenv('MONGO_URI'))
    db = mongo[db_name]

    # Register the command logger
    monitoring.register(DatabaseCacheFlusher())

    # Test the connection
    await mongo.admin.command('ping')
    print(f"Connected to MongoDB database: {db_name}")


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
    mongo = None
    db = None