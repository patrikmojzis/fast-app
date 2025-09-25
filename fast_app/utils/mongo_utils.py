import asyncio
import os
from typing import Optional

from pymongo import monitoring
from pymongo.errors import OperationFailure

from fast_app.utils.versioned_cache import bump_collection_version


class DatabaseCacheFlusher(monitoring.CommandListener):
    """Flush DatabaseCache version on mutating MongoDB commands."""

    def started(self, event) -> None:  # type: ignore[override]
        if event.command_name in [
            "insert",
            "update",
            "delete",
            "create",
            "findAndModify",
            "drop",
            "dropDatabase",
            "renameCollection",
        ]:
            try:
                collection = (
                    event.command.get(event.command_name)
                    or event.command.get("collection")
                    or event.command.get("renameCollection")
                )
                if isinstance(collection, str):
                    collection_name = collection.split(".")[-1]
                    bump_collection_version(collection_name)
            except Exception:
                pass

    def succeeded(self, event) -> None:  # type: ignore[override]
        pass

    def failed(self, event) -> None:  # type: ignore[override]
        pass


_watch_task: Optional[asyncio.Task] = None


async def maybe_start_change_stream_watcher(db) -> None:
    """
    Start a background task watching MongoDB change streams to bump cache versions.
    Enabled by env `ENABLE_DB_WATCH` truthy values. Silently no-ops if unsupported.
    """
    if os.getenv("ENABLE_DB_WATCH", "1") not in ["true", "1", "True", "TRUE"]:
        return

    global _watch_task
    if _watch_task is not None and not _watch_task.done():
        return

    async def _watch_loop() -> None:
        while True:
            try:
                async with db.watch() as stream:  # type: ignore[attr-defined]
                    async for change in stream:
                        operation_type = change.get("operationType")
                        if operation_type in (
                            "insert",
                            "update",
                            "replace",
                            "delete",
                            "drop",
                            "dropDatabase",
                            "rename",
                        ):
                            try:
                                namespace = change.get("ns") or {}
                                collection = namespace.get("coll")
                                if collection:
                                    bump_collection_version(collection)
                            except Exception:
                                pass
            except asyncio.CancelledError:
                raise
            except OperationFailure as exc:
                if getattr(exc, "code", None) == 40573:
                    return
                await asyncio.sleep(1)
            except Exception:
                await asyncio.sleep(1)

    _watch_task = asyncio.create_task(_watch_loop())


async def stop_change_stream_watcher() -> None:
    """Stop the change stream watcher task if running."""
    global _watch_task
    if _watch_task is not None:
        _watch_task.cancel()
        try:
            await _watch_task
        except asyncio.CancelledError:
            pass
        finally:
            _watch_task = None


