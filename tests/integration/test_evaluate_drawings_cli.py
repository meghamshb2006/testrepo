from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from search.database import SearchDatabase
from search.models.search_document import SearchDocument
from search.repositories.search_repository import SearchRepository


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write_mini_dataset(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "name": "cli-mini",
                "version": "1.0",
                "cases": [
                    {
                        "case_id": "exact-drawing-number",
                        "question": "Find drawing DR-1001",
                        "expected_drawing_ids": ["drawing-001"],
                        "expected_drawing_numbers": ["DR-1001"],
                        "answerable": True,
                    },
                    {
                        "case_id": "no-match-zz9999",
                        "question": "What is the titanium alloy for ZZ-9999?",
                        "answerable": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def _seed_database(path: Path) -> None:
    database = SearchDatabase(str(path))
    database.initialize()
    repository = SearchRepository(database)
    now = datetime.now(timezone.utc)
    repository.upsert(
        SearchDocument(
            drawing_id="drawing-001",
            filename="aluminium_mounting_bracket.pdf",
            drawing_number="DR-1001",
            revision="C",
            title="Aluminium Mounting Bracket",
            material="Aluminium 6061-T6",
            part_numbers="BR-1001",
            searchable_text=(
                "DR-1001 aluminium mounting bracket 6061-T6 BR-1001"
            ),
            created_at=now,
            updated_at=now,
        )
    )
    database.close()


def test_cli_retrieval_only_no_api_env(tmp_path: Path) -> None:
    project_root = _project_root()
    dataset_path = tmp_path / "benchmark.json"
    database_path = tmp_path / "search.db"
    json_out = tmp_path / "out.evaluation.json"
    md_out = tmp_path / "out.evaluation.md"

    _write_mini_dataset(dataset_path)
    _seed_database(database_path)

    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)
    env.pop("OPENAI_MODEL", None)
    env.pop("OPENAI_ANSWER_MODEL", None)

    result = subprocess.run(
        [
            sys.executable,
            str(project_root / "evaluate_drawings.py"),
            "--dataset",
            str(dataset_path),
            "--database",
            str(database_path),
            "--output-json",
            str(json_out),
            "--output-markdown",
            str(md_out),
        ],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Hit@1:" in result.stdout
    assert json_out.exists()
    assert md_out.exists()
    assert "SYSTEM INSTRUCTIONS" not in md_out.read_text(encoding="utf-8")


def test_cli_threshold_failure_returns_nonzero(tmp_path: Path) -> None:
    project_root = _project_root()
    dataset_path = tmp_path / "benchmark.json"
    database_path = tmp_path / "empty.db"

    _write_mini_dataset(dataset_path)
    database = SearchDatabase(str(database_path))
    database.initialize()
    database.close()

    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)

    result = subprocess.run(
        [
            sys.executable,
            str(project_root / "evaluate_drawings.py"),
            "--dataset",
            str(dataset_path),
            "--database",
            str(database_path),
            "--fail-below-hit-at-1",
            "0.9",
            "--quiet",
        ],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "threshold" in result.stderr.lower()
    assert "Traceback" not in result.stderr


def test_cli_invalid_dataset_returns_nonzero(tmp_path: Path) -> None:
    project_root = _project_root()
    missing = tmp_path / "missing.json"
    database_path = tmp_path / "empty.db"
    database = SearchDatabase(str(database_path))
    database.initialize()
    database.close()

    result = subprocess.run(
        [
            sys.executable,
            str(project_root / "evaluate_drawings.py"),
            "--dataset",
            str(missing),
            "--database",
            str(database_path),
            "--quiet",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
