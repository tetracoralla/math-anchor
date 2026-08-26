from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "script"))

from load_profiles import CODING_AGENT_CASES, EXPECTED_FAILURES, verify_case  # noqa: E402
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
