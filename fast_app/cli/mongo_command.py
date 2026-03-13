from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import OperationFailure

from fast_app.utils.env_utils import configure_env_from_app_config
from fast_app.utils.mongo_diagnostics import (
    MongoActivityReport,
    MongoIndexKey,
    MongoProfileReport,
    capture_profile_report,
    sample_activity,
)
from .command_base import CommandBase


class MongoCommand(CommandBase):
    @property
    def name(self) -> str:
        return "mongo"

    @property
    def help(self) -> str:
        return "Inspect MongoDB activity and temporary profiler findings"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        subparsers = parser.add_subparsers(dest="action", required=True)

        stats_parser = subparsers.add_parser(
            "stats",
            help="Sample low-overhead MongoDB activity over a short window",
        )
        stats_parser.add_argument(
            "--seconds",
            type=float,
            default=5.0,
            help="Sample window in seconds",
        )
        stats_parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="Maximum namespaces to print",
        )
        stats_parser.add_argument(
            "--sort",
            choices=["read-time", "read-ops", "total-time", "write-time"],
            default="read-time",
            help="Sort order for namespace rows",
        )
        stats_parser.add_argument(
            "--database",
            help="Override the database name from the environment",
        )
        stats_parser.add_argument(
            "--namespace",
            action="append",
            default=[],
            help="Repeatable namespace or collection filter (for example `lead` or `db.lead`)",
        )
        stats_parser.add_argument(
            "--exclude-namespace",
            action="append",
            default=[],
            help="Repeatable namespace or collection exclusion",
        )
        stats_parser.add_argument(
            "--all-databases",
            action="store_true",
            help="Do not filter namespace rows to the current app database",
        )
        stats_parser.add_argument(
            "--include-system",
            action="store_true",
            help="Include system namespaces in the namespace table",
        )
        stats_parser.add_argument(
            "--json",
            action="store_true",
            help="Print structured JSON instead of the human-readable table",
        )

        profile_parser = subparsers.add_parser(
            "profile",
            help="Temporarily enable the MongoDB profiler and summarize query shapes",
        )
        profile_parser.add_argument(
            "--dangerously-enable-profiler",
            action="store_true",
            help="Required: acknowledge that this temporarily changes the selected database profiler state",
        )
        profile_parser.add_argument(
            "--seconds",
            type=float,
            default=15.0,
            help="How long to keep the profiler enabled",
        )
        profile_parser.add_argument(
            "--slowms",
            type=int,
            default=25,
            help="Minimum duration in milliseconds when using level 1 profiling",
        )
        profile_parser.add_argument(
            "--sample-rate",
            type=float,
            default=1.0,
            help="MongoDB profiler sampleRate value",
        )
        profile_parser.add_argument(
            "--capture-all",
            action="store_true",
            help="Use profiler level 2 for the window instead of only slow operations",
        )
        profile_parser.add_argument(
            "--include-writes",
            action="store_true",
            help="Include write operations in the summary",
        )
        profile_parser.add_argument(
            "--namespace",
            action="append",
            default=[],
            help="Repeatable namespace or collection filter (for example `lead` or `db.lead`)",
        )
        profile_parser.add_argument(
            "--exclude-namespace",
            action="append",
            default=[],
            help="Repeatable namespace or collection exclusion",
        )
        profile_parser.add_argument(
            "--only-collection-scans",
            action="store_true",
            help="Keep only findings that used a collection scan",
        )
        profile_parser.add_argument(
            "--only-suggestions",
            action="store_true",
            help="Keep only findings that still have an index candidate after heuristic checks",
        )
        profile_parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="Maximum grouped findings to print",
        )
        profile_parser.add_argument(
            "--max-profile-docs",
            type=int,
            default=2000,
            help="Hard cap on `system.profile` rows to scan for the selected window",
        )
        profile_parser.add_argument(
            "--min-count",
            type=int,
            default=1,
            help="Minimum grouped occurrence count to keep",
        )
        profile_parser.add_argument(
            "--min-total-millis",
            type=int,
            default=0,
            help="Minimum cumulative millis to keep",
        )
        profile_parser.add_argument(
            "--min-docs-examined",
            type=int,
            default=0,
            help="Minimum grouped docsExamined to keep",
        )
        profile_parser.add_argument(
            "--min-scan-ratio",
            type=float,
            default=0.0,
            help="Minimum docsExamined/nreturned ratio to keep",
        )
        profile_parser.add_argument(
            "--sort",
            choices=["total-millis", "avg-millis", "max-millis", "docs-examined", "scan-ratio"],
            default="docs-examined",
            help="Sort order for grouped profiler findings",
        )
        profile_parser.add_argument(
            "--database",
            help="Override the database name from the environment",
        )
        profile_parser.add_argument(
            "--json",
            action="store_true",
            help="Print structured JSON instead of the human-readable table",
        )

    def execute(self, args: argparse.Namespace) -> None:
        configure_env_from_app_config()
        client: AsyncIOMotorClient | None = None
        try:
            self._validate_args(args)
            client = self._build_client()
            database = args.database or self._default_database_name()

            if args.action == "stats":
                asyncio.run(self._stats(args, client, database))
                return

            if args.action == "profile":
                if not args.dangerously_enable_profiler:
                    print(
                        "Mongo profile requires --dangerously-enable-profiler because it "
                        "temporarily changes the selected database profiler state."
                    )
                    raise SystemExit(2)
                asyncio.run(self._profile(args, client, database))
                return

            raise ValueError(f"Unknown mongo action: {args.action}")
        except SystemExit:
            raise
        except OperationFailure as exc:
            print(f"Mongo command failed: {exc}")
            raise SystemExit(1) from exc
        except Exception as exc:  # noqa: BLE001
            print(f"Mongo command failed: {exc}")
            raise SystemExit(1) from exc
        finally:
            if client is not None:
                client.close()

    async def _stats(
        self,
        args: argparse.Namespace,
        client: AsyncIOMotorClient,
        database: str,
    ) -> None:
        report = await sample_activity(
            client,
            database=database,
            window_seconds=args.seconds,
            limit=args.limit,
            sort=args.sort,
            include_system=args.include_system,
            all_databases=args.all_databases,
            namespace_filters=args.namespace,
            exclude_namespace_filters=args.exclude_namespace,
            status_callback=lambda message: print(message, file=sys.stderr, flush=True),
        )
        self._print_activity_report(report, json_output=args.json)

    async def _profile(
        self,
        args: argparse.Namespace,
        client: AsyncIOMotorClient,
        database: str,
    ) -> None:
        report = await capture_profile_report(
            client[database],
            window_seconds=args.seconds,
            slowms=args.slowms,
            sample_rate=args.sample_rate,
            limit=args.limit,
            max_profile_docs=args.max_profile_docs,
            sort=args.sort,
            include_writes=args.include_writes,
            capture_all=args.capture_all,
            namespace_filters=args.namespace,
            exclude_namespace_filters=args.exclude_namespace,
            only_collection_scans=args.only_collection_scans,
            only_suggestions=args.only_suggestions,
            min_count=args.min_count,
            min_total_millis=args.min_total_millis,
            min_docs_examined=args.min_docs_examined,
            min_scan_ratio=args.min_scan_ratio,
            status_callback=lambda message: print(message, file=sys.stderr, flush=True),
        )
        self._print_profile_report(report, json_output=args.json)

    @staticmethod
    def _validate_args(args: argparse.Namespace) -> None:
        if args.seconds <= 0:
            print("Mongo command failed: --seconds must be greater than 0.")
            raise SystemExit(2)
        if args.limit < 0:
            print("Mongo command failed: --limit must be 0 or greater.")
            raise SystemExit(2)

        if args.action != "profile":
            return

        if args.slowms < 0:
            print("Mongo command failed: --slowms must be 0 or greater.")
            raise SystemExit(2)
        if args.max_profile_docs <= 0:
            print("Mongo command failed: --max-profile-docs must be greater than 0.")
            raise SystemExit(2)
        if args.min_count <= 0:
            print("Mongo command failed: --min-count must be greater than 0.")
            raise SystemExit(2)
        if args.min_total_millis < 0:
            print("Mongo command failed: --min-total-millis must be 0 or greater.")
            raise SystemExit(2)
        if args.min_docs_examined < 0:
            print("Mongo command failed: --min-docs-examined must be 0 or greater.")
            raise SystemExit(2)
        if args.min_scan_ratio < 0:
            print("Mongo command failed: --min-scan-ratio must be 0 or greater.")
            raise SystemExit(2)
        if not 0.0 <= args.sample_rate <= 1.0:
            print("Mongo command failed: --sample-rate must be between 0.0 and 1.0.")
            raise SystemExit(2)

    @staticmethod
    def _print_activity_report(report: MongoActivityReport, *, json_output: bool = False) -> None:
        if json_output:
            print(json.dumps(report.to_dict(), indent=2))
            return

        scope = "all databases" if report.all_databases else report.database
        summary = report.summary
        print(
            f"Mongo activity window: {report.window_seconds:.1f}s scope={scope} "
            f"captured_at={report.captured_at.isoformat()}"
        )
        print(
            "Server summary (global Mongo counters): "
            f"reads/s={summary.reads_per_s:.2f} "
            f"writes/s={summary.writes_per_s:.2f} "
            f"commands/s={summary.commands_per_s:.2f} "
            f"docs_returned/s={summary.docs_returned_per_s:.2f} "
            f"collection_scans/s={summary.collection_scans_per_s:.2f} "
            f"scan/return={MongoCommand._fmt(summary.scanned_objects_per_returned_doc)} "
            f"avg_read_ms={MongoCommand._fmt(summary.avg_read_ms)} "
            f"avg_write_ms={MongoCommand._fmt(summary.avg_write_ms)}"
        )

        if not report.namespaces:
            print("No namespace activity detected in the sample window.")
            if (
                summary.reads_per_s > 0
                or summary.writes_per_s > 0
                or summary.commands_per_s > 0
            ):
                print(
                    "Use `fast-app mongo profile` for query-shape debugging when you need "
                    "authoritative namespace-level detail."
                )
            return

        visible_reads_per_s = sum(namespace.read_ops_per_s for namespace in report.namespaces)
        visible_writes_per_s = sum(namespace.write_ops_per_s for namespace in report.namespaces)
        visible_total_ms_per_s = sum(namespace.total_time_ms_per_s for namespace in report.namespaces)
        print(
            "Displayed namespaces: "
            f"reads/s={visible_reads_per_s:.2f} "
            f"writes/s={visible_writes_per_s:.2f} "
            f"total_ms/s={visible_total_ms_per_s:.2f}"
        )
        print("")
        print(
            MongoCommand._row(
                "namespace",
                "r/s",
                "w/s",
                "read_ms/s",
                "write_ms/s",
                "total_ms/s",
                widths=(34, 7, 7, 11, 12, 12),
            )
        )
        for namespace in report.namespaces:
            print(
                MongoCommand._row(
                    namespace.namespace,
                    f"{namespace.read_ops_per_s:.2f}",
                    f"{namespace.write_ops_per_s:.2f}",
                    f"{namespace.read_time_ms_per_s:.2f}",
                    f"{namespace.write_time_ms_per_s:.2f}",
                    f"{namespace.total_time_ms_per_s:.2f}",
                    widths=(34, 7, 7, 11, 12, 12),
                )
            )

    @staticmethod
    def _print_profile_report(report: MongoProfileReport, *, json_output: bool = False) -> None:
        if json_output:
            print(json.dumps(report.to_dict(), indent=2))
            return

        print(
            f"Mongo profiler window: {report.window_seconds:.1f}s db={report.database} "
            f"level={report.profiler_level} slowms={report.slowms} "
            f"sample_rate={report.sample_rate:.2f} matched={report.matched_profile_docs}/{report.total_profile_docs}"
        )
        filter_summary = MongoCommand._profile_filter_summary(report)
        if filter_summary:
            print(f"Filters: {filter_summary}")
        if report.truncated:
            print(
                "Profiler scan was capped before the full window was read: "
                f"max_profile_docs={report.max_profile_docs}"
            )

        if not report.findings:
            if report.only_suggestions:
                print("No remaining index candidates matched the selected window and filters.")
            else:
                print("No matching profiler findings captured in the selected window.")
            return

        print("")
        print(
            MongoCommand._row(
                "namespace",
                "op",
                "plan",
                "count",
                "totalMs",
                "avgMs",
                "scan/ret",
                "shape",
                widths=(28, 10, 16, 7, 8, 7, 9, 34),
            )
        )
        for finding in report.findings:
            plan = finding.plan_summary
            if finding.collection_scan and plan == "-":
                plan = "COLLSCAN"
            print(
                MongoCommand._row(
                    finding.namespace,
                    finding.operation,
                    plan,
                    str(finding.count),
                    str(finding.total_millis),
                    f"{finding.avg_millis:.1f}",
                    MongoCommand._fmt(finding.scan_ratio),
                    finding.shape,
                    widths=(28, 10, 16, 7, 8, 7, 9, 34),
                )
            )

        if not report.index_candidates:
            MongoCommand._print_profile_notes(report)
            return

        print("")
        print("Index candidates:")
        print(
            MongoCommand._row(
                "namespace",
                "keys",
                "conf",
                "ops",
                "totalMs",
                "reason",
                widths=(28, 40, 6, 6, 8, 34),
            )
        )
        for candidate in report.index_candidates:
            print(
                MongoCommand._row(
                    candidate.namespace,
                    MongoCommand._format_index_keys(candidate.keys),
                    candidate.confidence,
                    str(candidate.observed_queries),
                    str(candidate.total_millis),
                    candidate.reason,
                    widths=(28, 40, 6, 6, 8, 34),
                )
            )
        MongoCommand._print_profile_notes(report)

    @staticmethod
    def _fmt(value: float | None) -> str:
        if value is None:
            return "-"
        return f"{value:.2f}"

    @staticmethod
    def _format_index_keys(keys: list[MongoIndexKey]) -> str:
        if not keys:
            return "-"
        return ", ".join(f"{key.field}:{key.direction}" for key in keys)

    @staticmethod
    def _profile_filter_summary(report: MongoProfileReport) -> str:
        parts: list[str] = []
        if report.namespace_filters:
            parts.append("namespace=" + ",".join(report.namespace_filters))
        if report.exclude_namespace_filters:
            parts.append("exclude=" + ",".join(report.exclude_namespace_filters))
        if report.only_collection_scans:
            parts.append("only_collscan=true")
        if report.only_suggestions:
            parts.append("only_suggestions=true")
        if report.min_count > 1:
            parts.append(f"min_count={report.min_count}")
        if report.min_total_millis > 0:
            parts.append(f"min_total_ms={report.min_total_millis}")
        if report.min_docs_examined > 0:
            parts.append(f"min_docs_examined={report.min_docs_examined}")
        if report.min_scan_ratio > 0:
            parts.append(f"min_scan_ratio={report.min_scan_ratio:.2f}")
        return " ".join(parts)

    @staticmethod
    def _print_profile_notes(report: MongoProfileReport) -> None:
        noted_findings = [finding for finding in report.findings if finding.index_note]
        if not noted_findings:
            return
        print("")
        print("Existing index notes:")
        print(
            MongoCommand._row(
                "namespace",
                "shape",
                "covering_index",
                "note",
                widths=(28, 34, 30, 28),
            )
        )
        for finding in noted_findings:
            print(
                MongoCommand._row(
                    finding.namespace,
                    finding.shape,
                    MongoCommand._format_index_keys(finding.covering_index),
                    finding.index_note or "-",
                    widths=(28, 34, 30, 28),
                )
            )

    @staticmethod
    def _row(*values: str, widths: tuple[int, ...]) -> str:
        cells = []
        for value, width in zip(values, widths, strict=True):
            cell = value
            if len(cell) > width:
                cell = f"{cell[: max(width - 1, 0)]}..."
            cells.append(cell.ljust(width))
        return " ".join(cells)

    @staticmethod
    def _build_client() -> AsyncIOMotorClient:
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise ValueError("MONGO_URI is not set")

        return AsyncIOMotorClient(
            mongo_uri,
            tz_aware=True,
            serverSelectionTimeoutMS=3_000,
            connectTimeoutMS=3_000,
            appname="fast-app mongo",
        )

    @staticmethod
    def _default_database_name() -> str:
        if os.getenv("TEST_ENV"):
            return os.getenv("TEST_DB_NAME", "test_db")
        return os.getenv("DB_NAME", "db")


__all__ = ["MongoCommand"]
