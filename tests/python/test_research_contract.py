from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from math_anchor import __version__
from math_anchor.certificate_checker import (
    CertificateValidationError,
    verify_polynomial_identity_certificate,
)
from math_anchor.catalog import OPERATIONS
from math_anchor.errors import CalculatorError
from math_anchor.models import OperationSpec
from math_anchor.research_contract import _MODULE_BACKENDS, apply_research_contract
from math_anchor.runtime import execute_direct


ROOT = Path(__file__).resolve().parent.parent.parent


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def test_every_success_gets_the_compact_assurance_envelope() -> None:
    result = execute_direct("expression.evaluate", {"expression": "1/10 + 2/10"})

    assert result["assurance"] == "deterministic"
    assert result["claim"] == result["kind"] == "scalar"
    assert result["scope"] == "declared_operation_result"
    assert result["assumptions"] == []
    assert result["provenance"]["runtime"] == {"name": "math-anchor", "version": __version__}
    assert result["provenance"]["backends"][0]["name"] == "sympy"
    assert result["certificate"] is None
    assert result["checkedBy"] is None


def test_diagnostic_operation_exposes_its_narrow_scope() -> None:
    result = execute_direct(
        "numeric.integrate",
        {
            "expression": "x^2",
            "variable": "x",
            "lower": "0",
            "upper": "1",
            "featureScale": "1",
        },
    )

    assert result["assurance"] == "diagnostic"
    assert result["scope"] == "estimated_quadrature_interval_not_rigorous_enclosure"
    assert result["certificate"] is None


def test_unresolved_equivalence_probe_is_heuristic_not_proof() -> None:
    result = execute_direct(
        "expression.equivalent",
        {
            "left": "x*(x-1)*(x+1)*(2*x-1)*(2*x+1)*(x-2)*(x+2)*(x-3)*(x-pi)*(x-e)",
            "right": "0",
            "variables": ["x"],
        },
    )

    assert result["equivalence"] == "unknown"
    assert result["proven"] is False
    assert result["assurance"] == "heuristic"
    assert result["certificate"] is None


def test_operation_spec_rejects_an_unknown_assurance_level() -> None:
    with pytest.raises(ValueError, match="unsupported assurance level"):
        OperationSpec(
            id="test.invalid",
            category="test",
            summary="invalid",
            description="invalid",
            input_schema={"type": "object"},
            examples=(),
            handler=lambda arguments: {},
            assurance="proven",
        )


def test_certified_profile_cannot_return_without_a_certificate() -> None:
    spec = OperationSpec(
        id="test.certified",
        category="test",
        summary="test",
        description="test",
        input_schema={"type": "object"},
        examples=(),
        handler=lambda arguments: {},
        assurance="certified",
    )
    with pytest.raises(ValueError, match="returned no certificate"):
        apply_research_contract(
            spec,
            {
                "status": "ok",
                "operation": spec.id,
                "kind": "test",
                "warnings": [],
            },
        )


def test_runtime_owned_assurance_and_provenance_cannot_be_self_promoted() -> None:
    spec = OperationSpec(
        id="test.runtime_owned",
        category="test",
        summary="test",
        description="test",
        input_schema={"type": "object"},
        examples=(),
        handler=lambda arguments: {},
        assurance="diagnostic",
        assurance_scope="bounded_diagnostic",
        backends=("python",),
    )
    result = apply_research_contract(
        spec,
        {
            "status": "ok",
            "operation": spec.id,
            "kind": "test",
            "warnings": [],
            "assurance": "kernel_checked",
            "scope": "unbounded_proof",
            "provenance": {"runtime": {"name": "invented", "version": "1"}, "backends": []},
        },
    )

    assert result["assurance"] == "diagnostic"
    assert result["scope"] == "bounded_diagnostic"
    assert result["provenance"]["runtime"] == {"name": "math-anchor", "version": __version__}


@pytest.mark.parametrize(
    ("left", "right", "identity"),
    [
        ("(x + y)^2", "x^2 + 2*x*y + y^2", True),
        ("x^2", "x", False),
    ],
)
def test_polynomial_identity_certificate_passes_the_independent_checker(
    left: str, right: str, identity: bool
) -> None:
    result = execute_direct(
        "certificate.polynomial_identity",
        {"left": left, "right": right, "variables": ["x", "y"]},
    )
    checked = verify_polynomial_identity_certificate(result["certificate"])

    assert result["assurance"] == "certified"
    assert result["scope"] == "polynomial_identity_over_rationals"
    assert result["identity"] is identity
    assert result["checkedBy"] is None
    assert checked["valid"] is True
    assert checked["identity"] is identity
    assert checked["certificateDigest"] == result["certificate"]["certificateDigest"]


