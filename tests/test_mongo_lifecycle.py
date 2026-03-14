from __future__ import annotations

import importlib

import pytest


class _FakeClient:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs
        self.closed = False

    def __getitem__(self, name: str):
        return {"database": name}

    def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_clear_closes_existing_mongo_client(monkeypatch: pytest.MonkeyPatch) -> None:
    mongo_module = importlib.import_module("fast_app.database.mongo")
    original_mongo = mongo_module.mongo
    original_db = mongo_module.db
    stop_calls = 0

    async def fake_start_change_stream_watcher(db) -> None:
        return None

    async def fake_stop_change_stream_watcher() -> None:
        nonlocal stop_calls
        stop_calls += 1

    monkeypatch.setattr(mongo_module, "AsyncIOMotorClient", _FakeClient)
    monkeypatch.setattr(mongo_module, "maybe_start_change_stream_watcher", fake_start_change_stream_watcher)
    monkeypatch.setattr(mongo_module, "stop_change_stream_watcher", fake_stop_change_stream_watcher)
    monkeypatch.setenv("MONGO_URI", "mongodb://example:27017")
    monkeypatch.delenv("TEST_ENV", raising=False)

    try:
        await mongo_module.setup_mongo()
        client = mongo_module.mongo

        await mongo_module.clear()

        assert isinstance(client, _FakeClient)
        assert client.closed is True
        assert stop_calls == 1
        assert mongo_module.mongo is None
        assert mongo_module.db is None
    finally:
        mongo_module.mongo = original_mongo
        mongo_module.db = original_db
