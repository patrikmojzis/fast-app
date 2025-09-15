import os
import asyncio
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import monitoring
from pymongo.errors import OperationFailure

from fast_app.utils.versioned_cache import bump_collection_version
from fast_app.exceptions import EnvMissingException

mongo: AsyncIOMotorClient = None
db: AsyncIOMotorDatabase = None
_watch_task: Optional[asyncio.Task] = None


class DatabaseCacheFlusher(monitoring.CommandListener):
    """
    Flushes the DatabaseCache when a command is executed.
    """

    def started(self, event):
        if event.command_name in ["insert", "update", "delete", "create", "findAndModify", "drop", "dropDatabase", "renameCollection"]:
            # Try to resolve collection name and bump version
            try:
                coll = event.command.get(event.command_name) or event.command.get("collection") or event.command.get("renameCollection")
                if isinstance(coll, str):
                    # Namespace may include db.collection for rename; take collection part
                    collection_name = coll.split(".")[-1]
                    bump_collection_version(collection_name)
            except Exception:
                pass

    def succeeded(self, event):
        # No-op: we already flushed on started for mutating ops
        pass

    def failed(self, event):
        # No-op: avoid NotImplementedError on command failures
        pass

async def setup_mongo():
    global mongo, db
    # Get environment variables
    db_name = os.getenv('DB_NAME', 'db') if not os.getenv('TEST_ENV') else os.getenv('TEST_DB_NAME', 'test_db')

    if not os.getenv('MONGO_URI'):
        raise EnvMissingException("MONGO_URI")
        
    # Connect to MongoDB
    # Attach the DatabaseCacheFlusher at client construction time so command events are captured
    mongo = AsyncIOMotorClient(
        os.getenv('MONGO_URI'),
        event_listeners=[DatabaseCacheFlusher()]
    )
    db = mongo[db_name]

    # Test the connection
    await mongo.admin.command('ping')
    print(f"Connected to MongoDB database: {db_name}")

    # Optionally start DB change streams watcher for cross-process cache invalidation
    await _maybe_start_change_stream_watcher()


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
    global mongo, db, _watch_task
    # Stop watcher task if running
    if _watch_task is not None:
        _watch_task.cancel()
        try:
            await _watch_task
        except asyncio.CancelledError:
            pass
        finally:
            _watch_task = None
    mongo = None
    db = None


async def _maybe_start_change_stream_watcher():
    """
    Start a background task that watches MongoDB change streams and flushes the
    DatabaseCache on write operations. This provides cross-process invalidation.

    Enabled by setting env var ENABLE_DB_WATCH=1. If the MongoDB deployment does
    not support change streams (e.g., not a replica set), it will silently disable.
    """
    if os.getenv('ENABLE_DB_WATCH', '1') not in ['true', '1', 'True', 'TRUE']:
        return

    # Avoid starting multiple watchers
    global _watch_task
    if _watch_task is not None and not _watch_task.done():
        return

    async def _watch_loop():
        while True:
            try:
                # Using database-level watch to capture changes for all collections
                async with db.watch() as stream:  # type: ignore[attr-defined]
                    async for change in stream:
                        op = change.get('operationType')
                        if op in (
                            'insert', 'update', 'replace', 'delete',
                            'drop', 'dropDatabase', 'rename'
                        ):
                            try:
                                ns = change.get('ns') or {}
                                coll = ns.get('coll')
                                if coll:
                                    bump_collection_version(coll)
                            except Exception:
                                pass
            except asyncio.CancelledError:
                # Propagate cancellation so the task stops promptly
                raise
            except OperationFailure as e:
                # 40573: Change streams only supported on replica sets
                if getattr(e, 'code', None) == 40573:
                    return
                await asyncio.sleep(1)
            except Exception:
                # Transient error: backoff and retry
                await asyncio.sleep(1)

    _watch_task = asyncio.create_task(_watch_loop())
