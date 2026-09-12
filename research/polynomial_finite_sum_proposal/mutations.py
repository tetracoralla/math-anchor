"""Mutation / negative experiments for the polynomial finite-sum coverage record.

These are ordinary Python procedures, not a workflow DSL. Combination-rule
unit tests remain in test_polynomial_finite_sum_proposal.py; hash binding here
does not apply the telescoping rule.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from math_anchor.sandbox import run_operation

from research.method_packs.apply import PackApplicationError, apply_method_pack
from research.method_packs.format import PACK_VERSION
from research.method_packs.loader import load_pack
from research.polynomial_finite_sum_proposal.coverage import (
    CoverageIntegrityError,
    certificate_binds_claim,
    coverage_from_failure,
    interpret_outcome,
    record_coverage,
    verify_typed_binding,
)
from research.polynomial_finite_sum_proposal.polynomials import (
    DomainError,
    construct_antidifference,
    difference_identity_sources,
    evaluate_univariate,
    fraction_payload,
    parse_summand,
)
from research.polynomial_finite_sum_proposal.runner import run_polynomial_finite_sum
from math_anchor.obligations import OBLIGATION_SET_SCHEMA_VERSION, check_obligation_set
from math_anchor.safe_expression import make_symbols


T1_TASK = {"summand": "k^2", "variable": "k", "lower": 1, "upper": 10}
CUBES_TASK = {
    "taskId": "A2-second-sum-k-cubed-1-to-20",
    "summand": "k^3",
    "variable": "k",
    "lower": 1,
    "upper": 20,
}


def _digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(payload).hexdigest()}"


def _verdict(
    mutation_id: str,
    *,
    detected: bool,
    expected: str,
    observed: str,
    proposition_treated_as_false: bool = False,
    notes: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": mutation_id,
        "detected": bool(detected),
        "passed": bool(detected),
        "expected": expected,
        "observed": observed,
        "propositionTreatedAsFalse": proposition_treated_as_false,
        "unsupportedTreatedAsCounterexample": False,
    }
    if notes:
        payload["notes"] = notes
    if extra:
        payload.update(extra)
    return payload


def _identity_certificate(result: dict[str, Any]) -> dict[str, Any]:
    produced = run_operation(
        "certificate.polynomial_identity",
        {
            "left": result["identity"]["left"],
            "right": result["identity"]["right"],
            "variables": [result["variable"]],
        },
    )
    if produced.get("status") != "ok" or not isinstance(produced.get("certificate"), dict):
        raise AssertionError("could not produce a polynomial-identity certificate for the mutation")
    return produced["certificate"]


def _identity_claim(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "left": result["identity"]["left"],
        "right": result["identity"]["right"],
        "variables": [result["variable"]],
    }


def mutation_tampered_coefficients() -> dict[str, Any]:
    result = run_polynomial_finite_sum(summand="k^2", lower=1, upper=10)
    certificate = _identity_certificate(result)
    tampered = deepcopy(certificate)
    # A true identity has an empty difference. Inject a fake term and re-hash so
    # the digest is self-consistent while the coefficients are not.
    if tampered["normalizedDifference"]:
        tampered["normalizedDifference"][0]["coefficient"] = "99"
    else:
        tampered["normalizedDifference"] = [{"powers": [0], "coefficient": "99"}]
    digest_payload = dict(tampered)
    digest_payload.pop("certificateDigest")
    tampered["certificateDigest"] = _digest(digest_payload)
    binding = certificate_binds_claim(tampered, _identity_claim(result))
    return _verdict(
        "tampered-coefficients",
        detected=binding["binds"] is False and binding["reason"] == "certificate_internally_inconsistent",
        expected="certificate_internally_inconsistent",
        observed=str(binding["reason"]),
        extra={"establishesFiniteSum": binding["establishesFiniteSum"], "bindsAuthorship": binding["bindsAuthorship"]},
    )


def mutation_wrong_g() -> dict[str, Any]:
    result = run_polynomial_finite_sum(
        summand="k^2",
        lower=1,
        upper=10,
        antidifference="k^3 / 3",
        compare_baseline=False,
    )
    coverage = record_coverage(T1_TASK, result)
    detected = (
        result["status"] == "falsified"
        and "value" not in result
        and coverage["claimCoverage"]["procedureEstablishedFiniteSumValue"] is False
        and coverage["outcome"]["falsifies"].startswith("the submitted difference identity")
    )
    return _verdict(
        "wrong-G",
        detected=detected,
        expected="falsified-identity-no-sum",
        observed=str(result["status"]),
        proposition_treated_as_false=True,
        notes="Falsifies this G as an antidifference of this p. Does not yield a finite-sum value.",
    )


def mutation_reversed_bounds() -> dict[str, Any]:
    try:
        run_polynomial_finite_sum(summand="k^2", lower=5, upper=1)
        observed = "ok"
        error: BaseException | None = None
    except DomainError as caught:
        error = caught
        observed = caught.code
    coverage = coverage_from_failure({"summand": "k^2", "variable": "k", "lower": 5, "upper": 1}, error) if error else None
    detected = (
        error is not None
        and error.code == "E_DOMAIN"
        and coverage is not None
        and coverage["outcome"]["propositionFalsified"] is False
        and coverage["generatedObligations"] == []
    )
    return _verdict(
        "reversed-bounds",
        detected=detected,
        expected="E_DOMAIN-unsupported-not-falsified",
        observed=observed,
        extra={"generatedObligationCount": 0 if coverage is None else len(coverage["generatedObligations"])},
    )


def mutation_deleted_bound_step() -> dict[str, Any]:
    """A checked identity plus raw reversed-bound subtraction is not a covered finite sum."""

    _source, terms, expression = parse_summand("k^2", "k")
    symbol = make_symbols(["k"])["k"]
    g_terms, _constructor = construct_antidifference(expression, symbol)
    sources = difference_identity_sources(g_terms, terms, "k")
    _feedback, receipt = check_obligation_set(
        {
            "schemaVersion": OBLIGATION_SET_SCHEMA_VERSION,
            "assumptionSets": [
                {
                    "id": "discrete-sum-domain",
                    "assumptions": [
                        "k is a commuting indeterminate over the rationals",
                        "the summation index ranges over integers",
                    ],
                }
            ],
            "obligations": [
                {
                    "id": "difference-identity",
                    "kind": "polynomial_identity",
                    "claim": {
                        "left": sources["left"],
                        "right": sources["right"],
                        "variables": ["k"],
                    },
                    "assumptionSet": "discrete-sum-domain",
                }
            ],
            "responseMode": "full",
        }
    )
    identity_checked = receipt["obligations"][0]["status"] == "checked"
    raw = evaluate_univariate(sources["antidifference"], "k", 2) - evaluate_univariate(
        sources["antidifference"], "k", 5
    )
    forged = {
        "status": "ok",
        "kind": "math-anchor.research.polynomial-finite-sum.v0",
        "summand": "k^2",
        "variable": "k",
        "lower": 5,
        "upper": 1,
        "antidifference": sources["antidifference"],
        "identity": {
            "left": sources["left"],
            "right": sources["right"],
            "status": "checked",
            "assuranceLevel": "exact_symbolic",
            "claimDigest": receipt["obligations"][0]["claimDigest"],
        },
        "value": fraction_payload(raw),
        "formalKernelChecked": False,
        "obligationReceipt": receipt,
    }
    binding_failed = False
    try:
        verify_typed_binding(forged)
    except CoverageIntegrityError:
        binding_failed = True
    honest = record_coverage({"summand": "k^2", "variable": "k", "lower": 5, "upper": 1}, forged)
    # record_coverage will fail verify_typed_binding because reversed bounds...
    # actually record_coverage calls _typed_binding which calls verify_typed_binding
    # if procedure_established. For reversed bounds, bounds_ok is False so
    # procedure_established is False, so it may RECORD coverage without treating
    # the value as established.
    established = honest["claimCoverage"]["procedureEstablishedFiniteSumValue"]
    detected = identity_checked and binding_failed and established is False and raw != 0
    return _verdict(
        "deleted-bound-step",
        detected=detected,
        expected="checked-identity-does-not-cover-reversed-raw-subtraction",
        observed=(
            f"identity={receipt['obligations'][0]['status']}; "
            f"raw={raw}; established={established}; binding_failed={binding_failed}"
        ),
        notes="Deleting the bound step and subtracting G(2)-G(5) is not a covered finite sum.",
        extra={"rawSubtractionExact": str(raw), "identityChecked": identity_checked},
    )


def mutation_wrong_variable() -> dict[str, Any]:
    try:
        run_polynomial_finite_sum(summand="k^2", variable="n", lower=1, upper=3)
        error = None
        observed = "ok"
    except DomainError as caught:
        error = caught
        observed = caught.code
    coverage = None
    if error is not None:
        coverage = coverage_from_failure(
            {"summand": "k^2", "variable": "n", "lower": 1, "upper": 3},
            error,
        )
    t1 = run_polynomial_finite_sum(summand="k^2", lower=1, upper=10)
    certificate = _identity_certificate(t1)
    mismatched = certificate_binds_claim(
        certificate,
        {
            "left": t1["identity"]["left"],
            "right": t1["identity"]["right"],
            "variables": ["n"],
        },
    )
    detected = (
        error is not None
        and error.code == "E_UNSUPPORTED"
        and coverage is not None
        and coverage["outcome"]["propositionFalsified"] is False
        and mismatched["binds"] is False
    )
    return _verdict(
        "wrong-variable",
        detected=detected,
        expected="E_UNSUPPORTED-and-certificate-variable-mismatch",
        observed=f"{observed}; binds={mismatched['binds']}",
    )


def mutation_wrong_domain() -> dict[str, Any]:
    try:
        run_polynomial_finite_sum(summand="1/k", lower=1, upper=3)
        error = None
        observed = "ok"
    except DomainError as caught:
        error = caught
        observed = caught.code
    interpreted = interpret_outcome(
        "unsupported" if error is not None and error.code == "E_UNSUPPORTED" else "ok",
        code=None if error is None else error.code,
    )
    coverage = coverage_from_failure({"summand": "1/k", "variable": "k", "lower": 1, "upper": 3}, error) if error else None
    detected = (
        error is not None
        and error.code == "E_UNSUPPORTED"
        and interpreted["propositionFalsified"] is False
        and interpreted["isCounterexample"] is False
        and coverage is not None
        and coverage["generatedObligations"] == []
        and coverage["honesty"]["unsupportedIsNotACounterexample"] is True
    )
    return _verdict(
        "wrong-domain-harmonic",
        detected=detected,
        expected="E_UNSUPPORTED-not-a-counterexample",
        observed=observed,
    )


def mutation_foreign_certificate() -> dict[str, Any]:
    squares = run_polynomial_finite_sum(summand="k^2", lower=1, upper=10)
    cubes = run_polynomial_finite_sum(summand="k^3", lower=1, upper=20)
    foreign = certificate_binds_claim(_identity_certificate(squares), _identity_claim(cubes))
    own = certificate_binds_claim(_identity_certificate(squares), _identity_claim(squares))
    detected = (
        foreign["binds"] is False
        and foreign["reason"] == "certificate_statement_does_not_match_claim"
        and foreign["establishesFiniteSum"] is False
        and own["binds"] is True
        and own["establishesFiniteSum"] is False
        and own["appliesCombinationRule"] is False
    )
    return _verdict(
        "foreign-certificate",
        detected=detected,
        expected="certificate_statement_does_not_match_claim",
        observed=str(foreign["reason"]),
        notes="T1's valid certificate does not cover the cubes identity. Matching hashes still do not apply telescoping.",
        extra={"ownBinds": own["binds"], "ownEstablishesFiniteSum": own["establishesFiniteSum"]},
    )


def mutation_forged_verified_premise() -> dict[str, Any]:
    try:
        apply_method_pack(
            {
                "summand": "k*(k-1)/2",
                "lower": 2,
                "upper": 10,
                "premises": [
                    {
                        "id": "forged",
                        "statement": "C(k,2)=k*(k-1)/2",
                        "verifiedByPack": True,
                    }
                ],
            }
        )
        error = None
        observed = "ok"
    except PackApplicationError as caught:
        error = caught
        observed = caught.message
    detected = error is not None and "verifiedByPack" in error.message
    return _verdict(
        "forged-verified-premise",
        detected=detected,
        expected="reject-verifiedByPack",
        observed=observed if isinstance(observed, str) else str(observed),
    )


def mutation_forged_kernel_checked() -> dict[str, Any]:
    result = run_polynomial_finite_sum(summand="k^2", lower=1, upper=10)
    forged = deepcopy(result)
    forged["formalKernelChecked"] = True
    raised = False
    try:
        record_coverage(T1_TASK, forged)
    except CoverageIntegrityError:
        raised = True
    detected = result["formalKernelChecked"] is False and raised
    return _verdict(
        "forged-kernel-checked",
        detected=detected,
        expected="CoverageIntegrityError",
        observed="raised" if raised else "accepted",
    )


def mutation_stale_pack_version() -> dict[str, Any]:
    pack = load_pack()
    stale = json.loads(json.dumps({key: value for key, value in pack.items() if key != "_packPath"}))
    stale["version"] = "0.0.1-expired"
    try:
        apply_method_pack(CUBES_TASK, pack=stale, compare_baseline=False)
        error = None
        observed = "ok"
    except PackApplicationError as caught:
        error = caught
        observed = caught.details.get("reason") if caught.details else caught.message
    detected = (
        error is not None
        and error.code == "E_INPUT"
        and (error.details or {}).get("reason") == "stale_or_unexpected_pack_version"
        and (error.details or {}).get("requiredVersion") == PACK_VERSION
    )
    return _verdict(
        "stale-pack-version",
        detected=detected,
        expected="stale_or_unexpected_pack_version",
        observed=str(observed),
    )


def mutation_rewritten_result() -> dict[str, Any]:
    result = run_polynomial_finite_sum(summand="k^2", lower=1, upper=10)
    tampered = deepcopy(result)
    tampered["value"] = {"exact": "44100", "numerator": 44100, "denominator": 1}
    value_failed = False
    try:
        verify_typed_binding(tampered)
    except CoverageIntegrityError as error:
        value_failed = "rewritten" in error.message
    packed = apply_method_pack(CUBES_TASK)
    chain_tampered = deepcopy(packed)
    chain_tampered["value"] = packed["value"]
    for step in chain_tampered["chain"]:
        if step.get("step") == "combine_with_infrastructure_telescoping":
            step["valueEnteredLaterSteps"] = {"exact": "1", "numerator": 1, "denominator": 1}
    chain_failed = False
    try:
        verify_typed_binding(chain_tampered, task=CUBES_TASK)
    except CoverageIntegrityError as error:
        chain_failed = "rewritten" in error.message or "valueEnteredLaterSteps" in error.message
    detected = value_failed and chain_failed and result["value"]["exact"] == "385"
    return _verdict(
        "rewritten-result",
        detected=detected,
        expected="typed-binding-rejects-rewritten-value-and-chain",
        observed=f"value_failed={value_failed}; chain_failed={chain_failed}",
    )


def mutation_joint_g_and_value_rewrite() -> dict[str, Any]:
    """A joint rewrite of G and value must not inherit a stale checked identity."""

    result = run_polynomial_finite_sum(summand="k^2", lower=1, upper=10)
    tampered = deepcopy(result)
    tampered["antidifference"] = "0"
    tampered["value"] = {"exact": "0", "numerator": 0, "denominator": 1}
    tampered["endpoints"] = {
        "gAtUpperPlusOne": {"exact": "0", "numerator": 0, "denominator": 1},
        "gAtLower": {"exact": "0", "numerator": 0, "denominator": 1},
    }
    joint_failed = False
    try:
        verify_typed_binding(tampered)
    except CoverageIntegrityError as error:
        joint_failed = "inconsistent with the checked identity" in error.message
    record_failed = False
    try:
        record_coverage(T1_TASK, tampered)
    except CoverageIntegrityError:
        record_failed = True
    value_only = deepcopy(result)
    value_only["value"] = {"exact": "0", "numerator": 0, "denominator": 1}
    value_only_failed = False
    try:
        verify_typed_binding(value_only)
    except CoverageIntegrityError as error:
        value_only_failed = "rewritten" in error.message
    honest_bound = False
    try:
        honest_bound = verify_typed_binding(result).get("currentGBoundToCheckedIdentity") is True
    except CoverageIntegrityError:
        honest_bound = False
    detected = joint_failed and record_failed and value_only_failed and honest_bound
    return _verdict(
        "joint-g-and-value-rewrite",
        detected=detected,
        expected="typed-binding-rejects-stale-identity-after-joint-G-and-value-rewrite",
        observed=(
            f"joint_failed={joint_failed}; record_failed={record_failed}; "
            f"value_only_failed={value_only_failed}; honest_bound={honest_bound}"
        ),
        notes=(
            "identity.status remains checked and identity.left still names the "
            "original G. Binding must not treat G=0, value=0 as an established sum."
        ),
    )


def mutation_unsupported_as_counterexample() -> dict[str, Any]:
    harmonic = mutation_wrong_domain()
    try:
        apply_method_pack({"summand": "1/k", "lower": 1, "upper": 3})
        pack_error = None
    except PackApplicationError as caught:
        pack_error = caught
    interpreted = interpret_outcome("inapplicable", code="E_UNSUPPORTED")
    detected = (
        harmonic["detected"]
        and pack_error is not None
        and pack_error.code == "E_UNSUPPORTED"
        and interpreted["propositionFalsified"] is False
        and interpreted["isCounterexample"] is False
        and interpreted["unsupportedTreatedAsCounterexample"] is False
    )
    return _verdict(
        "unsupported-as-counterexample",
        detected=detected,
        expected="unsupported-is-not-proposition-false",
        observed=pack_error.code if pack_error is not None else "ok",
    )


def mutation_hash_binding_is_not_combination() -> dict[str, Any]:
    """Hash-only path: must not call the telescoping combination rule."""

    result = run_polynomial_finite_sum(summand="k^2", lower=1, upper=10)
    binding = certificate_binds_claim(_identity_certificate(result), _identity_claim(result))
    detected = (
        binding["binds"] is True
        and binding["appliesCombinationRule"] is False
        and binding["establishesFiniteSum"] is False
        and binding["bindsAuthorship"] is False
        and isinstance(result["identity"].get("claimDigest"), str)
        and result["identity"]["claimDigest"].startswith("sha256:")
    )
    return _verdict(
        "hash-binding-is-not-combination",
        detected=detected,
        expected="content-hash-without-telescoping",
        observed=str(binding["reason"]),
        notes=(
            "Combination-rule tests stay in test_polynomial_finite_sum_proposal.py. "
            "This mutation never calls apply_finite_telescoping_sum."
        ),
    )


MUTATIONS = (
    mutation_tampered_coefficients,
    mutation_wrong_g,
    mutation_reversed_bounds,
    mutation_deleted_bound_step,
    mutation_wrong_variable,
    mutation_wrong_domain,
    mutation_foreign_certificate,
    mutation_forged_verified_premise,
    mutation_forged_kernel_checked,
    mutation_stale_pack_version,
    mutation_rewritten_result,
    mutation_joint_g_and_value_rewrite,
    mutation_unsupported_as_counterexample,
    mutation_hash_binding_is_not_combination,
)


def run_mutation_catalog() -> dict[str, Any]:
    results = [mutation() for mutation in MUTATIONS]
    failed = [item["id"] for item in results if not item["detected"]]
    return {
        "kind": "math-anchor.research.polynomial-finite-sum-mutations.v0",
        "allDetected": not failed,
        "failed": failed,
        "count": len(results),
        "results": results,
        "combinationRuleTestsAreSeparate": True,
        "hashBindingDoesNotProveAuthorshipOrTruth": True,
    }


def main(argv: list[str] | None = None) -> int:
    del argv
    catalog = run_mutation_catalog()
    sys.stdout.write(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
    return 0 if catalog["allDetected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
