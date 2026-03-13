from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Literal

from pymongo.errors import OperationFailure

ActivitySort = Literal["read-time", "read-ops", "total-time", "write-time"]
ProfileSort = Literal["total-millis", "avg-millis", "max-millis", "docs-examined", "scan-ratio"]
SuggestionConfidence = Literal["high", "medium", "low"]

PROFILE_ROW_SETTLE_SECONDS = 0.25

READ_OPERATIONS = {
    "aggregate",
    "count",
    "countdocuments",
    "distinct",
    "find",
    "getmore",
    "query",
}
WRITE_OPERATIONS = {
    "bulkwrite",
    "delete",
    "findandmodify",
    "insert",
    "remove",
    "replace",
    "update",
}
EQ_LIKE_OPERATORS = {"$eq", "$in", "$all"}
LOGICAL_OPERATORS = {"$and", "$or", "$nor"}
RANGE_LIKE_OPERATORS = {
    "$gt",
    "$gte",
    "$lt",
    "$lte",
    "$ne",
    "$nin",
    "$regex",
    "$not",
    "$exists",
    "$size",
}
PROFILE_DOC_PROJECTION = {
    "command": 1,
    "docsExamined": 1,
    "keysExamined": 1,
    "millis": 1,
    "nreturned": 1,
    "ns": 1,
    "numYield": 1,
    "op": 1,
    "planSummary": 1,
    "query": 1,
    "ts": 1,
}
PROFILE_READ_RETRY_DELAYS = (0.1, 0.25, 0.5)


@dataclass(slots=True)
class MongoIndexKey:
    field: str
    direction: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "direction": self.direction,
        }


@dataclass(slots=True)
class MongoIndexCandidate:
    namespace: str
    keys: list[MongoIndexKey]
    confidence: SuggestionConfidence
    source_operations: list[str]
    supporting_findings: int
    observed_queries: int
    total_millis: int
    max_millis: int
    worst_scan_ratio: float | None
    collection_scan: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "keys": [key.to_dict() for key in self.keys],
            "confidence": self.confidence,
            "source_operations": self.source_operations,
            "supporting_findings": self.supporting_findings,
            "observed_queries": self.observed_queries,
            "total_millis": self.total_millis,
            "max_millis": self.max_millis,
            "worst_scan_ratio": _round_or_none(self.worst_scan_ratio),
            "collection_scan": self.collection_scan,
            "reason": self.reason,
        }


@dataclass(slots=True)
class _MongoShapeInfo:
    label: str
    equality_fields: list[str]
    range_fields: list[str]
    sort_fields: list[tuple[str, int]]


@dataclass(slots=True)
class MongoActivitySnapshot:
    captured_at: datetime
    opcounters_query: int
    opcounters_getmore: int
    opcounters_command: int
    opcounters_insert: int
    opcounters_update: int
    opcounters_delete: int
    docs_returned: int
    docs_inserted: int
    docs_updated: int
    docs_deleted: int
    scanned: int
    scanned_objects: int
    collection_scans: int
    read_latency_micros: int
    read_ops: int
    write_latency_micros: int
    write_ops: int
    command_latency_micros: int
    command_ops: int
    top_totals: dict[str, dict[str, dict[str, int]]]


@dataclass(slots=True)
class MongoNamespaceActivity:
    namespace: str
    read_ops: int
    write_ops: int
    total_ops: int
    read_ops_per_s: float
    write_ops_per_s: float
    total_ops_per_s: float
    read_time_ms: float
    write_time_ms: float
    total_time_ms: float
    read_time_ms_per_s: float
    write_time_ms_per_s: float
    total_time_ms_per_s: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "read_ops": self.read_ops,
            "write_ops": self.write_ops,
            "total_ops": self.total_ops,
            "read_ops_per_s": round(self.read_ops_per_s, 3),
            "write_ops_per_s": round(self.write_ops_per_s, 3),
            "total_ops_per_s": round(self.total_ops_per_s, 3),
            "read_time_ms": round(self.read_time_ms, 3),
            "write_time_ms": round(self.write_time_ms, 3),
            "total_time_ms": round(self.total_time_ms, 3),
            "read_time_ms_per_s": round(self.read_time_ms_per_s, 3),
            "write_time_ms_per_s": round(self.write_time_ms_per_s, 3),
            "total_time_ms_per_s": round(self.total_time_ms_per_s, 3),
        }


@dataclass(slots=True)
class MongoActivitySummary:
    reads_per_s: float
    writes_per_s: float
    commands_per_s: float
    docs_returned_per_s: float
    docs_inserted_per_s: float
    docs_updated_per_s: float
    docs_deleted_per_s: float
    collection_scans_per_s: float
    avg_read_ms: float | None
    avg_write_ms: float | None
    avg_command_ms: float | None
    scanned_objects_per_returned_doc: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "reads_per_s": round(self.reads_per_s, 3),
            "writes_per_s": round(self.writes_per_s, 3),
            "commands_per_s": round(self.commands_per_s, 3),
            "docs_returned_per_s": round(self.docs_returned_per_s, 3),
            "docs_inserted_per_s": round(self.docs_inserted_per_s, 3),
            "docs_updated_per_s": round(self.docs_updated_per_s, 3),
            "docs_deleted_per_s": round(self.docs_deleted_per_s, 3),
            "collection_scans_per_s": round(self.collection_scans_per_s, 3),
            "avg_read_ms": _round_or_none(self.avg_read_ms),
            "avg_write_ms": _round_or_none(self.avg_write_ms),
            "avg_command_ms": _round_or_none(self.avg_command_ms),
            "scanned_objects_per_returned_doc": _round_or_none(self.scanned_objects_per_returned_doc),
        }


