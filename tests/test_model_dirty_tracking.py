from datetime import datetime

import pytest
from bson import ObjectId

from fast_app.contracts.model import Model


class DirtyTrackedModel(Model):
    name: str | None = None
    scheduled_for: datetime | None = None

    compare_normalizers = {
        "scheduled_for": lambda value: value.date() if isinstance(value, datetime) else value,
    }


def test_touch_and_restore_marks_field_pure_but_touched():
    model = DirtyTrackedModel(_id=ObjectId(), name="Alice")

    model.name = "Bob"
    model.name = "Alice"

    assert model.is_touched("name") is True
    assert model.is_dirty("name") is False
    assert model.is_pure("name") is True
    assert model.dirty_fields() == set()


def test_datetime_normalizer_treats_same_day_as_pure():
    model = DirtyTrackedModel(
        _id=ObjectId(),
        scheduled_for=datetime(2026, 3, 9, 9, 0, 0),
    )

    model.scheduled_for = datetime(2026, 3, 9, 17, 30, 0)

    assert model.is_touched("scheduled_for") is True
    assert model.is_dirty("scheduled_for") is False
    assert model.is_pure("scheduled_for") is True


@pytest.mark.asyncio
async def test_update_persists_only_actually_dirty_fields():
    model = DirtyTrackedModel(_id=ObjectId(), name="Alice")

    model.name = "Bob"
    model.name = "Alice"
    model.scheduled_for = datetime(2026, 3, 10, 8, 0, 0)

    captured: dict[str, object] = {}

    class DummyCollection:
        async def update_one(self, query, payload):
            captured["query"] = query
            captured["payload"] = payload

    async def fake_collection():
        return DummyCollection()

    async def fake_refresh():
        model.clean = {}
        return model

    model.collection = fake_collection
    model.refresh = fake_refresh

    await model._update()

    assert captured["query"] == {"_id": model._id}
    assert captured["payload"] == {
        "$set": {"scheduled_for": datetime(2026, 3, 10, 8, 0, 0)},
        "$currentDate": {"updated_at": True},
    }
    assert model.clean == {}


@pytest.mark.asyncio
async def test_update_with_no_actual_changes_is_a_noop():
    model = DirtyTrackedModel(_id=ObjectId(), name="Alice")
    model.name = "Alice"

    events: list[str] = []

    class DummyCollection:
        async def update_one(self, query, payload):  # pragma: no cover - should not be called
            raise AssertionError("update_one should not be called for a pure model")

    async def fake_collection():
        return DummyCollection()

    async def fake_notify(hook: str):
        events.append(hook)

    model.collection = fake_collection
    model._notify_observer = fake_notify

    await model._update()

    assert events == []
    assert model.clean == {}
