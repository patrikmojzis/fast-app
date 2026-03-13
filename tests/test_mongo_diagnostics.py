from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from fast_app.utils import mongo_diagnostics
from fast_app.utils.mongo_diagnostics import (
    PROFILE_DOC_PROJECTION,
    MongoActivitySnapshot,
    MongoIndexKey,
    _read_profile_docs,
    build_activity_report,
    build_profile_report,
)


def _top_metric(
    *,
    total_count: int,
    total_time: int,
    queries_count: int = 0,
    queries_time: int = 0,
    getmore_count: int = 0,
    getmore_time: int = 0,
    commands_count: int = 0,
    commands_time: int = 0,
    insert_count: int = 0,
    insert_time: int = 0,
    update_count: int = 0,
    update_time: int = 0,
    remove_count: int = 0,
    remove_time: int = 0,
) -> dict[str, dict[str, int]]:
    return {
        "total": {"count": total_count, "time": total_time},
        "queries": {"count": queries_count, "time": queries_time},
        "getmore": {"count": getmore_count, "time": getmore_time},
        "commands": {"count": commands_count, "time": commands_time},
        "insert": {"count": insert_count, "time": insert_time},
        "update": {"count": update_count, "time": update_time},
        "remove": {"count": remove_count, "time": remove_time},
    }


def _snapshot(captured_at: datetime, top_totals: dict[str, dict[str, dict[str, int]]]) -> MongoActivitySnapshot:
    return MongoActivitySnapshot(
        captured_at=captured_at,
        opcounters_query=100,
        opcounters_getmore=20,
        opcounters_command=40,
        opcounters_insert=10,
        opcounters_update=5,
        opcounters_delete=2,
        docs_returned=200,
        docs_inserted=20,
        docs_updated=10,
        docs_deleted=2,
        scanned=400,
        scanned_objects=500,
        collection_scans=5,
        read_latency_micros=100_000,
        read_ops=50,
        write_latency_micros=40_000,
        write_ops=15,
        command_latency_micros=20_000,
        command_ops=10,
        top_totals=top_totals,
    )


def test_build_activity_report_prioritizes_read_hotspots() -> None:
    start = datetime(2026, 3, 12, 12, 0, tzinfo=UTC)
    before = _snapshot(
        start,
        {
            "fastapp.lead": _top_metric(total_count=10, total_time=20_000, queries_count=10, queries_time=20_000),
            "fastapp.order": _top_metric(total_count=5, total_time=6_000, commands_count=5, commands_time=6_000),
            "fastapp.system.profile": _top_metric(total_count=1, total_time=500, queries_count=1, queries_time=500),
        },
    )
    after = MongoActivitySnapshot(
        captured_at=start + timedelta(seconds=5),
        opcounters_query=160,
        opcounters_getmore=30,
        opcounters_command=70,
        opcounters_insert=15,
        opcounters_update=8,
        opcounters_delete=3,
        docs_returned=500,
        docs_inserted=30,
        docs_updated=16,
        docs_deleted=3,
        scanned=900,
        scanned_objects=1_100,
        collection_scans=11,
        read_latency_micros=310_000,
        read_ops=110,
        write_latency_micros=85_000,
        write_ops=26,
        command_latency_micros=44_000,
        command_ops=20,
        top_totals={
            "fastapp.lead": _top_metric(total_count=40, total_time=170_000, queries_count=28, queries_time=120_000, commands_count=5, commands_time=10_000, update_count=7, update_time=40_000),
            "fastapp.order": _top_metric(total_count=18, total_time=90_000, queries_count=4, queries_time=20_000, commands_count=9, commands_time=50_000, update_count=5, update_time=20_000),
            "fastapp.system.profile": _top_metric(total_count=4, total_time=4_500, queries_count=4, queries_time=4_500),
        },
    )

    report = build_activity_report(
        before,
        after,
        database="fastapp",
        limit=10,
        sort="read-time",
        include_system=False,
        all_databases=False,
    )

    assert round(report.window_seconds, 1) == 5.0
    assert round(report.summary.reads_per_s, 1) == 12.0
    assert round(report.summary.writes_per_s, 1) == 2.2
    assert round(report.summary.docs_returned_per_s, 1) == 60.0
    assert round(report.summary.collection_scans_per_s, 1) == 1.2
    assert round(report.summary.scanned_objects_per_returned_doc or 0, 1) == 2.0
    assert [namespace.namespace for namespace in report.namespaces] == [
        "fastapp.lead",
        "fastapp.order",
    ]
    assert round(report.namespaces[0].read_time_ms_per_s, 1) == 22.0
    assert round(report.namespaces[1].write_time_ms_per_s, 1) == 4.0
    assert report.to_dict()["kind"] == "mongo.activity.report"