@dataclass(slots=True)
class MongoActivityReport:
    database: str
    all_databases: bool
    include_system: bool
    window_seconds: float
    captured_at: datetime
    summary: MongoActivitySummary
    namespaces: list[MongoNamespaceActivity]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "kind": "mongo.activity.report",
            "database": self.database,
            "all_databases": self.all_databases,
            "include_system": self.include_system,
            "window_seconds": round(self.window_seconds, 3),
            "captured_at": self.captured_at.isoformat(),
            "summary": self.summary.to_dict(),
            "namespaces": [namespace.to_dict() for namespace in self.namespaces],
        }


@dataclass(slots=True)
class MongoProfileFinding:
    namespace: str
    operation: str
    plan_summary: str
    shape: str
    count: int
    total_millis: int
    avg_millis: float
    max_millis: int
    docs_examined: int
    keys_examined: int
    nreturned: int
    num_yields: int
    scan_ratio: float | None
    collection_scan: bool
    suggested_index: list[MongoIndexKey]
    suggestion_confidence: SuggestionConfidence | None
    suggestion_reason: str | None
    covering_index: list[MongoIndexKey]
    index_note: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "operation": self.operation,
            "plan_summary": self.plan_summary,
            "shape": self.shape,
            "count": self.count,
            "total_millis": self.total_millis,
            "avg_millis": round(self.avg_millis, 3),
            "max_millis": self.max_millis,
            "docs_examined": self.docs_examined,
            "keys_examined": self.keys_examined,
            "nreturned": self.nreturned,
            "num_yields": self.num_yields,
            "scan_ratio": _round_or_none(self.scan_ratio),
            "collection_scan": self.collection_scan,
            "suggested_index": [key.to_dict() for key in self.suggested_index],
            "suggestion_confidence": self.suggestion_confidence,
            "suggestion_reason": self.suggestion_reason,
            "covering_index": [key.to_dict() for key in self.covering_index],
            "index_note": self.index_note,
        }


@dataclass(slots=True)
class MongoProfileReport:
    database: str
    window_seconds: float
    captured_at: datetime
    profiler_level: int
    slowms: int
    sample_rate: float
    include_writes: bool
    total_profile_docs: int
    matched_profile_docs: int
    truncated: bool
    max_profile_docs: int
    namespace_filters: list[str]
    exclude_namespace_filters: list[str]
    only_collection_scans: bool
    only_suggestions: bool
    min_count: int
    min_total_millis: int
    min_docs_examined: int
    min_scan_ratio: float
    findings: list[MongoProfileFinding]
    index_candidates: list[MongoIndexCandidate]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "kind": "mongo.profile.report",
            "database": self.database,
            "window_seconds": round(self.window_seconds, 3),
            "captured_at": self.captured_at.isoformat(),
            "profiler_level": self.profiler_level,
            "slowms": self.slowms,
            "sample_rate": round(self.sample_rate, 3),
            "include_writes": self.include_writes,
            "total_profile_docs": self.total_profile_docs,
            "matched_profile_docs": self.matched_profile_docs,
            "truncated": self.truncated,
            "max_profile_docs": self.max_profile_docs,
            "namespace_filters": self.namespace_filters,
            "exclude_namespace_filters": self.exclude_namespace_filters,
            "only_collection_scans": self.only_collection_scans,
            "only_suggestions": self.only_suggestions,
            "min_count": self.min_count,
            "min_total_millis": self.min_total_millis,
            "min_docs_examined": self.min_docs_examined,
            "min_scan_ratio": round(self.min_scan_ratio, 3),
            "findings": [finding.to_dict() for finding in self.findings],
            "index_candidates": [candidate.to_dict() for candidate in self.index_candidates],
        }


async def sample_activity(
    client: Any,
    *,
    database: str,
    window_seconds: float,
    limit: int,
    sort: ActivitySort,
    include_system: bool = False,
    all_databases: bool = False,
    namespace_filters: list[str] | None = None,
    exclude_namespace_filters: list[str] | None = None,
    status_callback: Callable[[str], None] | None = None,
) -> MongoActivityReport:
    before = await collect_activity_snapshot(client)
    if status_callback is not None:
        status_callback(
            f"Mongo activity sampling started for `{database}`. Waiting {window_seconds:.1f}s..."
        )
    await asyncio.sleep(window_seconds)
    after = await collect_activity_snapshot(client)
    return build_activity_report(
        before,
        after,
        database=database,
        limit=limit,
        sort=sort,
        include_system=include_system,
        all_databases=all_databases,
        namespace_filters=namespace_filters,
        exclude_namespace_filters=exclude_namespace_filters,
    )


async def collect_activity_snapshot(client: Any) -> MongoActivitySnapshot:
    admin_db = client["admin"]
    try:
        server_status = await admin_db.command({"serverStatus": 1})
        top = await admin_db.command({"top": 1})
    except OperationFailure as exc:
        raise RuntimeError(
            "Mongo activity sampling requires access to the admin commands "
            "`serverStatus` and `top`."
        ) from exc

    op_latencies = server_status.get("opLatencies") or {}
    query_executor = (server_status.get("metrics") or {}).get("queryExecutor") or {}
    documents = (server_status.get("metrics") or {}).get("document") or {}
    opcounters = server_status.get("opcounters") or {}

    return MongoActivitySnapshot(
        captured_at=datetime.now(UTC),
        opcounters_query=_int(opcounters.get("query")),
        opcounters_getmore=_int(opcounters.get("getmore")),
        opcounters_command=_int(opcounters.get("command")),
        opcounters_insert=_int(opcounters.get("insert")),
        opcounters_update=_int(opcounters.get("update")),
        opcounters_delete=_int(opcounters.get("delete")),
        docs_returned=_int(documents.get("returned")),
        docs_inserted=_int(documents.get("inserted")),
        docs_updated=_int(documents.get("updated")),
        docs_deleted=_int(documents.get("deleted")),
        scanned=_int(query_executor.get("scanned")),
        scanned_objects=_int(query_executor.get("scannedObjects")),
        collection_scans=_int(((query_executor.get("collectionScans") or {}).get("total"))),
        read_latency_micros=_int((op_latencies.get("reads") or {}).get("latency")),
        read_ops=_int((op_latencies.get("reads") or {}).get("ops")),
        write_latency_micros=_int((op_latencies.get("writes") or {}).get("latency")),
        write_ops=_int((op_latencies.get("writes") or {}).get("ops")),
        command_latency_micros=_int((op_latencies.get("commands") or {}).get("latency")),
        command_ops=_int((op_latencies.get("commands") or {}).get("ops")),
        top_totals=top.get("totals") or {},
    )


