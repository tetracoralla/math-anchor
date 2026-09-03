from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from math_anchor import cli
from math_anchor.errors import CalculatorError
from math_anchor.transport_budget import MAX_BATCH_REQUEST_BYTES


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


class _BoundedBatchInput:
    def __init__(self, payload: bytes) -> None:
        self.buffer = self
        self.payload = payload
        self.read_sizes: list[int] = []

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        if size < 0:
            raise AssertionError("batch stdin must never be read without a byte bound")
        return self.payload[:size]


def test_batch_stdin_reads_only_one_byte_beyond_the_hard_transport_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = _BoundedBatchInput(b"[]")
    monkeypatch.setattr(cli.sys, "stdin", stream)

    assert cli._batch_items("-") == []
    assert stream.read_sizes == [MAX_BATCH_REQUEST_BYTES + 1]


def test_batch_stdin_rejects_oversize_before_json_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "MAX_BATCH_REQUEST_BYTES", 8)
    stream = _BoundedBatchInput(b"[12345678]")
    monkeypatch.setattr(cli.sys, "stdin", stream)

    with pytest.raises(CalculatorError) as caught:
        cli._batch_items("-")

    assert caught.value.code == "E_LIMIT"
    assert stream.read_sizes == [9]