def test_build_profile_report_groups_reads_and_excludes_writes_by_default() -> None:
    raw_docs = [
        {
            "ns": "fastapp.lead",
            "command": {"find": "lead", "filter": {"business_id": 1, "status": "open"}, "sort": {"created_at": -1}},
            "planSummary": "COLLSCAN",
            "millis": 40,
            "docsExamined": 500,
            "keysExamined": 0,
            "nreturned": 4,
            "numYield": 1,
        },
        {
            "ns": "fastapp.lead",
            "command": {"find": "lead", "filter": {"business_id": 1, "status": "open"}, "sort": {"created_at": -1}},
            "planSummary": "COLLSCAN",
            "millis": 20,
            "docsExamined": 300,
            "keysExamined": 0,
            "nreturned": 2,
            "numYield": 0,
        },
        {
            "ns": "fastapp.order",
            "command": {"update": "order", "updates": [{"q": {"_id": "abc"}}]},
            "planSummary": "IDHACK",
            "millis": 5,
            "docsExamined": 1,
            "keysExamined": 1,
            "nreturned": 0,
            "numYield": 0,
        },
        {
            "ns": "fastapp.system.profile",
            "command": {"find": "system.profile"},
            "planSummary": "COLLSCAN",
            "millis": 1,
            "docsExamined": 1,
            "keysExamined": 0,
            "nreturned": 1,
            "numYield": 0,
        },
    ]

    report = build_profile_report(
        raw_docs,
        database="fastapp",
        window_seconds=15.0,
        profiler_level=1,
        slowms=25,
        sample_rate=1.0,
        include_writes=False,
        limit=10,
        max_profile_docs=2000,
        sort="total-millis",
    )

    assert report.total_profile_docs == 4
    assert report.matched_profile_docs == 2
    assert report.truncated is False
    assert len(report.findings) == 1
    assert len(report.index_candidates) == 1

    finding = report.findings[0]
    assert finding.namespace == "fastapp.lead"
    assert finding.operation == "find"
    assert finding.count == 2
    assert finding.total_millis == 60
    assert round(finding.avg_millis, 1) == 30.0
    assert finding.collection_scan is True
    assert round(finding.scan_ratio or 0, 1) == 133.3
    assert finding.shape == "filter=business_id,status sort=created_at"
    assert [(key.field, key.direction) for key in finding.suggested_index] == [
        ("business_id", 1),
        ("status", 1),
        ("created_at", -1),
    ]
    assert finding.suggestion_confidence == "high"
    assert finding.covering_index == []
    assert finding.index_note is None
    assert report.to_dict()["kind"] == "mongo.profile.report"

    candidate = report.index_candidates[0]
    assert candidate.namespace == "fastapp.lead"
    assert candidate.confidence == "high"
    assert candidate.observed_queries == 2
    assert [(key.field, key.direction) for key in candidate.keys] == [
        ("business_id", 1),
        ("status", 1),
        ("created_at", -1),
    ]


def test_build_profile_report_suggests_indexes_for_aggregate_match_and_sort() -> None:
    raw_docs = [
        {
            "ns": "fastapp.order",
            "command": {
                "aggregate": "order",
                "pipeline": [
                    {"$match": {"business_id": 1, "status": "open"}},
                    {"$sort": {"created_at": -1}},
                    {"$limit": 25},
                ],
            },
            "planSummary": "COLLSCAN",
            "millis": 80,
            "docsExamined": 1_200,
            "keysExamined": 0,
            "nreturned": 25,
            "numYield": 2,
        }
    ]

    report = build_profile_report(
        raw_docs,
        database="fastapp",
        window_seconds=10.0,
        profiler_level=1,
        slowms=25,
        sample_rate=1.0,
        include_writes=False,
        limit=10,
        max_profile_docs=1000,
        sort="total-millis",
    )

    finding = report.findings[0]
    assert finding.operation == "aggregate"
    assert finding.shape == "filter=business_id,status sort=created_at stages=$match,$sort,$limit"
    assert [(key.field, key.direction) for key in finding.suggested_index] == [
        ("business_id", 1),
        ("status", 1),
        ("created_at", -1),
    ]