def build_activity_report(
    before: MongoActivitySnapshot,
    after: MongoActivitySnapshot,
    *,
    database: str,
    limit: int,
    sort: ActivitySort,
    include_system: bool = False,
    all_databases: bool = False,
    namespace_filters: list[str] | None = None,
    exclude_namespace_filters: list[str] | None = None,
) -> MongoActivityReport:
    window_seconds = max((after.captured_at - before.captured_at).total_seconds(), 0.001)
    summary = MongoActivitySummary(
        reads_per_s=_per_second(
            _delta(after.read_ops, before.read_ops),
            window_seconds,
        ),
        writes_per_s=_per_second(
            _delta(after.write_ops, before.write_ops),
            window_seconds,
        ),
        commands_per_s=_per_second(
            _delta(after.command_ops, before.command_ops),
            window_seconds,
        ),
        docs_returned_per_s=_per_second(
            _delta(after.docs_returned, before.docs_returned),
            window_seconds,
        ),
        docs_inserted_per_s=_per_second(
            _delta(after.docs_inserted, before.docs_inserted),
            window_seconds,
        ),
        docs_updated_per_s=_per_second(
            _delta(after.docs_updated, before.docs_updated),
            window_seconds,
        ),
        docs_deleted_per_s=_per_second(
            _delta(after.docs_deleted, before.docs_deleted),
            window_seconds,
        ),
        collection_scans_per_s=_per_second(
            _delta(after.collection_scans, before.collection_scans),
            window_seconds,
        ),
        avg_read_ms=_avg_latency_ms(
            after.read_latency_micros,
            before.read_latency_micros,
            after.read_ops,
            before.read_ops,
        ),
        avg_write_ms=_avg_latency_ms(
            after.write_latency_micros,
            before.write_latency_micros,
            after.write_ops,
            before.write_ops,
        ),
        avg_command_ms=_avg_latency_ms(
            after.command_latency_micros,
            before.command_latency_micros,
            after.command_ops,
            before.command_ops,
        ),
        scanned_objects_per_returned_doc=_safe_ratio(
            _delta(after.scanned_objects, before.scanned_objects),
            _delta(after.docs_returned, before.docs_returned),
        ),
    )

    namespaces: list[MongoNamespaceActivity] = []
    for namespace, metrics in after.top_totals.items():
        if not _should_include_namespace(
            namespace,
            database=database,
            include_system=include_system,
            all_databases=all_databases,
            namespace_filters=namespace_filters,
            exclude_namespace_filters=exclude_namespace_filters,
        ):
            continue

        previous_metrics = before.top_totals.get(namespace) or {}
        namespace_activity = _build_namespace_activity(
            namespace,
            previous_metrics,
            metrics,
            window_seconds=window_seconds,
        )
        if namespace_activity.total_ops == 0 and namespace_activity.total_time_ms == 0:
            continue
        namespaces.append(namespace_activity)

    sort_key = {
        "read-time": lambda item: (item.read_time_ms_per_s, item.total_time_ms_per_s),
        "read-ops": lambda item: (item.read_ops_per_s, item.total_ops_per_s),
        "total-time": lambda item: (item.total_time_ms_per_s, item.read_time_ms_per_s),
        "write-time": lambda item: (item.write_time_ms_per_s, item.total_time_ms_per_s),
    }[sort]
    namespaces.sort(key=sort_key, reverse=True)
    if limit > 0:
        namespaces = namespaces[:limit]

    return MongoActivityReport(
        database=database,
        all_databases=all_databases,
        include_system=include_system,
        window_seconds=window_seconds,
        captured_at=after.captured_at,
        summary=summary,
        namespaces=namespaces,
    )


