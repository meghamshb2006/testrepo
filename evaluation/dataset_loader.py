from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from evaluation.schemas import BenchmarkDataset


class BenchmarkDatasetLoader:
    """Loads and validates JSON benchmark datasets."""

    @classmethod
    def load(cls, path: str | Path) -> BenchmarkDataset:
        resolved = Path(path).expanduser().resolve()

        if not resolved.exists():
            raise ValueError(f"Benchmark dataset was not found: {resolved}")

        if not resolved.is_file():
            raise ValueError(f"Benchmark dataset path is not a file: {resolved}")

        try:
            raw_text = resolved.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(
                f"Could not read benchmark dataset: {resolved}"
            ) from exc

        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Malformed JSON in benchmark dataset: {resolved}: {exc}"
            ) from exc

        try:
            return BenchmarkDataset.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(
                f"Invalid benchmark dataset schema in {resolved}: {exc}"
            ) from exc