def test_build_profile_report_filters_namespaces_and_collection_scans() -> None:
    raw_docs = [
        {
            "ns": "fastapp.lead",
            "command": {"find": "lead", "filter": {"business_id": 1, "status": "open"}},
            "planSummary": "COLLSCAN",
            "millis": 30,
            "docsExamined": 400,
            "keysExamined": 0,
            "nreturned": 10,
            "numYield": 0,
        },
        {
            "ns": "fastapp.order",
            "command": {"find": "order", "filter": {"business_id": 1, "stock_id": 2}},
            "planSummary": "IXSCAN { business_id: 1, stock_id: 1 }",
            "millis": 10,
            "docsExamined": 10,
            "keysExamined": 10,
            "nreturned": 10,
            "numYield": 0,
        },
    ]

    report = build_profile_report(
        raw_docs,
        database="fastapp",
        window_seconds=10.0,
        profiler_level=1,
        slowms=25,
        sample_rate=1.0,
        include_writes=False,
        limit=10,
        max_profile_docs=1000,
        sort="docs-examined",
        namespace_filters=["lead"],
        only_collection_scans=True,
        min_count=1,
        min_total_millis=0,
        min_docs_examined=100,
        min_scan_ratio=0.0,
    )

    assert report.namespace_filters == ["lead"]
    assert report.only_collection_scans is True
    assert [finding.namespace for finding in report.findings] == ["fastapp.lead"]


def test_build_profile_report_only_suggestions_filters_non_candidates() -> None:
    raw_docs = [
        {
            "ns": "fastapp.lead",
            "command": {"find": "lead", "filter": {"business_id": 1, "status": "open"}, "sort": {"created_at": -1}},
            "planSummary": "COLLSCAN",
            "millis": 40,
            "docsExamined": 400,
            "keysExamined": 0,
            "nreturned": 10,
            "numYield": 0,
        },
        {
            "ns": "fastapp.auth",
            "command": {"find": "auth", "filter": {"_id": "abc"}},
            "planSummary": "IXSCAN { _id: 1 }",
            "millis": 3,
            "docsExamined": 1,
            "keysExamined": 1,
            "nreturned": 1,
            "numYield": 0,
        },
    ]

    report = build_profile_report(
        raw_docs,
        database="fastapp",
        window_seconds=10.0,
        profiler_level=1,
        slowms=25,
        sample_rate=1.0,
        include_writes=False,
        limit=10,
        max_profile_docs=1000,
        sort="docs-examined",
        only_suggestions=True,
    )

    assert report.only_suggestions is True
    assert [finding.namespace for finding in report.findings] == ["fastapp.lead"]