async def capture_profile_report(
    db: Any,
    *,
    window_seconds: float,
    slowms: int,
    sample_rate: float,
    limit: int,
    max_profile_docs: int,
    sort: ProfileSort,
    include_writes: bool = False,
    capture_all: bool = False,
    namespace_filters: list[str] | None = None,
    exclude_namespace_filters: list[str] | None = None,
    only_collection_scans: bool = False,
    only_suggestions: bool = False,
    min_count: int = 1,
    min_total_millis: int = 0,
    min_docs_examined: int = 0,
    min_scan_ratio: float = 0.0,
    status_callback: Callable[[str], None] | None = None,
) -> MongoProfileReport:
    try:
        original = await db.command({"profile": -1})
    except OperationFailure as exc:
        raise RuntimeError(
            f"Mongo profiler inspection requires permission to read profiler settings for database `{db.name}`."
        ) from exc

    profiler_level = 2 if capture_all else 1
    effective_slowms = 0 if capture_all else slowms
    enable_command: dict[str, Any] = {
        "profile": profiler_level,
        "slowms": effective_slowms,
    }
    if sample_rate < 1.0:
        enable_command["sampleRate"] = sample_rate

    start_at = datetime.now(UTC)
    end_at = start_at
    enabled = False
    try:
        try:
            await db.command(enable_command)
        except OperationFailure as exc:
            raise RuntimeError(
                f"Mongo profiler could not be enabled for database `{db.name}`. "
                "This command changes the database profiler level for the selected window."
            ) from exc
        enabled = True
        start_at = datetime.now(UTC)
        if status_callback is not None:
            status_callback(
                f"Mongo profiler enabled for `{db.name}`. Capturing for {window_seconds:.1f}s..."
            )
        await asyncio.sleep(window_seconds)
        end_at = datetime.now(UTC)
    finally:
        if enabled:
            restore_command: dict[str, Any] = {"profile": _int(original.get("was"))}
            if "slowms" in original:
                restore_command["slowms"] = _int(original.get("slowms"))
            if "sampleRate" in original:
                restore_command["sampleRate"] = float(original.get("sampleRate"))
            try:
                await db.command(restore_command)
            except OperationFailure as exc:
                raise RuntimeError(
                    f"Mongo profiler settings for database `{db.name}` could not be restored automatically. "
                    "Check the current profiler state and restore it manually."
                ) from exc

    if PROFILE_ROW_SETTLE_SECONDS > 0:
        await asyncio.sleep(PROFILE_ROW_SETTLE_SECONDS)

    raw_docs = await _read_profile_docs(
        db["system.profile"],
        database_name=db.name,
        start_at=start_at,
        end_at=end_at,
        max_profile_docs=max_profile_docs,
    )

    truncated = len(raw_docs) > max_profile_docs
    if truncated:
        raw_docs = raw_docs[:max_profile_docs]

    namespace_indexes = await _collect_namespace_indexes(
        db,
        raw_docs,
        database=db.name,
        namespace_filters=namespace_filters,
        exclude_namespace_filters=exclude_namespace_filters,
    )

    return build_profile_report(
        raw_docs,
        database=db.name,
        window_seconds=window_seconds,
        profiler_level=profiler_level,
        slowms=effective_slowms,
        sample_rate=sample_rate,
        include_writes=include_writes,
        limit=limit,
        max_profile_docs=max_profile_docs,
        sort=sort,
        captured_at=end_at,
        truncated=truncated,
        namespace_filters=namespace_filters,
        exclude_namespace_filters=exclude_namespace_filters,
        only_collection_scans=only_collection_scans,
        only_suggestions=only_suggestions,
        min_count=min_count,
        min_total_millis=min_total_millis,
        min_docs_examined=min_docs_examined,
        min_scan_ratio=min_scan_ratio,
        namespace_indexes=namespace_indexes,
    )


async def _read_profile_docs(
    profile_collection: Any,
    *,
    database_name: str,
    start_at: datetime,
    end_at: datetime,
    max_profile_docs: int,
) -> list[dict[str, Any]]:
    for attempt, retry_delay in enumerate((0.0, *PROFILE_READ_RETRY_DELAYS)):
        if retry_delay > 0:
            await asyncio.sleep(retry_delay)
        try:
            raw_docs = await profile_collection.find(
                {"ts": {"$gte": start_at, "$lte": end_at}},
                PROFILE_DOC_PROJECTION,
            ).sort("ts", 1).limit(max_profile_docs + 1).to_list(length=max_profile_docs + 1)
        except OperationFailure as exc:
            raise RuntimeError(
                f"Mongo profiler rows could not be read from `{database_name}.system.profile`."
            ) from exc
        if raw_docs or attempt == len(PROFILE_READ_RETRY_DELAYS):
            return raw_docs
    return []


