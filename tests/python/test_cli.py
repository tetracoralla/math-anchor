from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def test_run_parse_failure_uses_the_structured_json_error_contract() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "math_anchor.cli", "run", "expression.evaluate", "not-json"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert completed.stderr == ""
    result = json.loads(completed.stdout)
    assert result["status"] == "error"
    assert result["error"]["code"] == "E_INPUT"


def test_run_rejects_nonfinite_json_numbers_without_emitting_invalid_json() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "math_anchor.cli",
            "run",
            "units.convert",
            '{"value":Infinity,"fromUnit":"meter","toUnit":"foot"}',
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert completed.stderr == ""
    assert "Infinity" not in completed.stdout
    result = json.loads(completed.stdout)
    assert result["status"] == "error"
    assert result["error"]["code"] == "E_INPUT"
