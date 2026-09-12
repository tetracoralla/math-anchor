"""Reviewer regression candidates for Math Anchor PR #13.

Reviewed head: 5217679e6c84eb366e3bda487b3db42614c1e414.
These tests assert desired behavior, not the buggy behavior. They have been
syntax-checked, but HAVE NOT been run against a complete Math Anchor checkout
in the review environment. Run against the pinned PR before applying fixes;
record each observed failure. Do not turn failures into xfail or relax the
mathematical contract merely to make the file green.

From the repository root after its normal bootstrap:
    PYTHONPATH=src:. .venv/bin/python -m pytest -q \
        /absolute/path/test_pr13_review_regressions.py

No model calls, installs, publishing, or external network requests are made.
The two protocol tests call the existing no-model smoke. They deliberately
allow a future implementation to reject custom protocol overrides entirely.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from math_anchor.errors import CalculatorError
from research.polynomial_finite_sum_proposal.polynomials import parse_summand
from research.polynomial_finite_sum_proposal.runner import run_polynomial_finite_sum
from research.polynomial_finite_sum_proposal.coverage import (
    record_coverage,
    verify_typed_binding,
)
from research.method_packs.apply import apply_method_pack
from research.method_packs.loader import load_pack
from research.ai_for_math_eval.score import decide


SQUARE_TASK = {"summand": "k^2", "variable": "k", "lower": 1, "upper": 10}


@pytest.fixture(scope="module")
def square_result() -> dict[str, Any]:
    result = run_polynomial_finite_sum(**SQUARE_TASK, compare_baseline=False)
    assert result["status"] == "ok"
    assert result["value"]["exact"] == "385"
    return result


@pytest.mark.parametrize("source", ["k/k", "(k-1)/(k-1)", "0/k"])
def test_original_polynomial_language_is_checked_before_cancellation(source: str) -> None:
    # This vertical explicitly permits constant denominators only. It must
    # not promote a rational expression after its undefined points disappear.
    with pytest.raises(CalculatorError):
        parse_summand(source, "k")


def test_valid_constant_denominator_still_works() -> None:
    _source, terms, _expression = parse_summand("(2*k+1)/3", "k")
    assert terms  # Positive control: a fix must not ban rational coefficients.


def test_matched_task_and_result_still_bind(square_result: dict[str, Any]) -> None:
    assert verify_typed_binding(deepcopy(square_result), task=SQUARE_TASK)["ok"] is True


def test_result_for_squares_cannot_certify_cubes(square_result: dict[str, Any]) -> None:
    foreign_task = {**SQUARE_TASK, "summand": "k^3"}
    with pytest.raises(CalculatorError):
        record_coverage(foreign_task, deepcopy(square_result))


def test_result_bounds_cannot_silently_override_requested_bounds(square_result: dict[str, Any]) -> None:
    foreign_task = {**SQUARE_TASK, "upper": 20}
    with pytest.raises(CalculatorError):
        verify_typed_binding(deepcopy(square_result), task=foreign_task)


def test_identity_right_side_must_match_task_and_receipt(square_result: dict[str, Any]) -> None:
    changed = deepcopy(square_result)
    changed["identity"]["right"] = "k^3"
    with pytest.raises(CalculatorError):
        verify_typed_binding(changed, task=SQUARE_TASK)


def test_exact_text_cannot_disagree_with_rational_fields(square_result: dict[str, Any]) -> None:
    changed = deepcopy(square_result)
    changed["value"]["exact"] = "999999"
    # numerator/denominator are intentionally left unchanged at 385/1.
    with pytest.raises(CalculatorError):
        verify_typed_binding(changed, task=SQUARE_TASK)


def test_pack_cannot_publish_an_unobserved_checker_version() -> None:
    forged_version = "999.0.0-review-probe"
    pack = deepcopy(load_pack())
    pack["verification"]["checkerVersion"] = forged_version
    try:
        result = apply_method_pack(SQUARE_TASK, pack=pack, compare_baseline=False)
    except CalculatorError:
        return  # Rejection is a valid fix.
    # Alternatively derive the reported version from the actual checker.
    assert result["verification"]["checkerVersion"] != forged_version


def test_decision_does_not_invent_a_latency_observation() -> None:
    # Scoring cells deliberately carry no measured latency. The decision may
    # remain evidence_insufficient, but cannot say a slower path was observed.
    cells = [
        {
            "arm": arm,
            "task": task,
            "scoring": {
                "matchedPreRegisteredExpectation": True,
                "wrongAcceptance": False,
                "applicabilityMisjudgment": False,
                "countedAsSolved": task != "negative-harmonic",
                "coversOriginalTaskClaim": False,
                "formalKernelChecked": False,
                "baselineEmbedded": False,
            },
        }
        for arm in ("B0", "B1", "B2")
        for task in ("T1", "held-out-cubes", "negative-harmonic")
    ]
    decision = decide(cells, {"ran": False, "skipReason": "no latency measured"})
    assert decision.get("observedSlowerCheckedPath") is not True


def test_protocol_digest_tracks_the_protocol_actually_used() -> None:
    from research.ai_for_math_eval.protocol import load_protocol
    from research.ai_for_math_eval.smoke import run_smoke

    original = load_protocol()
    changed = deepcopy(original)
    for task in changed["tasks"]:
        if task["id"] == "T1":
            task["upper"] = 9
            task["expectedExact"] = "285"
    try:
        report_a = run_smoke(protocol=original)
        report_b = run_smoke(protocol=changed)
    except (CalculatorError, ValueError):
        return  # A pinned-only protocol API may explicitly refuse overrides.
    assert report_a["protocolDigest"] != report_b["protocolDigest"]