def build_profile_report(
    raw_docs: list[dict[str, Any]],
    *,
    database: str,
    window_seconds: float,
    profiler_level: int,
    slowms: int,
    sample_rate: float,
    include_writes: bool,
    limit: int,
    max_profile_docs: int = 0,
    sort: ProfileSort,
    captured_at: datetime | None = None,
    truncated: bool = False,
    namespace_filters: list[str] | None = None,
    exclude_namespace_filters: list[str] | None = None,
    only_collection_scans: bool = False,
    only_suggestions: bool = False,
    min_count: int = 1,
    min_total_millis: int = 0,
    min_docs_examined: int = 0,
    min_scan_ratio: float = 0.0,
    namespace_indexes: dict[str, list[list[MongoIndexKey]]] | None = None,
) -> MongoProfileReport:
    findings_by_signature: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    matched_profile_docs = 0

    for raw_doc in raw_docs:
        namespace = str(raw_doc.get("ns") or "")
        if not namespace.startswith(f"{database}."):
            continue
        if namespace.startswith(f"{database}.system."):
            continue
        if not _namespace_allowed(
            namespace,
            database=database,
            namespace_filters=namespace_filters,
            exclude_namespace_filters=exclude_namespace_filters,
        ):
            continue

        operation = _extract_operation_name(raw_doc)
        if not operation or operation == "profile":
            continue
        if not include_writes and _is_write_operation(operation):
            continue
        if include_writes is False and not _is_read_operation(operation):
            continue

        matched_profile_docs += 1
        plan_summary = str(raw_doc.get("planSummary") or "-")
        shape_info = _extract_shape_info(raw_doc, operation)
        shape = shape_info.label
        signature = (namespace, operation, plan_summary, shape)
        bucket = findings_by_signature.setdefault(
            signature,
            {
                "namespace": namespace,
                "operation": operation,
                "plan_summary": plan_summary,
                "shape": shape,
                "shape_info": shape_info,
                "count": 0,
                "total_millis": 0,
                "max_millis": 0,
                "docs_examined": 0,
                "keys_examined": 0,
                "nreturned": 0,
                "num_yields": 0,
            },
        )
        millis = _int(raw_doc.get("millis"))
        bucket["count"] += 1
        bucket["total_millis"] += millis
        bucket["max_millis"] = max(bucket["max_millis"], millis)
        bucket["docs_examined"] += _int(raw_doc.get("docsExamined"))
        bucket["keys_examined"] += _int(raw_doc.get("keysExamined"))
        bucket["nreturned"] += _int(raw_doc.get("nreturned"))
        bucket["num_yields"] += _int(raw_doc.get("numYield"))

    findings: list[MongoProfileFinding] = []
    for bucket in findings_by_signature.values():
        scan_ratio = _safe_ratio(bucket["docs_examined"], bucket["nreturned"])
        collection_scan = "COLLSCAN" in bucket["plan_summary"].upper()
        if only_collection_scans and not collection_scan:
            continue
        if bucket["count"] < min_count:
            continue
        if bucket["total_millis"] < min_total_millis:
            continue
        if bucket["docs_examined"] < min_docs_examined:
            continue
        if (scan_ratio or 0.0) < min_scan_ratio:
            continue

        suggested_index, suggestion_confidence, suggestion_reason, covering_index, index_note = _build_index_suggestion(
            operation=bucket["operation"],
            shape_info=bucket["shape_info"],
            plan_summary=bucket["plan_summary"],
            count=bucket["count"],
            total_millis=bucket["total_millis"],
            docs_examined=bucket["docs_examined"],
            nreturned=bucket["nreturned"],
            collection_scan=collection_scan,
            existing_indexes=(namespace_indexes or {}).get(bucket["namespace"], []),
        )
        if only_suggestions and not suggested_index:
            continue

        findings.append(
            MongoProfileFinding(
                namespace=bucket["namespace"],
                operation=bucket["operation"],
                plan_summary=bucket["plan_summary"],
                shape=bucket["shape"],
                count=bucket["count"],
                total_millis=bucket["total_millis"],
                avg_millis=bucket["total_millis"] / max(bucket["count"], 1),
                max_millis=bucket["max_millis"],
                docs_examined=bucket["docs_examined"],
                keys_examined=bucket["keys_examined"],
                nreturned=bucket["nreturned"],
                num_yields=bucket["num_yields"],
                scan_ratio=scan_ratio,
                collection_scan=collection_scan,
                suggested_index=suggested_index,
                suggestion_confidence=suggestion_confidence,
                suggestion_reason=suggestion_reason,
                covering_index=covering_index,
                index_note=index_note,
            )
        )

    sort_key = {
        "total-millis": lambda item: (item.total_millis, item.avg_millis),
        "avg-millis": lambda item: (item.avg_millis, item.total_millis),
        "max-millis": lambda item: (item.max_millis, item.total_millis),
        "docs-examined": lambda item: (item.docs_examined, item.total_millis),
        "scan-ratio": lambda item: ((item.scan_ratio or 0.0), item.total_millis),
    }[sort]
    findings.sort(key=sort_key, reverse=True)
    if limit > 0:
        findings = findings[:limit]

    index_candidates = _build_index_candidates(findings)

    return MongoProfileReport(
        database=database,
        window_seconds=window_seconds,
        captured_at=captured_at or datetime.now(UTC),
        profiler_level=profiler_level,
        slowms=slowms,
        sample_rate=sample_rate,
        include_writes=include_writes,
        total_profile_docs=len(raw_docs),
        matched_profile_docs=matched_profile_docs,
        truncated=truncated,
        max_profile_docs=max_profile_docs,
        namespace_filters=list(namespace_filters or []),
        exclude_namespace_filters=list(exclude_namespace_filters or []),
        only_collection_scans=only_collection_scans,
        only_suggestions=only_suggestions,
        min_count=min_count,
        min_total_millis=min_total_millis,
        min_docs_examined=min_docs_examined,
        min_scan_ratio=min_scan_ratio,
        findings=findings,
        index_candidates=index_candidates,
    )


def _build_namespace_activity(
    namespace: str,
    previous_metrics: dict[str, Any],
    current_metrics: dict[str, Any],
    *,
    window_seconds: float,
) -> MongoNamespaceActivity:
    read_ops = sum(
        [
            _counter_delta(previous_metrics, current_metrics, "queries", "count"),
            _counter_delta(previous_metrics, current_metrics, "getmore", "count"),
            _counter_delta(previous_metrics, current_metrics, "commands", "count"),
        ]
    )
    write_ops = sum(
        [
            _counter_delta(previous_metrics, current_metrics, "insert", "count"),
            _counter_delta(previous_metrics, current_metrics, "update", "count"),
            _counter_delta(previous_metrics, current_metrics, "remove", "count"),
        ]
    )
    total_ops = _counter_delta(previous_metrics, current_metrics, "total", "count")
    read_time_ms = (
        _counter_delta(previous_metrics, current_metrics, "queries", "time")
        + _counter_delta(previous_metrics, current_metrics, "getmore", "time")
        + _counter_delta(previous_metrics, current_metrics, "commands", "time")
    ) / 1000
    write_time_ms = (
        _counter_delta(previous_metrics, current_metrics, "insert", "time")
        + _counter_delta(previous_metrics, current_metrics, "update", "time")
        + _counter_delta(previous_metrics, current_metrics, "remove", "time")
    ) / 1000
    total_time_ms = _counter_delta(previous_metrics, current_metrics, "total", "time") / 1000

    return MongoNamespaceActivity(
        namespace=namespace,
        read_ops=read_ops,
        write_ops=write_ops,
        total_ops=total_ops,
        read_ops_per_s=_per_second(read_ops, window_seconds),
        write_ops_per_s=_per_second(write_ops, window_seconds),
        total_ops_per_s=_per_second(total_ops, window_seconds),
        read_time_ms=read_time_ms,
        write_time_ms=write_time_ms,
        total_time_ms=total_time_ms,
        read_time_ms_per_s=_per_second(read_time_ms, window_seconds),
        write_time_ms_per_s=_per_second(write_time_ms, window_seconds),
        total_time_ms_per_s=_per_second(total_time_ms, window_seconds),
    )


