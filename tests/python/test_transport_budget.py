from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import sys

import math_anchor.sandbox as sandbox
from math_anchor.sandbox import run_batch, run_operation
from math_anchor.transport_budget import TransportBudgetError, encode_json_line


ROOT = Path(__file__).resolve().parents[2]


def test_transport_budget_rejects_cumulative_nodes_and_depth() -> None:
    try:
        encode_json_line([1, 2, 3, 4], max_nodes=4)
    except TransportBudgetError as error:
        assert error.rule == "maxRequestNodes"
    else:  # pragma: no cover - assertion spelling keeps error details visible
        raise AssertionError("node budget was not enforced")

    nested: object = 0
    for _ in range(5):
        nested = [nested]
    try:
        encode_json_line(nested, max_depth=4)
    except TransportBudgetError as error:
        assert error.rule == "maxRequestDepth"
    else:  # pragma: no cover
        raise AssertionError("depth budget was not enforced")


def test_oversized_single_request_is_rejected_before_worker_acquisition(
    monkeypatch,
) -> None:
    def unexpected_acquire(*args, **kwargs):
        raise AssertionError("worker acquisition must happen after request preflight")

    monkeypatch.setattr(sandbox._WORKER_POOL, "acquire", unexpected_acquire)
    result = run_operation(
        "expression.evaluate",
        {"expression": "1" * (sandbox.MAX_REQUEST_BYTES + 1)},
    )

    assert result["status"] == "error"
    assert result["error"]["code"] == "E_LIMIT"
    assert result["error"]["phase"] == "input"
    assert result["error"]["details"]["rule"] == "maxRequestBytes"


def test_batch_transport_budget_rejects_non_json_before_scheduling() -> None:
    circular: list[object] = []
    circular.append(circular)
    result = run_batch(
        [{"operation": "expression.evaluate", "arguments": {"value": circular}}]
    )

    assert result["status"] == "error"
    assert result["error"]["code"] == "E_INPUT"
    assert result["error"]["phase"] == "input"


def test_nonfinite_numbers_are_rejected_before_worker_acquisition(monkeypatch) -> None:
    def unexpected_acquire(*args, **kwargs):
        raise AssertionError("worker acquisition must happen after request preflight")

    monkeypatch.setattr(sandbox._WORKER_POOL, "acquire", unexpected_acquire)
    for value in (math.nan, math.inf, -math.inf):
        result = run_operation(
            "units.convert",
            {"value": value, "fromUnit": "meter", "toUnit": "foot"},
        )
        assert result["status"] == "error"
        assert result["error"]["code"] == "E_INPUT"
        assert result["error"]["phase"] == "input"
        assert "finite" in result["error"]["message"]


def test_batch_rejects_nonfinite_numbers_before_scheduling() -> None:
    result = run_batch(
        [
            {
                "operation": "units.convert",
                "arguments": {
                    "value": math.inf,
                    "fromUnit": "meter",
                    "toUnit": "foot",
                },
            }
        ]
    )
    assert result["status"] == "error"
    assert result["error"]["code"] == "E_INPUT"
    assert result["error"]["phase"] == "input"
    assert "finite" in result["error"]["message"]


def test_batch_deadline_includes_transport_preflight(monkeypatch) -> None:
    timestamps = iter((10.0, 10.101))
    monkeypatch.setattr(sandbox.time, "monotonic", lambda: next(timestamps))

    result = run_batch(
        [{"operation": "expression.evaluate", "arguments": {"expression": "1"}}],
        timeout_ms=100,
    )

    assert result["status"] == "error"
    assert result["error"]["code"] == "E_TIMEOUT"
    assert result["error"]["phase"] == "input"


def test_single_request_worker_rejects_malformed_json_structurally() -> None:
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    completed = subprocess.run(
        [sys.executable, "-m", "math_anchor.worker"],
        input=b"not-json\n",
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
    )

    response = json.loads(completed.stdout.splitlines()[-1])
    assert response["ok"] is False
    assert response["error"]["code"] == "E_INPUT"
