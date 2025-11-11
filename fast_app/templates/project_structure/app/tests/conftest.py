import os

import pytest_asyncio
from app.modules.asgi.quart import create_quart_app

import fast_app.boot  # noqa: F401


@pytest_asyncio.fixture(scope="function")
async def app():
    quart_app = create_quart_app()
    quart_app.config['TESTING'] = True
    yield quart_app


@pytest_asyncio.fixture(scope='function', autouse=True)
async def setup_session():
    # Reset MongoDB global variables to avoid event loop issues
    # FastApp imports
    from fast_app.database import clear
    await clear()

    # Clear caches (best-effort in tests; ignore if Redis not available)
    try:
        from fast_app.utils.versioned_cache import _redis
        _redis.flushdb()
    except Exception:
        pass

    try:
        # FastApp imports
        from fast_app.core.cache import Cache
        await Cache.flush()
    except Exception:
        pass

    yield
    
    
async def drop_db():
    if db := os.getenv('TEST_DB_NAME'):
        # Create a fresh MongoDB connection for this operation to avoid event loop issues
        # Third party
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