def _counter_delta(previous_metrics: dict[str, Any], current_metrics: dict[str, Any], section: str, key: str) -> int:
    previous_value = (previous_metrics.get(section) or {}).get(key)
    current_value = (current_metrics.get(section) or {}).get(key)
    return _delta(_int(current_value), _int(previous_value))


def _should_include_namespace(
    namespace: str,
    *,
    database: str,
    include_system: bool,
    all_databases: bool,
    namespace_filters: list[str] | None = None,
    exclude_namespace_filters: list[str] | None = None,
) -> bool:
    if not all_databases and not namespace.startswith(f"{database}."):
        return False
    if not _namespace_allowed(
        namespace,
        database=database,
        namespace_filters=namespace_filters,
        exclude_namespace_filters=exclude_namespace_filters,
    ):
        return False
    if include_system:
        return True
    return ".system." not in namespace


def _namespace_allowed(
    namespace: str,
    *,
    database: str,
    namespace_filters: list[str] | None,
    exclude_namespace_filters: list[str] | None,
) -> bool:
    if namespace_filters and not any(
        _namespace_matches_filter(namespace, database=database, candidate=candidate)
        for candidate in namespace_filters
    ):
        return False
    if exclude_namespace_filters and any(
        _namespace_matches_filter(namespace, database=database, candidate=candidate)
        for candidate in exclude_namespace_filters
    ):
        return False
    return True


def _namespace_matches_filter(namespace: str, *, database: str, candidate: str) -> bool:
    normalized = candidate.strip()
    if normalized == "":
        return False
    collection_name = namespace.removeprefix(f"{database}.")
    if normalized == namespace or normalized == collection_name:
        return True
    return False


async def _collect_namespace_indexes(
    db: Any,
    raw_docs: list[dict[str, Any]],
    *,
    database: str,
    namespace_filters: list[str] | None,
    exclude_namespace_filters: list[str] | None,
) -> dict[str, list[list[MongoIndexKey]]]:
    namespaces = {
        namespace
        for raw_doc in raw_docs
        if isinstance(raw_doc, dict)
        for namespace in [str(raw_doc.get("ns") or "")]
        if namespace.startswith(f"{database}.")
        and not namespace.startswith(f"{database}.system.")
        and _namespace_allowed(
            namespace,
            database=database,
            namespace_filters=namespace_filters,
            exclude_namespace_filters=exclude_namespace_filters,
        )
    }
    namespace_indexes: dict[str, list[list[MongoIndexKey]]] = {}
    for namespace in namespaces:
        collection_name = namespace.removeprefix(f"{database}.")
        try:
            index_docs = await db[collection_name].list_indexes().to_list(length=None)
        except OperationFailure:
            continue
        namespace_indexes[namespace] = [
            [
                MongoIndexKey(field=str(field), direction=_normalize_index_direction(direction))
                for field, direction in (index_doc.get("key") or {}).items()
            ]
            for index_doc in index_docs
            if isinstance(index_doc.get("key"), dict)
        ]
    return namespace_indexes


def _normalize_index_direction(value: Any) -> int:
    return -1 if value == -1 else 1


def _extract_operation_name(raw_doc: dict[str, Any]) -> str:
    command = raw_doc.get("command")
    if isinstance(command, dict):
        for key in command.keys():
            if key in {"$db", "lsid", "$clusterTime", "$readPreference"}:
                continue
            return str(key)

    if isinstance(raw_doc.get("query"), dict):
        return "query"

    return str(raw_doc.get("op") or "").strip()


def _extract_shape_info(raw_doc: dict[str, Any], operation: str) -> _MongoShapeInfo:
    command = raw_doc.get("command")
    if not isinstance(command, dict):
        command = raw_doc.get("query") if isinstance(raw_doc.get("query"), dict) else {}

    normalized_operation = operation.lower()
    equality_fields: list[str] = []
    range_fields: list[str] = []
    sort_fields: list[tuple[str, int]] = []
    stage_names: list[str] = []

    if normalized_operation == "find":
        equality_fields, range_fields = _classify_filter_fields(command.get("filter"))
        sort_fields = _extract_sort_fields(command.get("sort"))
    elif normalized_operation == "aggregate":
        equality_fields, range_fields, sort_fields, stage_names = _extract_pipeline_shape(command.get("pipeline"))
    elif normalized_operation in {"count", "distinct"}:
        equality_fields, range_fields = _classify_filter_fields(command.get("query"))
    elif normalized_operation == "update":
        updates = command.get("updates")
        if isinstance(updates, list) and updates:
            equality_fields, range_fields = _classify_filter_fields((updates[0] or {}).get("q"))
    elif normalized_operation == "delete":
        deletes = command.get("deletes")
        if isinstance(deletes, list) and deletes:
            equality_fields, range_fields = _classify_filter_fields((deletes[0] or {}).get("q"))
    elif normalized_operation == "query":
        equality_fields, range_fields = _classify_filter_fields(command)
        sort_fields = _extract_sort_fields(command.get("orderby"))

    label = _build_shape_label(
        equality_fields=equality_fields,
        range_fields=range_fields,
        sort_fields=sort_fields,
        stage_names=stage_names,
    )
    return _MongoShapeInfo(
        label=label,
        equality_fields=equality_fields,
        range_fields=range_fields,
        sort_fields=sort_fields,
    )


