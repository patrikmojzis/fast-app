from fast_app.app_provider import boot
boot()

import os

import pytest_asyncio

from app.modules.api import create_app


@pytest_asyncio.fixture(scope="function")
async def app():
    quart_app = create_app()
    quart_app.config['TESTING'] = True
    yield quart_app


@pytest_asyncio.fixture(scope='function', autouse=True)
async def setup_session():
    # Reset MongoDB global variables to avoid event loop issues
    import fast_app.database.mongo
    fast_app.database.mongo.clear()

    # Clear caches
    from fast_app.utils.database_cache import DatabaseCache
    DatabaseCache.flush()

    from fast_app.core.cache import Cache
    Cache.flush()

    yield
    
    
async def drop_db():
    if db := os.getenv('TEST_DB_NAME'):
        # Create a fresh MongoDB connection for this operation to avoid event loop issues
        from motor.motor_asyncio import AsyncIOMotorClient
        
        if not os.getenv('MONGO_URI'):
            raise ValueError("Set environment variable `MONGO_URI`")

        fresh_client = AsyncIOMotorClient(os.getenv('MONGO_URI'))
        try:
            await fresh_client.drop_database(db)
        finally:
            fresh_client.close()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_db():
    await drop_db()
    yield


def pytest_configure():
    os.environ['TEST_ENV'] = 'true'
    os.environ['QUEUE_DRIVER'] = 'sync'
    os.environ['MAIL_DRIVER'] = 'log'
    os.environ['DB'] = os.getenv('TEST_DB_NAME', 'test_db')