def test_build_profile_report_suppresses_redundant_index_suggestions() -> None:
    raw_docs = [
        {
            "ns": "fastapp.auth",
            "command": {"find": "auth", "filter": {"_id": "abc", "is_revoked": False}},
            "planSummary": "IXSCAN { _id: 1 }",
            "millis": 12,
            "docsExamined": 1,
            "keysExamined": 1,
            "nreturned": 1,
            "numYield": 0,
        },
        {
            "ns": "fastapp.lead",
            "command": {"find": "lead", "filter": {"business_id": 1, "status": "open"}, "sort": {"created_at": -1}},
            "planSummary": "COLLSCAN",
            "millis": 40,
            "docsExamined": 400,
            "keysExamined": 0,
            "nreturned": 10,
            "numYield": 0,
        },
        {
            "ns": "fastapp.order",
            "command": {"find": "order", "filter": {"business_id": 1, "status": "open"}, "sort": {"created_at": -1}},
            "planSummary": "COLLSCAN",
            "millis": 40,
            "docsExamined": 400,
            "keysExamined": 0,
            "nreturned": 10,
            "numYield": 0,
        },
        {
            "ns": "fastapp.stock",
            "command": {"find": "stock", "filter": {"business_id": 1, "status": "open"}, "sort": {"created_at": -1}},
            "planSummary": "IXSCAN { business_id: 1, created_at: -1 }",
            "millis": 2,
            "docsExamined": 950,
            "keysExamined": 950,
            "nreturned": 900,
            "numYield": 0,
        },
    ]

    report = build_profile_report(
        raw_docs,
        database="fastapp",
        window_seconds=10.0,
        profiler_level=1,
        slowms=25,
        sample_rate=1.0,
        include_writes=False,
        limit=10,
        max_profile_docs=1000,
        sort="docs-examined",
        namespace_indexes={
            "fastapp.auth": [[MongoIndexKey(field="_id", direction=1)]],
            "fastapp.lead": [
                [
                    MongoIndexKey(field="business_id", direction=1),
                    MongoIndexKey(field="status", direction=1),
                    MongoIndexKey(field="created_at", direction=-1),
                ]
            ],
        },
    )

    auth_finding = next(finding for finding in report.findings if finding.namespace == "fastapp.auth")
    assert auth_finding.suggested_index == []
    assert auth_finding.suggestion_confidence is None
    assert [(key.field, key.direction) for key in auth_finding.covering_index] == [
        ("_id", 1),
    ]
    assert auth_finding.index_note == "Covered by _id lookup"

    lead_finding = next(finding for finding in report.findings if finding.namespace == "fastapp.lead")
    assert lead_finding.suggested_index == []
    assert lead_finding.suggestion_confidence is None
    assert [(key.field, key.direction) for key in lead_finding.covering_index] == [
        ("business_id", 1),
        ("status", 1),
        ("created_at", -1),
    ]
    assert lead_finding.index_note == "Covered by existing index prefix"

    order_finding = next(finding for finding in report.findings if finding.namespace == "fastapp.order")
    assert [(key.field, key.direction) for key in order_finding.suggested_index] == [
        ("business_id", 1),
        ("status", 1),
        ("created_at", -1),
    ]

    stock_finding = next(finding for finding in report.findings if finding.namespace == "fastapp.stock")
    assert stock_finding.suggested_index == []
    assert stock_finding.suggestion_confidence is None


class _FakeProfileCursor:
    def __init__(self, collection: "_FakeProfileCollection") -> None:
        self._collection = collection

    def sort(self, _field: str, _direction: int) -> "_FakeProfileCursor":
        return self

    def limit(self, _value: int) -> "_FakeProfileCursor":
        return self

    async def to_list(self, *, length: int) -> list[dict[str, object]]:
        self._collection.lengths.append(length)
        return self._collection.responses.pop(0)


class _FakeProfileCollection:
    def __init__(self, responses: list[list[dict[str, object]]]) -> None:
        self.responses = list(responses)
        self.find_calls: list[dict[str, object]] = []
        self.lengths: list[int] = []

    def find(self, query: dict[str, object], projection: dict[str, int]) -> _FakeProfileCursor:
        self.find_calls.append(
            {
                "query": query,
                "projection": projection,
            }
        )
        return _FakeProfileCursor(self)


@pytest.mark.asyncio
async def test_read_profile_docs_retries_when_profiler_rows_arrive_late(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr(mongo_diagnostics.asyncio, "sleep", fake_sleep)

    start = datetime(2026, 3, 12, 12, 0, tzinfo=UTC)
    end = start + timedelta(seconds=5)
    collection = _FakeProfileCollection(
        [
            [],
            [],
            [{"ns": "fastapp.lead", "ts": end}],
        ]
    )

    docs = await _read_profile_docs(
        collection,
        database_name="fastapp",
        start_at=start,
        end_at=end,
        max_profile_docs=25,
    )

    assert docs == [{"ns": "fastapp.lead", "ts": end}]
    assert delays == [0.1, 0.25]
    assert collection.lengths == [26, 26, 26]
    assert collection.find_calls == [
        {
            "query": {"ts": {"$gte": start, "$lte": end}},
            "projection": PROFILE_DOC_PROJECTION,
        },
        {
            "query": {"ts": {"$gte": start, "$lte": end}},
            "projection": PROFILE_DOC_PROJECTION,
        },
        {
            "query": {"ts": {"$gte": start, "$lte": end}},
            "projection": PROFILE_DOC_PROJECTION,
        },
    ]