def test_checker_recomputes_coefficients_instead_of_trusting_valid_digests() -> None:
    result = execute_direct(
        "certificate.polynomial_identity",
        {"left": "x^2", "right": "x", "variables": ["x"]},
    )
    tampered = deepcopy(result["certificate"])
    tampered["normalizedDifference"][0]["coefficient"] = "99"
    digest_payload = dict(tampered)
    digest_payload.pop("certificateDigest")
    tampered["certificateDigest"] = _digest(digest_payload)

    with pytest.raises(CertificateValidationError, match="coefficients do not match"):
        verify_polynomial_identity_certificate(tampered)


def test_certificate_operation_rejects_nonpolynomial_and_unsafe_input() -> None:
    with pytest.raises(CalculatorError) as nonpolynomial:
        execute_direct(
            "certificate.polynomial_identity",
            {"left": "sin(x)", "right": "0", "variables": ["x"]},
        )
    assert nonpolynomial.value.code == "E_DOMAIN"

    with pytest.raises(CalculatorError) as expensive_nonpolynomial:
        execute_direct(
            "certificate.polynomial_identity",
            {"left": "factorial(5000)", "right": "0", "variables": ["x"]},
            timeout_ms=100,
        )
    assert expensive_nonpolynomial.value.code == "E_DOMAIN"

    with pytest.raises(CalculatorError) as unsafe:
        execute_direct(
            "certificate.polynomial_identity",
            {"left": "x.__class__", "right": "0", "variables": ["x"]},
        )
    assert unsafe.value.code == "E_AST_BLOCK"


def test_certificate_operation_rejects_inexact_literals_and_oversized_expansion() -> None:
    with pytest.raises(CalculatorError) as inexact:
        execute_direct(
            "certificate.polynomial_identity",
            {"left": "0.1*x", "right": "x/10", "variables": ["x"]},
        )
    assert inexact.value.code == "E_DOMAIN"

    with pytest.raises(CalculatorError) as high_degree:
        execute_direct(
            "certificate.polynomial_identity",
            {"left": "(x + 1)^10000", "right": "0", "variables": ["x"]},
            timeout_ms=500,
        )
    assert high_degree.value.code == "E_LIMIT"

    with pytest.raises(CalculatorError) as too_many_terms:
        execute_direct(
            "certificate.polynomial_identity",
            {
                "left": "(a + b + c + d + f + g + h + j)^8",
                "right": "0",
                "variables": ["a", "b", "c", "d", "f", "g", "h", "j"],
            },
            timeout_ms=500,
        )
    assert too_many_terms.value.code == "E_LIMIT"


def test_certificate_operation_rejects_zero_denominator_and_negative_exponent() -> None:
    with pytest.raises(CalculatorError) as zero_denominator:
        execute_direct(
            "certificate.polynomial_identity",
            {"left": "x/0", "right": "0", "variables": ["x"]},
        )
    assert zero_denominator.value.code == "E_DOMAIN"
    assert "division by zero" in zero_denominator.value.message

    with pytest.raises(CalculatorError) as negative_exponent:
        execute_direct(
            "certificate.polynomial_identity",
            {"left": "x^-1", "right": "0", "variables": ["x"]},
        )
    assert negative_exponent.value.code == "E_DOMAIN"
    assert "nonnegative" in negative_exponent.value.message


def test_every_operation_declares_or_registers_backend_provenance() -> None:
    for spec in OPERATIONS.values():
        module_name = spec.handler.__module__.rsplit(".", 1)[-1]
        assert spec.backends or module_name in _MODULE_BACKENDS, (
            f"{spec.id} would silently fall back to python backend provenance"
        )


def test_independent_checker_does_not_import_the_generator_or_sympy() -> None:
    source = (ROOT / "src" / "math_anchor" / "certificate_checker.py").read_text(encoding="utf-8")
    assert "math_anchor.operations" not in source
    assert "from .operations" not in source
    assert "import sympy" not in source


def test_cli_verifies_a_complete_result_from_stdin() -> None:
    result = execute_direct(
        "certificate.polynomial_identity",
        {"left": "(x + 1)^2", "right": "x^2 + 2*x + 1", "variables": ["x"]},
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    completed = subprocess.run(
        [sys.executable, "-m", "math_anchor.cli", "verify-certificate", "-"],
        input=json.dumps(result),
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=environment,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    checked = json.loads(completed.stdout)
    assert checked["status"] == "ok"
    assert checked["valid"] is True
    assert checked["kind"] == "certificate_check"


def test_cli_reports_missing_or_null_certificate_as_structured_input_error(
    tmp_path: Path,
) -> None:
    missing = subprocess.run(
        [sys.executable, "-m", "math_anchor.cli", "verify-certificate", str(tmp_path / "missing.json")],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        check=False,
    )
    assert missing.returncode == 2
    assert json.loads(missing.stdout)["error"]["code"] == "E_INPUT"

    null_result = subprocess.run(
        [sys.executable, "-m", "math_anchor.cli", "verify-certificate", "-"],
        input=json.dumps({"status": "ok", "certificate": None}),
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        check=False,
    )
    assert null_result.returncode == 2
    assert json.loads(null_result.stdout)["error"]["code"] == "E_INPUT"
