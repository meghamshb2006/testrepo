"""Structured observability logging for retrieval requests."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


class RetrievalLogger:
    """Optional structured logger for retrieval observability."""

    def __init__(
        self,
        enabled: bool = False,
        level: str = "INFO",
        logger: logging.Logger | None = None,
    ) -> None:
        self.enabled = enabled
        self.logger = logger or logging.getLogger("search.retrieval")
        self._level = getattr(logging, level.upper(), logging.INFO)

    def log_retrieval(
        self,
        *,
        query: str,
        normalized_query: str,
        identifiers: list[dict[str, Any]],
        result_count: int,
        confidence_level: str,
        confidence_score: float,
        latency_ms: float,
        drawing_ids: list[str] | None = None,
        confidence_explanation: list[str] | None = None,
        error: str | None = None,
    ) -> None:
        if not self.enabled:
            return

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "retrieval",
            "query": query,
            "normalized_query": normalized_query,
            "identifier_count": len(identifiers),
            "detected_identifiers": [
                item.get("value") for item in identifiers
            ],
            "result_count": result_count,
            "confidence_level": confidence_level,
            "confidence_score": confidence_score,
            "latency_ms": round(latency_ms, 3),
            "error": error,
        }

        self.logger.log(self._level, json.dumps(payload, default=str))

        if drawing_ids is not None or confidence_explanation:
            debug_payload = {
                "event": "retrieval_debug",
                "drawing_ids": drawing_ids or [],
                "confidence_explanation": confidence_explanation or [],
            }
            self.logger.debug(json.dumps(debug_payload, default=str))