def _build_shape_label(
    *,
    equality_fields: list[str],
    range_fields: list[str],
    sort_fields: list[tuple[str, int]],
    stage_names: list[str],
) -> str:
    parts: list[str] = []
    filter_fields = equality_fields + [field for field in range_fields if field not in equality_fields]
    if filter_fields:
        parts.append(f"filter={','.join(filter_fields)}")
    if sort_fields:
        parts.append("sort=" + ",".join(field for field, _ in sort_fields))
    if stage_names:
        stage_preview = ",".join(stage_names[:4])
        if len(stage_names) > 4:
            stage_preview += ",..."
        parts.append(f"stages={stage_preview}")
    if not parts:
        return "-"
    return " ".join(parts)


def _classify_filter_fields(value: Any) -> tuple[list[str], list[str]]:
    equality_fields: list[str] = []
    range_fields: list[str] = []

    def visit(document: Any) -> None:
        if not isinstance(document, dict):
            return
        for key, operand in document.items():
            if key in LOGICAL_OPERATORS and isinstance(operand, list):
                for branch in operand:
                    visit(branch)
                continue
            if key.startswith("$"):
                continue
            if _is_equality_condition(operand):
                _append_unique(equality_fields, str(key))
                continue
            _append_unique(range_fields, str(key))

    visit(value)
    return equality_fields, range_fields


def _is_equality_condition(value: Any) -> bool:
    if not isinstance(value, dict):
        return True
    operators = {str(key) for key in value.keys() if str(key).startswith("$")}
    if not operators:
        return True
    if "$elemMatch" in operators:
        return False
    if operators.issubset(EQ_LIKE_OPERATORS):
        return True
    if operators & RANGE_LIKE_OPERATORS:
        return False
    return False


def _extract_sort_fields(value: Any) -> list[tuple[str, int]]:
    if not isinstance(value, dict):
        return []
    fields: list[tuple[str, int]] = []
    for field, direction in value.items():
        field_name = str(field)
        if field_name.startswith("$"):
            continue
        fields.append((field_name, -1 if direction == -1 else 1))
    return fields


def _extract_pipeline_shape(value: Any) -> tuple[list[str], list[str], list[tuple[str, int]], list[str]]:
    if not isinstance(value, list):
        return [], [], [], []

    equality_fields: list[str] = []
    range_fields: list[str] = []
    sort_fields: list[tuple[str, int]] = []
    stage_names: list[str] = []

    for stage in value:
        if not isinstance(stage, dict) or not stage:
            continue
        stage_name, stage_value = next(iter(stage.items()))
        stage_names.append(str(stage_name))

        if stage_name == "$match":
            eq_fields, range_stage_fields = _classify_filter_fields(stage_value)
            _extend_unique(equality_fields, eq_fields)
            _extend_unique(range_fields, range_stage_fields)
            continue

        if stage_name == "$sort":
            for field, direction in _extract_sort_fields(stage_value):
                if field not in {existing_field for existing_field, _ in sort_fields}:
                    sort_fields.append((field, direction))
            continue

        if stage_name in {"$limit", "$skip"}:
            continue

        break

    return equality_fields, range_fields, sort_fields, stage_names


def _build_index_keys(shape_info: _MongoShapeInfo) -> list[MongoIndexKey]:
    keys: list[MongoIndexKey] = []
    seen_fields: set[str] = set()

    for field in shape_info.equality_fields:
        if field in seen_fields:
            continue
        seen_fields.add(field)
        keys.append(MongoIndexKey(field=field, direction=1))

    for field, direction in shape_info.sort_fields:
        if field in seen_fields:
            continue
        seen_fields.add(field)
        keys.append(MongoIndexKey(field=field, direction=direction))

    for field in shape_info.range_fields:
        if field in seen_fields:
            continue
        seen_fields.add(field)
        keys.append(MongoIndexKey(field=field, direction=1))

    return keys


def _build_index_suggestion(
    *,
    operation: str,
    shape_info: _MongoShapeInfo,
    plan_summary: str,
    count: int,
    total_millis: int,
    docs_examined: int,
    nreturned: int,
    collection_scan: bool,
    existing_indexes: list[list[MongoIndexKey]],
) -> tuple[
    list[MongoIndexKey],
    SuggestionConfidence | None,
    str | None,
    list[MongoIndexKey],
    str | None,
]:
    if "_id" in shape_info.equality_fields:
        return [], None, None, [MongoIndexKey(field="_id", direction=1)], "Covered by _id lookup"

    suggested_index = _build_index_keys(shape_info)
    if not suggested_index:
        return [], None, None, [], None

    scan_ratio = _safe_ratio(docs_examined, nreturned)
    confidence = _suggestion_confidence(
        collection_scan=collection_scan,
        scan_ratio=scan_ratio,
        count=count,
        total_millis=total_millis,
        docs_examined=docs_examined,
    )
    if confidence == "low":
        return [], None, None, [], None
    covering_index = _find_covering_index(suggested_index, existing_indexes)
    if covering_index is not None:
        return [], None, None, covering_index, "Covered by existing index prefix"

    return (
        suggested_index,
        confidence,
        _suggestion_reason(
            operation=operation,
            shape_info=shape_info,
            collection_scan=collection_scan,
            scan_ratio=scan_ratio,
            total_millis=total_millis,
            docs_examined=docs_examined,
            plan_summary=plan_summary,
        ),
        [],
        None,
    )


def _find_covering_index(
    candidate: list[MongoIndexKey],
    existing_indexes: list[list[MongoIndexKey]],
) -> list[MongoIndexKey] | None:
    candidate_signature = [(key.field, key.direction) for key in candidate]
    for existing in existing_indexes:
        existing_signature = [(key.field, key.direction) for key in existing]
        if len(existing_signature) < len(candidate_signature):
            continue
        if existing_signature[: len(candidate_signature)] == candidate_signature:
            return existing
    return None


