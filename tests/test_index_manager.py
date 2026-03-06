from __future__ import annotations

from typing import Any

import pytest

from fast_app import ASC, DESC, Index, Model
from fast_app.utils.index_manager import (
    apply_index_sync_plan,
    build_index_sync_plan,
    get_plan_totals,
)


class FakeCursor:
    def __init__(self, data: list[dict[str, Any]]):
        self._data = data

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        return list(self._data)


class FakeCollection:
    def __init__(self, indexes: list[dict[str, Any]]):
        self.indexes = list(indexes)
        self.created: list[dict[str, Any]] = []
        self.dropped: list[str] = []

    def list_indexes(self) -> FakeCursor:
        return FakeCursor(self.indexes)

    async def create_index(self, keys: list[tuple[str, Any]], **options: Any) -> str:
        document = {"key": dict(keys), **options}
        self.created.append(document)
        self.indexes = [index for index in self.indexes if index.get("name") != options.get("name")]
        self.indexes.append(document)
        return str(options.get("name"))

    async def drop_index(self, name: str) -> None:
        self.dropped.append(name)
        self.indexes = [index for index in self.indexes if index.get("name") != name]


class FakeDb(dict[str, FakeCollection]):
    def __getitem__(self, item: str) -> FakeCollection:
        return super().__getitem__(item)


class Order(Model):
    indexes = [
        Index(
            keys=[("business_id", ASC), ("stock_id", ASC), ("date", DESC)],
            name="order_business_stock_date",
        ),
        Index(
            keys=[("business_id", ASC), ("status", ASC), ("date", DESC)],
            name="order_business_status_date",
        ),
        Index(
            keys=[("business_id", ASC), ("lead_id", ASC)],
            name="order_business_lead",
        ),
    ]


@pytest.mark.asyncio
async def test_build_index_sync_plan_detects_missing_changed_and_stale() -> None:
    db = FakeDb(
        {
            "order": FakeCollection(
                [
                    {"name": "_id_", "key": {"_id": 1}},
                    {
                        "name": "order_business_stock_date",
                        "key": {"business_id": 1, "stock_id": 1, "date": -1},
                    },
                    {
                        "name": "order_business_status_date",
                        "key": {"business_id": 1, "status": 1, "date": 1},
                    },
                    {"name": "legacy_order_idx", "key": {"owner_id": 1}},
                ]
            )
        }
    )

    plan = await build_index_sync_plan(db, [Order])
    collection_plan = plan.collections[0]

    assert collection_plan.collection == "order"
    assert [index.name for index in collection_plan.missing] == ["order_business_lead"]
    assert [index.name for index, _ in collection_plan.changed] == ["order_business_status_date"]
    assert [index["name"] for index in collection_plan.stale] == ["legacy_order_idx"]
    assert collection_plan.unchanged == ["order_business_stock_date"]

    totals = get_plan_totals(plan)
    assert totals.collections == 1
    assert totals.declared == 3
    assert totals.missing == 1
    assert totals.changed == 1
    assert totals.stale == 1
    assert totals.unchanged == 1


@pytest.mark.asyncio
async def test_apply_index_sync_plan_dry_run_is_non_destructive() -> None:
    db = FakeDb(
        {
            "order": FakeCollection(
                [
                    {"name": "_id_", "key": {"_id": 1}},
                    {
                        "name": "order_business_status_date",
                        "key": {"business_id": 1, "status": 1, "date": 1},
                    },
                    {"name": "legacy_order_idx", "key": {"owner_id": 1}},
                ]
            )
        }
    )

    plan = await build_index_sync_plan(db, [Order])
    result = await apply_index_sync_plan(db, plan, drop_stale=True, dry_run=True)

    assert result.created == 2
    assert result.recreated == 1
    assert result.dropped_stale == 1
    assert db["order"].created == []
    assert db["order"].dropped == []


@pytest.mark.asyncio
async def test_apply_index_sync_plan_respects_drop_stale_flag() -> None:
    db = FakeDb(
        {
            "order": FakeCollection(
                [
                    {"name": "_id_", "key": {"_id": 1}},
                    {
                        "name": "order_business_status_date",
                        "key": {"business_id": 1, "status": 1, "date": 1},
                    },
                    {"name": "legacy_order_idx", "key": {"owner_id": 1}},
                ]
            )
        }
    )

    plan = await build_index_sync_plan(db, [Order])
    result = await apply_index_sync_plan(db, plan, drop_stale=False, dry_run=False)

    assert result.created == 2
    assert result.recreated == 1
    assert result.dropped_stale == 0
    assert "legacy_order_idx" not in db["order"].dropped

    plan_after_sync = await build_index_sync_plan(db, [Order])
    stale_names = [index["name"] for index in plan_after_sync.collections[0].stale]
    assert stale_names == ["legacy_order_idx"]


@pytest.mark.asyncio
async def test_build_index_sync_plan_raises_on_conflicting_index_definitions() -> None:
    class SharedOne(Model):
        indexes = [Index(keys=[("a", ASC)], name="shared_idx")]

        @classmethod
        def collection_name(cls) -> str:
            return "shared"

    class SharedTwo(Model):
        indexes = [Index(keys=[("b", ASC)], name="shared_idx")]

        @classmethod
        def collection_name(cls) -> str:
            return "shared"

    db = FakeDb({"shared": FakeCollection([{"name": "_id_", "key": {"_id": 1}}])})

    with pytest.raises(ValueError, match="Conflicting index definitions"):
        await build_index_sync_plan(db, [SharedOne, SharedTwo])
