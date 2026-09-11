"""A3 claim→obligation coverage and mutation tests for the polynomial finite-sum workflow.

Research proposal tests. Combination-rule unit tests remain in
test_polynomial_finite_sum_proposal.py; hash binding here does not apply
telescoping.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.method_packs.apply import PackApplicationError, apply_method_pack
from research.method_packs.format import PACK_VERSION
from research.method_packs.loader import load_pack
from research.polynomial_finite_sum_proposal.coverage import (
    COVERAGE_KIND,
    DIFFERENCE_IDENTITY_OBLIGATION_ID,
    CoverageIntegrityError,
    certificate_binds_claim,
    interpret_outcome,
    load_frozen_workflow_coverage,
    project_surface_feedback,
    record_coverage,
    static_workflow_coverage,
    verify_coverage_honesty,
    verify_typed_binding,
)
from research.polynomial_finite_sum_proposal.mutations import (
    mutation_hash_binding_is_not_combination,
    run_mutation_catalog,
)
from research.polynomial_finite_sum_proposal.polynomials import DomainError
from research.polynomial_finite_sum_proposal.runner import run_polynomial_finite_sum
from research.polynomial_finite_sum_proposal.telescoping import TELESCOPING_RULE_ORIGIN


A1_RUNNER = ROOT / "research" / "polynomial_finite_sum_proposal" / "run.py"
A2_RUNNER = ROOT / "research" / "method_packs" / "run.py"
A1_EXAMPLE = (
    ROOT
    / "research"
    / "polynomial_finite_sum_proposal"
    / "examples"
    / "sum-k-squared-1-to-10.json"
)
CUBES_EXAMPLE = ROOT / "research" / "method_packs" / "examples" / "sum-k-cubed-1-to-20.json"
HOCKEY = ROOT / "research" / "method_packs" / "examples" / "hockey-stick-c-k-2-rewritten.json"
A1_TESTS = ROOT / "tests" / "python" / "test_polynomial_finite_sum_proposal.py"


def _cli(runner: Path, *args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(runner), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def test_frozen_workflow_coverage_matches_module() -> None:
    frozen = load_frozen_workflow_coverage()
    assert frozen == static_workflow_coverage()
    assert frozen["kind"] == COVERAGE_KIND
    assert frozen["taskToObligation"]["generatedObligationIds"] == [DIFFERENCE_IDENTITY_OBLIGATION_ID]
    assert frozen["taskToObligation"]["naturalLanguageToClaim"] == "uncovered"
    assert frozen["bounds"]["coveredByDifferenceIdentityObligation"] is False
    assert frozen["evidenceScope"]["obligationSuccessIsNotClaimCoverage"] is True
    assert frozen["evidenceScope"]["formalKernelChecked"] is False
    assert frozen["typedBindingPattern"]["formula"] == "G(upper + 1) - G(lower)"
    assert frozen["typedBindingPattern"]["notAGeneralDataflowLanguage"] is True
    by_id = {step["id"]: step for step in frozen["steps"]}
    assert by_id["nl-to-structured-claim"]["coverage"] == "uncovered"
    assert by_id["difference-identity"]["obligationId"] == DIFFERENCE_IDENTITY_OBLIGATION_ID
    assert by_id["telescoping-combination"]["coverage"] == "hand-provided-infrastructure"
    assert by_id["telescoping-combination"]["agentExtracted"] is False
    assert by_id["binomial-rewrite"]["coverage"] == "uncovered-conditional-premise"
    assert by_id["whole-finite-sum-kernel"]["formalKernelChecked"] is False


def test_t1_coverage_maps_claim_to_identity_obligation_only() -> None:
    task = json.loads(A1_EXAMPLE.read_text(encoding="utf-8"))
    result = run_polynomial_finite_sum(summand="k^2", lower=1, upper=10)
    coverage = record_coverage(task, result)
    assert coverage["kind"] == COVERAGE_KIND
    assert coverage["taskClaim"]["rendered"] == "sum_{k=1}^{10} (k^2)"
    assert coverage["generatedObligations"][0]["id"] == DIFFERENCE_IDENTITY_OBLIGATION_ID
    assert coverage["generatedObligations"][0]["id"] == result["obligationReceipt"]["obligations"][0]["id"]
    assert coverage["generatedObligations"][0]["status"] == "checked"
    assert coverage["claimCoverage"]["allSubmittedObligationsChecked"] is True
    assert coverage["claimCoverage"]["coversOriginalTaskClaim"] is False
    assert coverage["claimCoverage"]["procedureEstablishedFiniteSumValue"] is True
    assert coverage["honesty"]["obligationSuccessIsNotClaimCoverage"] is True
    assert coverage["honesty"]["formalKernelChecked"] is False
    assert coverage["typedBinding"]["status"] == "bound"
    assert coverage["typedBinding"]["formula"] == "G(upper + 1) - G(lower)"
    assert coverage["typedBinding"]["recomputed"]["exact"] == "385"
    assert coverage["typedBinding"]["producedBy"]["origin"] == TELESCOPING_RULE_ORIGIN
    assert coverage["typedBinding"]["hashBinding"]["doesNotBind"]
    assert "authorship" in coverage["typedBinding"]["hashBinding"]["doesNotBind"]
    assert coverage["assumptions"]["interpretation"] == "bound_not_evaluated"
    assert coverage["bounds"]["coveredByDifferenceIdentityObligation"] is False
    by_id = {step["id"]: step for step in coverage["steps"]}
    assert by_id["nl-to-structured-claim"]["coverage"] == "uncovered"
    assert by_id["difference-identity"]["executed"] is True
    assert by_id["telescoping-combination"]["executed"] is True
    assert by_id["telescoping-combination"]["agentExtracted"] is False
    assert by_id["binomial-rewrite"]["status"] == "not_applicable"
    assert by_id["whole-finite-sum-kernel"]["formalKernelChecked"] is False
    assert result["formalKernelChecked"] is False
    verify_typed_binding(result, task=task)
    verify_coverage_honesty(coverage, result=result)


def test_method_pack_cubes_binds_value_into_downstream() -> None:
    task = json.loads(CUBES_EXAMPLE.read_text(encoding="utf-8"))
    result = apply_method_pack(task)
    coverage = record_coverage(task, result, pack=load_pack(), source="method-pack-apply")
    assert result["value"]["exact"] == "44100"
    assert coverage["generatedObligations"][0]["id"] == DIFFERENCE_IDENTITY_OBLIGATION_ID
    assert coverage["claimCoverage"]["coversOriginalTaskClaim"] is False
    assert coverage["claimCoverage"]["procedureEstablishedFiniteSumValue"] is True
    assert coverage["typedBinding"]["status"] == "bound"
    paths = {item["path"] for item in coverage["typedBinding"]["outputs"]}
    assert "value" in paths
    assert "downstream.value" in paths
    assert any(path.endswith("valueEnteredLaterSteps") for path in paths)
    assert coverage["typedBinding"]["recomputed"]["exact"] == "44100"
    assert coverage["methodPack"]["version"] == PACK_VERSION
    assert coverage["evidenceScope"]["formalKernelChecked"] is False
    verify_typed_binding(result, task=task)


def test_hockey_stick_binomial_rewrite_stays_uncovered() -> None:
    task = json.loads(HOCKEY.read_text(encoding="utf-8"))
    result = apply_method_pack(task)
    coverage = record_coverage(task, result, pack=load_pack())
    assert result["status"] == "ok"
    assert coverage["claimCoverage"]["coversOriginalTaskClaim"] is False
    binomial = next(step for step in coverage["steps"] if step["id"] == "binomial-rewrite")
    assert binomial["coverage"] == "uncovered-conditional-premise"
    assert binomial["executed"] is False
    assert binomial["presentAsConditionalPremise"] is True
    assert binomial["verifiedByPack"] is False
    assert result["conditionalPremises"][0]["status"] == "conditional"


def test_feedback_surfaces_reuse_existing_modes() -> None:
    result = run_polynomial_finite_sum(summand="k^2", lower=1, upper=10)
    feedback = project_surface_feedback(result)
    assert feedback["identityCheckInsideRunner"] == "full"
    assert feedback["compute"]["value"]["exact"] == "385"
    assert feedback["backgroundCheck"]["responseMode"] == "failures_only"
    assert feedback["backgroundCheck"]["status"] == "checked"
    assert feedback["backgroundCheck"]["obligations"] == []
    assert feedback["unsupportedIsNotPropositionFalse"] is True
    try:
        run_polynomial_finite_sum(summand="1/k", lower=1, upper=3)
    except DomainError as error:
        failed = project_surface_feedback({"status": "error"}, error=error)
    else:
        raise AssertionError("1/k must fail closed")
    assert failed["backgroundCheck"]["status"] == "attention_required"
    assert failed["compute"]["value"] is None


def test_hash_binding_is_separate_from_combination_rule_tests() -> None:
    a1_source = A1_TESTS.read_text(encoding="utf-8")
    assert "def test_telescoping_rule_requires_a_checked_identity" in a1_source
    assert "def test_telescoping_rule_rejects_reversed_bounds_and_booleans" in a1_source
    assert "apply_finite_telescoping_sum" not in mutation_hash_binding_is_not_combination.__code__.co_names
    assert "apply_finite_telescoping_sum" not in certificate_binds_claim.__code__.co_names
    verdict = mutation_hash_binding_is_not_combination()
    assert verdict["detected"] is True
    result = run_polynomial_finite_sum(summand="k^2", lower=1, upper=10)
    binding = certificate_binds_claim(
        {
            "format": "not-used",
        },
        {
            "left": result["identity"]["left"],
            "right": result["identity"]["right"],
            "variables": [result["variable"]],
        },
    )
    assert binding["binds"] is False
    assert binding["establishesFiniteSum"] is False
    assert binding["appliesCombinationRule"] is False


def test_mutation_catalog_detects_the_brief_negatives() -> None:
    catalog = run_mutation_catalog()
    assert catalog["allDetected"] is True, catalog["failed"]
    ids = {item["id"] for item in catalog["results"]}
    assert ids >= {
        "tampered-coefficients",
        "wrong-G",
        "deleted-bound-step",
        "reversed-bounds",
        "wrong-variable",
        "wrong-domain-harmonic",
        "foreign-certificate",
        "forged-verified-premise",
        "forged-kernel-checked",
        "stale-pack-version",
        "rewritten-result",
        "unsupported-as-counterexample",
        "hash-binding-is-not-combination",
    }
    by_id = {item["id"]: item for item in catalog["results"]}
    assert by_id["unsupported-as-counterexample"]["propositionTreatedAsFalse"] is False
    assert by_id["wrong-domain-harmonic"]["propositionTreatedAsFalse"] is False
    assert by_id["foreign-certificate"]["ownEstablishesFiniteSum"] is False
    assert by_id["hash-binding-is-not-combination"]["detected"] is True
    assert interpret_outcome("unsupported", code="E_UNSUPPORTED")["propositionFalsified"] is False
    assert interpret_outcome("inapplicable", code="E_UNSUPPORTED")["isCounterexample"] is False
    assert interpret_outcome("falsified")["propositionFalsified"] is True


def test_rewritten_result_cannot_be_recorded_as_coverage() -> None:
    result = run_polynomial_finite_sum(summand="k^2", lower=1, upper=10)
    tampered = deepcopy(result)
    tampered["value"] = {"exact": "0", "numerator": 0, "denominator": 1}
    with pytest.raises(CoverageIntegrityError, match="rewritten"):
        verify_typed_binding(tampered)
    with pytest.raises(CoverageIntegrityError):
        record_coverage({"summand": "k^2", "lower": 1, "upper": 10}, tampered)


def test_stale_pack_version_is_rejected_without_running_the_sum() -> None:
    pack = json.loads(
        json.dumps({key: value for key, value in load_pack().items() if key != "_packPath"})
    )
    pack["version"] = "9.9.9-forged"
    with pytest.raises(PackApplicationError, match="stale or unexpected") as caught:
        apply_method_pack({"summand": "k^3", "lower": 1, "upper": 20}, pack=pack)
    assert caught.value.details["reason"] == "stale_or_unexpected_pack_version"


def test_cli_writes_coverage_sidecar(tmp_path: Path) -> None:
    coverage_path = tmp_path / "t1-coverage.json"
    completed = _cli(
        A1_RUNNER,
        "--task",
        str(A1_EXAMPLE),
        "--coverage-output",
        str(coverage_path),
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    payload = json.loads(completed.stdout)
    stored = json.loads(coverage_path.read_text(encoding="utf-8"))
    assert payload["value"]["exact"] == "385"
    assert payload["coverage"]["kind"] == COVERAGE_KIND
    assert stored["generatedObligations"][0]["id"] == DIFFERENCE_IDENTITY_OBLIGATION_ID
    assert stored["claimCoverage"]["coversOriginalTaskClaim"] is False
    assert stored["typedBinding"]["recomputed"]["exact"] == "385"

    cubes_coverage = tmp_path / "cubes-coverage.json"
    cubes = _cli(
        A2_RUNNER,
        "apply",
        "--task",
        str(CUBES_EXAMPLE),
        "--coverage-output",
        str(cubes_coverage),
        "--no-baseline",
    )
    assert cubes.returncode == 0, cubes.stderr + cubes.stdout
    cubes_stored = json.loads(cubes_coverage.read_text(encoding="utf-8"))
    assert cubes_stored["typedBinding"]["recomputed"]["exact"] == "44100"
    assert cubes_stored["claimCoverage"]["coversOriginalTaskClaim"] is False

    rejected = _cli(
        A1_RUNNER,
        "--summand",
        "1/k",
        "--lower",
        "1",
        "--upper",
        "3",
        "--coverage-output",
        str(tmp_path / "harmonic-coverage.json"),
    )
    assert rejected.returncode == 2
    harmonic = json.loads((tmp_path / "harmonic-coverage.json").read_text(encoding="utf-8"))
    assert harmonic["generatedObligations"] == []
    assert harmonic["outcome"]["propositionFalsified"] is False
    assert harmonic["honesty"]["unsupportedIsNotACounterexample"] is True