def _suggestion_confidence(
    *,
    collection_scan: bool,
    scan_ratio: float | None,
    count: int,
    total_millis: int,
    docs_examined: int,
) -> SuggestionConfidence:
    if collection_scan and (count >= 3 or docs_examined >= 100):
        return "high"
    if scan_ratio is not None and scan_ratio >= 50:
        return "high"
    if (
        (scan_ratio is not None and scan_ratio >= 20)
        or total_millis >= 100
        or (scan_ratio is not None and scan_ratio >= 3 and docs_examined >= 100)
    ):
        return "medium"
    return "low"


def _suggestion_reason(
    *,
    operation: str,
    shape_info: _MongoShapeInfo,
    collection_scan: bool,
    scan_ratio: float | None,
    total_millis: int,
    docs_examined: int,
    plan_summary: str,
) -> str:
    basis_parts: list[str] = []
    if shape_info.equality_fields or shape_info.range_fields:
        basis_parts.append("filter")
    if shape_info.sort_fields:
        basis_parts.append("sort")
    basis = "+".join(basis_parts) if basis_parts else "shape"

    if collection_scan:
        return f"Repeated {operation} COLLSCAN on {basis}"
    if scan_ratio is not None and scan_ratio >= 20:
        return f"High docsExamined/nreturned ratio on {operation} {basis}"
    if "IXSCAN" in plan_summary.upper() and scan_ratio is not None and scan_ratio >= 3:
        return f"Indexed {operation} still examines many documents for {basis}"
    if total_millis >= 100:
        return f"High cumulative latency on {operation} {basis}"
    return f"Repeated slow {operation} {basis}"


def _build_index_candidates(findings: list[MongoProfileFinding]) -> list[MongoIndexCandidate]:
    buckets: dict[tuple[str, tuple[tuple[str, int], ...]], dict[str, Any]] = {}

    for finding in findings:
        if not finding.suggested_index or finding.suggestion_confidence is None or finding.suggestion_reason is None:
            continue

        signature = (
            finding.namespace,
            tuple((key.field, key.direction) for key in finding.suggested_index),
        )
        bucket = buckets.setdefault(
            signature,
            {
                "namespace": finding.namespace,
                "keys": finding.suggested_index,
                "confidence": finding.suggestion_confidence,
                "source_operations": set(),
                "supporting_findings": 0,
                "observed_queries": 0,
                "total_millis": 0,
                "max_millis": 0,
                "worst_scan_ratio": None,
                "collection_scan": False,
                "reason": finding.suggestion_reason,
            },
        )
        bucket["source_operations"].add(finding.operation)
        bucket["supporting_findings"] += 1
        bucket["observed_queries"] += finding.count
        bucket["total_millis"] += finding.total_millis
        bucket["max_millis"] = max(bucket["max_millis"], finding.max_millis)
        bucket["worst_scan_ratio"] = _max_or_keep(bucket["worst_scan_ratio"], finding.scan_ratio)
        bucket["collection_scan"] = bucket["collection_scan"] or finding.collection_scan
        if _confidence_rank(finding.suggestion_confidence) > _confidence_rank(bucket["confidence"]):
            bucket["confidence"] = finding.suggestion_confidence
            bucket["reason"] = finding.suggestion_reason

    candidates = [
        MongoIndexCandidate(
            namespace=bucket["namespace"],
            keys=bucket["keys"],
            confidence=bucket["confidence"],
            source_operations=sorted(bucket["source_operations"]),
            supporting_findings=bucket["supporting_findings"],
            observed_queries=bucket["observed_queries"],
            total_millis=bucket["total_millis"],
            max_millis=bucket["max_millis"],
            worst_scan_ratio=bucket["worst_scan_ratio"],
            collection_scan=bucket["collection_scan"],
            reason=bucket["reason"],
        )
        for bucket in buckets.values()
    ]
    candidates.sort(
        key=lambda item: (
            item.collection_scan,
            _confidence_rank(item.confidence),
            item.total_millis,
            item.observed_queries,
            item.worst_scan_ratio or 0.0,
        ),
        reverse=True,
    )
    return candidates


def _confidence_rank(value: SuggestionConfidence) -> int:
    return {
        "low": 0,
        "medium": 1,
        "high": 2,
    }[value]


def _append_unique(values: list[str], item: str) -> None:
    if item not in values:
        values.append(item)


def _extend_unique(values: list[str], items: list[str]) -> None:
    for item in items:
        _append_unique(values, item)


def _max_or_keep(current: float | None, candidate: float | None) -> float | None:
    if current is None:
        return candidate
    if candidate is None:
        return current
    return max(current, candidate)


def _is_write_operation(operation: str) -> bool:
    return operation.lower() in WRITE_OPERATIONS


def _is_read_operation(operation: str) -> bool:
    return operation.lower() in READ_OPERATIONS


def _avg_latency_ms(current_latency_micros: int, previous_latency_micros: int, current_ops: int, previous_ops: int) -> float | None:
    operations = _delta(current_ops, previous_ops)
    if operations <= 0:
        return None
    return (_delta(current_latency_micros, previous_latency_micros) / operations) / 1000


def _delta(current: int, previous: int) -> int:
    return max(current - previous, 0)


def _per_second(value: int | float, window_seconds: float) -> float:
    return float(value) / max(window_seconds, 0.001)


def _safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    if denominator <= 0:
        return None
    return float(numerator) / float(denominator)


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _round_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 3)


__all__ = [
    "MongoActivityReport",
    "MongoActivitySnapshot",
    "MongoProfileReport",
    "build_activity_report",
    "build_profile_report",
    "capture_profile_report",
    "sample_activity",
]
