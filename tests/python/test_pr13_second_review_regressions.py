"""Second-review regression candidates for Math Anchor PR #13.

Target: 89490a1c7665857550462c9079bfede429cc74ef.

These tests were derived from reading the pinned source. This review environment
syntax-checked this file, but did NOT run it against a full Math Anchor checkout.
They assert the intended contract, not acceptance of the identified defects.

Run from the real repository after its usual dependency setup:
    PYTHONPATH=src:. .venv/bin/python -m pytest -q \
        /absolute/path/test_pr13_second_review_regressions.py

Uses the real repository functions. No mocks, model calls, network access,
publishing, installation changes, or writes outside pytest temporary paths.
Custom protocol overrides may either be explicitly rejected or faithfully
executed; a generic experiment engine is not required to fix these tests.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest

from math_anchor.errors import CalculatorError
from research.polynomial_finite_sum_proposal.runner import run_polynomial_finite_sum
from research.polynomial_finite_sum_proposal.coverage import (
    record_coverage,
    verify_typed_binding,
)
from research.method_packs.apply import apply_method_pack
from research.method_packs.run import main as method_pack_main
from research.ai_for_math_eval.protocol import load_protocol
from research.ai_for_math_eval.smoke import run_smoke


SQUARE_TASK = {"summand": "k^2", "variable": "k", "lower": 1, "upper": 10}


@pytest.fixture(scope="module")
def square_result() -> dict[str, Any]:
    result = run_polynomial_finite_sum(**SQUARE_TASK, compare_baseline=False)
    assert result["status"] == "ok"
    assert result["value"]["exact"] == "385"
    return result


def _rewrite_candidate_keep_receipt(result: dict[str, Any]) -> dict[str, Any]:
    """Change a candidate coherently, while leaving its genuine old receipt intact."""
    changed = deepcopy(result)
    zero = {"exact": "0", "numerator": 0, "denominator": 1}
    changed["antidifference"] = "0"
    changed["identity"]["left"] = "(0) - (0)"
    changed["value"] = deepcopy(zero)
    changed["endpoints"] = {
        "gAtUpperPlusOne": deepcopy(zero),
        "gAtLower": deepcopy(zero),
    }
    # identity.right is still k^2. 0 - 0 = k^2 is false. No digest is recomputed.
    assert changed["identity"]["right"] == result["identity"]["right"]
    assert changed["obligationReceipt"] == result["obligationReceipt"]
    return changed


def test_current_positive_control_still_binds(square_result: dict[str, Any]) -> None:
    assert verify_typed_binding(deepcopy(square_result), task=SQUARE_TASK)["ok"] is True


def test_coherent_candidate_rewrite_cannot_reuse_old_checked_receipt(
    square_result: dict[str, Any],
) -> None:
    changed = _rewrite_candidate_keep_receipt(square_result)
    try:
        binding = verify_typed_binding(changed, task=SQUARE_TASK)
    except CalculatorError:
        return
    assert binding.get("ok") is not True, (
        "A stale receipt for the original G must not certify new G=0 for sum k^2."
    )


def test_coverage_cannot_establish_false_sum_from_old_receipt(
    square_result: dict[str, Any],
) -> None:
    changed = _rewrite_candidate_keep_receipt(square_result)
    try:
        coverage = record_coverage(SQUARE_TASK, changed)
    except CalculatorError:
        return
    assert coverage["claimCoverage"]["procedureEstablishedFiniteSumValue"] is not True
    assert coverage["typedBinding"]["status"] != "bound"


@pytest.mark.parametrize("include_receipt", [False, True])
def test_adding_a_real_receipt_does_not_destroy_valid_coverage(
    include_receipt: bool,
) -> None:
    result = apply_method_pack(
        deepcopy(SQUARE_TASK),
        compare_baseline=False,
        include_backend_receipt=include_receipt,
    )
    assert result["status"] == "ok"
    coverage = record_coverage(SQUARE_TASK, result)
    assert coverage["claimCoverage"]["procedureEstablishedFiniteSumValue"] is True
    assert coverage["typedBinding"]["status"] == "bound"
    assert coverage["typedBinding"]["recomputed"]["exact"] == "385"


@pytest.mark.parametrize("receipt_mode", ["inline", "separate"])
def test_cli_receipt_and_coverage_options_compose(
    receipt_mode: str, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    task_path = tmp_path / "task.json"
    task_path.write_text(json.dumps(SQUARE_TASK), encoding="utf-8")
    coverage_path = tmp_path / "coverage.json"
    receipt_path = tmp_path / "receipt.json"
    argv = [
        "apply", "--task", str(task_path), "--no-baseline",
        "--coverage-output", str(coverage_path),
    ]
    if receipt_mode == "inline":
        argv += ["--include-receipt"]
    else:
        argv += ["--receipt-output", str(receipt_path)]
    exit_code = method_pack_main(argv)
    captured = capsys.readouterr()
    assert exit_code == 0, captured.out + captured.err
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    assert coverage["claimCoverage"]["procedureEstablishedFiniteSumValue"] is True
    assert coverage["typedBinding"]["status"] == "bound"
    assert coverage["generatedObligations"], "Externalizing evidence must not erase it."
    if receipt_mode == "separate":
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert receipt["obligations"][0]["status"] == "checked"


def test_protocol_arm_override_is_rejected_or_actually_followed() -> None:
    protocol = deepcopy(load_protocol())
    protocol["arms"] = [arm for arm in protocol["arms"] if arm["id"] == "B0"]
    assert len(protocol["arms"]) == 1
    try:
        report = run_smoke(protocol=protocol)
    except (ValueError, CalculatorError):
        return  # Pinned-only smoke is a valid, simpler contract.
    actual_arms = {cell["arm"] for cell in report["cells"]}
    assert actual_arms == {"B0"}, (
        "The digest must describe the executed protocol, not an ignored arm plan."
    )


def test_protocol_trial_override_is_rejected_or_actually_followed() -> None:
    protocol = deepcopy(load_protocol())
    protocol["latency"]["trials"] = 3
    protocol["latency"]["labels"] = ["first", "repeat-1", "repeat-2"]
    try:
        report = run_smoke(protocol=protocol)
    except (ValueError, CalculatorError):
        return
    assert report["cells"]
    assert all(len(cell["trials"]) == 3 for cell in report["cells"]), (
        "Do not accept and hash a three-trial protocol while executing two trials."
    )
