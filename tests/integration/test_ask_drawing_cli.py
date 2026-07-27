from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_cli_no_evidence_does_not_require_api_env(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    database_path = tmp_path / "empty_search.db"

    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)
    env.pop("OPENAI_MODEL", None)
    env.pop("OPENAI_ANSWER_MODEL", None)

    result = subprocess.run(
        [
            sys.executable,
            str(project_root / "ask_drawing.py"),
            "What is the titanium alloy specification for part ZZ-9999?",
            "--database",
            str(database_path),
        ],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Answer:" in result.stdout
    assert "does not contain enough information" in result.stdout
    assert "Sources:" in result.stdout
    assert "None" in result.stdout
