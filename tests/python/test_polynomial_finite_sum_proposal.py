"""Independent regressions for the A0/A1 polynomial finite-sum proposal.

This file is the domain regression for a research proposal. It is not evidence
that the flow is a supported Math Anchor product module.
"""

from __future__ import annotations

from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.polynomial_finite_sum_proposal.baseline import sympy_finite_sum
from research.polynomial_finite_sum_proposal.polynomials import DomainError
from research.polynomial_finite_sum_proposal.runner import run_polynomial_finite_sum
from research.polynomial_finite_sum_proposal.telescoping import (
    TELESCOPING_RULE_ORIGIN,
    TelescopingRuleError,
    apply_finite_telescoping_sum,
)


RUNNER = ROOT / "research" / "polynomial_finite_sum_proposal" / "run.py"
EXAMPLES = ROOT / "research" / "polynomial_finite_sum_proposal" / "examples"


def _cli(*args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def test_telescoping_rule_requires_a_checked_identity() -> None:
    with pytest.raises(TelescopingRuleError, match="checked difference identity"):
        apply_finite_telescoping_sum(
            difference_identity_checked=False,
            lower=1,
            upper=3,
            g_at_upper_plus_one=Fraction(10),
            g_at_lower=Fraction(1),
        )


def test_telescoping_rule_empty_sum_is_zero() -> None:
    value = apply_finite_telescoping_sum(
        difference_identity_checked=True,
        lower=5,
        upper=4,
        g_at_upper_plus_one=Fraction(11, 2),
        g_at_lower=Fraction(11, 2),
    )
    assert value == 0


def test_telescoping_rule_subtracts_checked_endpoints() -> None:
    value = apply_finite_telescoping_sum(
        difference_identity_checked=True,
        lower=1,
        upper=10,
        g_at_upper_plus_one=Fraction(385),
        g_at_lower=Fraction(0),
    )
    assert value == 385


def test_telescoping_rule_rejects_reversed_bounds_and_booleans() -> None:
    with pytest.raises(TelescopingRuleError, match="reversed bounds"):
        apply_finite_telescoping_sum(
            difference_identity_checked=True,
            lower=5,
            upper=1,
            g_at_upper_plus_one=Fraction(1),
            g_at_lower=Fraction(2),
        )
    with pytest.raises(TelescopingRuleError, match="integer"):
        apply_finite_telescoping_sum(
            difference_identity_checked=True,
            lower=True,
            upper=3,
            g_at_upper_plus_one=Fraction(1),
            g_at_lower=Fraction(0),
        )


def test_sum_of_squares_matches_closed_form_and_baseline() -> None:
    result = run_polynomial_finite_sum(summand="k^2", lower=1, upper=10)
    assert result["status"] == "ok"
    assert result["value"]["exact"] == "385"
    assert result["identity"]["status"] == "checked"
    assert result["identity"]["assuranceLevel"] == "exact_symbolic"
    assert result["formalKernelChecked"] is False
    assert result["combinationRule"]["origin"] == TELESCOPING_RULE_ORIGIN
    assert result["combinationRule"]["agentExtracted"] is False
    assert result["baseline"]["agrees"] is True
    assert "formal_kernel_checked" not in json.dumps(result)


def test_empty_sum_and_single_term() -> None:
    empty = run_polynomial_finite_sum(summand="k^2", lower=5, upper=4)
    assert empty["status"] == "ok"
    assert empty["value"]["exact"] == "0"
    single = run_polynomial_finite_sum(summand="2*k + 1", lower=7, upper=7)
    assert single["value"]["exact"] == "15"


def test_rational_coefficient_polynomial() -> None:
    result = run_polynomial_finite_sum(summand="(2*k + 1)/3", lower=0, upper=2)
    assert result["status"] == "ok"
    assert result["value"]["exact"] == "3"
    assert result["baseline"]["agrees"] is True


def test_wrong_antidifference_is_falsified() -> None:
    result = run_polynomial_finite_sum(
        summand="k^2",
        lower=1,
        upper=10,
        antidifference="k^3 / 3",
        compare_baseline=False,
    )
    assert result["status"] == "falsified"
    assert result["identity"]["status"] == "falsified"
    assert result["formalKernelChecked"] is False
    assert "value" not in result


def test_reversed_bounds_are_unsupported() -> None:
    with pytest.raises(DomainError, match="reversed bounds"):
        run_polynomial_finite_sum(summand="k^2", lower=5, upper=1)


def test_non_polynomial_and_nonconstant_denominator_are_unsupported() -> None:
    with pytest.raises(DomainError, match="polynomial"):
        run_polynomial_finite_sum(summand="sin(k)", lower=1, upper=3)
    with pytest.raises(DomainError, match="constant denominators"):
        run_polynomial_finite_sum(summand="1/k", lower=1, upper=3)


def test_sympy_baseline_accepts_karr_reversed_bounds_that_the_proposal_rejects() -> None:
    baseline = sympy_finite_sum(summand="k^2", lower=5, upper=1)
    assert baseline["status"] == "ok"
    assert baseline["value"]["exact"] == "-29"
    with pytest.raises(DomainError, match="reversed bounds"):
        run_polynomial_finite_sum(summand="k^2", lower=5, upper=1)


def test_cli_end_to_end_example_and_negative_paths(tmp_path: Path) -> None:
    output = tmp_path / "sum.json"
    receipt = tmp_path / "receipt.json"
    completed = _cli(
        "--task",
        str(EXAMPLES / "sum-k-squared-1-to-10.json"),
        "--output",
        str(output),
        "--receipt-output",
        str(receipt),
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    result = json.loads(completed.stdout)
    assert result["value"]["exact"] == "385"
    assert result["formalKernelChecked"] is False
    assert json.loads(output.read_text())["value"]["exact"] == "385"
    stored_receipt = json.loads(receipt.read_text())
    assert stored_receipt["obligations"][0]["status"] == "checked"
    assert stored_receipt["obligations"][0]["assuranceLevel"] == "exact_symbolic"

    falsified = _cli("--task", str(EXAMPLES / "wrong-antidifference.json"))
    assert falsified.returncode == 1
    payload = json.loads(falsified.stdout)
    assert payload["status"] == "falsified"

    reversed_bounds = _cli("--summand", "k^2", "--lower", "5", "--upper", "1")
    assert reversed_bounds.returncode == 2
    assert json.loads(reversed_bounds.stdout)["error"]["code"] == "E_DOMAIN"

    unsupported = _cli("--summand", "1/k", "--lower", "1", "--upper", "3")
    assert unsupported.returncode == 2
    assert json.loads(unsupported.stdout)["error"]["code"] == "E_UNSUPPORTED"

    baseline_only = _cli("--baseline-only", "--summand", "k^2", "--lower", "1", "--upper", "10")
    assert baseline_only.returncode == 0
    assert json.loads(baseline_only.stdout)["kind"] == "sympy_summation_baseline"
    assert json.loads(baseline_only.stdout)["value"]["exact"] == "385"
