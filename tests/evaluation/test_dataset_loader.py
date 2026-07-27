from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.dataset_loader import BenchmarkDatasetLoader


def test_valid_json_loaded(tmp_path: Path) -> None:
    path = tmp_path / "benchmark.json"
    path.write_text(
        json.dumps(
            {
                "name": "demo",
                "version": "1.0",
                "cases": [
                    {
                        "case_id": "case-1",
                        "question": "What material is used?",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    dataset = BenchmarkDatasetLoader.load(path)

    assert dataset.name == "demo"
    assert dataset.cases[0].case_id == "case-1"


def test_missing_file_rejected(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"

    with pytest.raises(ValueError, match="was not found"):
        BenchmarkDatasetLoader.load(missing)


def test_malformed_json_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="Malformed JSON"):
        BenchmarkDatasetLoader.load(path)


def test_schema_validation_errors_exposed(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(
        json.dumps(
            {
                "name": "demo",
                "version": "1.0",
                "cases": [
                    {"case_id": " ", "question": "What material?"}
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid benchmark dataset schema"):
        BenchmarkDatasetLoader.load(path)
