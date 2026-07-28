"""Developer-facing retrieval health report."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from search.services.reindex_service import ReindexService
from search.services.retrieval_service import RetrievalService


class RetrievalHealthReport:
    """Summarize index health and optional probe/benchmark signals."""

    def __init__(
        self,
        reindex_service: ReindexService,
        retrieval_service: RetrievalService | None = None,
    ) -> None:
        self.reindex_service = reindex_service
        self.retrieval_service = retrieval_service

    def build(
        self,
        *,
        probe_query: str | None = None,
        benchmark_json: str | Path | None = None,
    ) -> dict[str, Any]:
        validation = self.reindex_service.validate_index()
        db_path = self.reindex_service.database.db_path
        index_size_bytes = (
            db_path.stat().st_size if db_path.exists() else 0
        )

        probe: dict[str, Any] | None = None

        if probe_query and self.retrieval_service is not None:
            started = time.perf_counter()
            retrieval = self.retrieval_service.retrieve(
                probe_query,
                include_trace=True,
            )
            probe = {
                "query": probe_query,
                "latency_ms": round(
                    (time.perf_counter() - started) * 1000.0,
                    3,
                ),
                "result_count": retrieval.get("result_count", 0),
                "confidence_level": retrieval.get("confidence_level"),
                "confidence_explanation": retrieval.get(
                    "confidence_explanation"
                )
                or [],
            }

        benchmark_summary: dict[str, Any] | None = None

        if benchmark_json is not None:
            path = Path(benchmark_json)
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
                benchmark_summary = payload.get("summary")

        return {
            "database_path": str(db_path),
            "index_size_bytes": index_size_bytes,
            "document_count": validation.get("document_count", 0),
            "fts_integrity": validation.get("fts_integrity") or {},
            "identifier_coverage": validation.get("identifier_coverage")
            or {},
            "missing_field_rates": validation.get("missing_field_rates")
            or {},
            "probe": probe,
            "benchmark_summary": benchmark_summary,
            "ok": bool(validation.get("ok")),
        }

    @classmethod
    def to_markdown(cls, report: dict[str, Any]) -> str:
        integrity = report.get("fts_integrity") or {}
        coverage = report.get("identifier_coverage") or {}
        missing = report.get("missing_field_rates") or {}
        probe = report.get("probe")
        benchmark = report.get("benchmark_summary")

        lines = [
            "# Retrieval Health Report",
            "",
            "## Index",
            f"- database: `{report.get('database_path', '')}`",
            f"- indexed drawings: {report.get('document_count', 0)}",
            f"- index size bytes: {report.get('index_size_bytes', 0)}",
            f"- FTS exists: {integrity.get('fts_exists')}",
            f"- FTS count: {integrity.get('fts_count')}",
            f"- counts match: {integrity.get('counts_match')}",
            f"- integrity ok: {integrity.get('ok')}",
            "",
            "## Identifier Coverage",
        ]

        for field_name, rate in coverage.items():
            lines.append(f"- {field_name}: {float(rate) * 100.0:.1f}%")

        lines.extend(["", "## Missing Metadata Rates"])

        for field_name, rate in sorted(missing.items()):
            lines.append(f"- {field_name}: {float(rate) * 100.0:.1f}%")

        if probe:
            lines.extend(
                [
                    "",
                    "## Probe Query",
                    f"- query: {probe.get('query')}",
                    f"- latency: {probe.get('latency_ms')} ms",
                    f"- result count: {probe.get('result_count')}",
                    f"- confidence: {probe.get('confidence_level')}",
                ]
            )

        if benchmark:
            lines.extend(
                [
                    "",
                    "## Benchmark Summary",
                    f"- Hit@1: {float(benchmark.get('hit_at_1', 0.0)) * 100:.1f}%",
                    f"- Hit@5: {float(benchmark.get('hit_at_5', 0.0)) * 100:.1f}%",
                    f"- MRR: {float(benchmark.get('mean_reciprocal_rank', 0.0)):.2f}",
                    (
                        "- mean retrieval latency: "
                        f"{float(benchmark.get('retrieval_latency_mean_ms', 0.0)):.1f} ms"
                    ),
                ]
            )

        lines.append("")
        return "\n".join(lines)
