from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "script"))

from load_profiles import CODING_AGENT_CASES, EXPECTED_FAILURES, verify_case  # noqa: E402
import load_check  # noqa: E402
from math_anchor import sandbox  # noqa: E402


def test_coding_agent_load_profile_has_distinct_verified_operations() -> None:
    assert len(CODING_AGENT_CASES) >= 12
    assert len({case.id for case in CODING_AGENT_CASES}) == len(CODING_AGENT_CASES)
    assert len({case.operation for case in CODING_AGENT_CASES}) >= 10
    try:
        for case in CODING_AGENT_CASES:
            verify_case(case, sandbox.run_operation(case.operation, case.arguments))
    finally:
        sandbox._WORKER_POOL.shutdown()


def test_failure_profile_keeps_caller_errors_typed_and_nonretryable() -> None:
    try:
        for operation, arguments, expected_code in EXPECTED_FAILURES:
            result = sandbox.run_operation(operation, arguments)
            assert result["status"] == "error"
            assert result["error"]["code"] == expected_code
            assert result["error"]["retryable"] is False
    finally:
        sandbox._WORKER_POOL.shutdown()


def test_load_harness_does_not_retain_every_result_payload(monkeypatch) -> None:
    released = 0

    class TrackedResult(dict):
        def __del__(self) -> None:
            nonlocal released
            released += 1

    def expression_result(expression: str, *, timeout_ms: int = 10_000) -> dict:
        left = int(expression.split("+", 1)[0])
        return TrackedResult(status="ok", exact=str(left + 1))

    monkeypatch.setattr(load_check, "_call", expression_result)
    timings, operations = load_check._timed_calls(100, 1, "expression")

    assert len(timings) == 100
    assert operations == {"expression.evaluate": 100}
    assert released == 100
