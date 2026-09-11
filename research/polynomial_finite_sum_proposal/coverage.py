"""Claim → obligation coverage for the polynomial finite-sum workflow.

Ordinary Python. Not an obligation-runtime dataflow language, not a fifth MCP
tool, and not a natural-language compiler. Success of the submitted identity
obligation is not coverage of the original finite-sum claim.
"""

from __future__ import annotations

from fractions import Fraction
import json
from pathlib import Path
from typing import Any

from math_anchor.certificate_checker import (
    CHECKER_SYSTEM,
    CHECKER_VERSION,
    CertificateValidationError,
    verify_polynomial_identity_certificate,
)
from math_anchor.errors import CalculatorError
from math_anchor.expression_source import normalize_expression_source

from .polynomials import (
    DomainError,
    evaluate_univariate,
    fraction_payload,
    parse_antidifference,
    parse_summand,
    polynomial_source,
    rational_from_payload,
)
from .telescoping import (
    TELESCOPING_RULE_ID,
    TELESCOPING_RULE_ORIGIN,
    TelescopingRuleError,
    apply_finite_telescoping_sum,
)


COVERAGE_KIND = "math-anchor.research.polynomial-finite-sum-coverage.v0"
DIFFERENCE_IDENTITY_OBLIGATION_ID = "difference-identity"
DIFFERENCE_IDENTITY_KIND = "polynomial_identity"
ASSUMPTION_SET_ID = "discrete-sum-domain"
FROZEN_WORKFLOW_PATH = Path(__file__).with_name("workflow_coverage.json")

IDENTITY_DOES_NOT_COVER = (
    "natural-language-to-claim translation",
    "integer bound convention and empty/reversed sums",
    "construction of G (Gosper is untrusted construction)",
    "the finite-sum combination G(b+1)-G(a)",
    "binomial or other caller rewrites",
    "the whole conclusion as a Lean kernel theorem",
    "universal quantification over all degrees in the checker limit",
)


class CoverageIntegrityError(CalculatorError):
    """Coverage record is internally dishonest or a mutation was detected."""


def static_workflow_coverage() -> dict[str, Any]:
    """Committed machine-readable table for this domain workflow (no instance digests)."""

    return {
        "kind": COVERAGE_KIND,
        "workflow": "rational-polynomial-finite-sum",
        "proposalId": "math-anchor.research.polynomial-finite-sum.v0",
        "methodPackId": "math-anchor.research.method-pack.polynomial-antidifference-gosper.v0",
        "notAWorkflowDsl": True,
        "notAFifthMcpTool": True,
        "taskToObligation": {
            "sourceClaimForm": "structured-task-json (summand, variable, lower, upper)",
            "naturalLanguageToClaim": "uncovered",
            "generatedObligationIds": [DIFFERENCE_IDENTITY_OBLIGATION_ID],
            "generatedObligationKind": DIFFERENCE_IDENTITY_KIND,
            "mappingNote": (
                "The domain runner emits one polynomial_identity obligation for "
                "G(k+1)-G(k)=p(k). That mapping is recorded here; it is not a "
                "compiler from prose, and checking that obligation does not cover "
                "the original finite-sum claim."
            ),
        },
        "declaredGoal": (
            "Exact inclusive finite sum of a univariate rational-coefficient "
            "polynomial p(k) on integer bounds, via a checked discrete antidifference."
        ),
        "bounds": {
            "inclusive": True,
            "integerIndex": True,
            "magnitudeLimit": 1_000_000,
            "emptySum": "upper == lower - 1 yields 0",
            "reversedBounds": "unsupported when upper < lower - 1 (not Karr reversal)",
            "coveredByDifferenceIdentityObligation": False,
        },
        "assumptions": {
            "setId": ASSUMPTION_SET_ID,
            "interpretation": "bound_not_evaluated",
            "text": [
                "the summation variable is a commuting indeterminate over the rationals",
                "the summation index ranges over integers",
            ],
            "note": (
                "Assumption prose is hash-bound and not evaluated. Integer-index "
                "semantics are not proved by the polynomial-identity checker."
            ),
        },
        "steps": list(WORKFLOW_STEPS),
        "typedBindingPattern": {
            "name": "finite-sum-value",
            "formula": "G(upper + 1) - G(lower)",
            "type": {
                "kind": "exact_rational",
                "python": "fractions.Fraction",
                "payloadFields": ["exact", "numerator", "denominator"],
            },
            "producedBy": {
                "ruleId": TELESCOPING_RULE_ID,
                "origin": TELESCOPING_RULE_ORIGIN,
                "agentExtracted": False,
                "notAnObligation": True,
            },
            "entersLaterParameters": [
                "result.value (compute surface)",
                "method-pack downstream.value",
                "method-pack chain combine_with_infrastructure_telescoping.valueEnteredLaterSteps",
            ],
            "currentGBoundToCheckedIdentity": True,
            "notAGeneralDataflowLanguage": True,
        },
        "evidenceScope": {
            "identityScope": "polynomial_identity_over_rationals",
            "identityAssurance": "exact_symbolic",
            "formalKernelChecked": False,
            "instancesAreNotUniversalProof": True,
            "structureValidationIsNotMathematicalCorrectness": True,
            "hashBindsContentNotAuthorshipOrTruth": True,
            "obligationSuccessIsNotClaimCoverage": True,
            "unsupportedIsNotACounterexample": True,
            "telescopingIsHandProvidedInfrastructure": True,
        },
        "honesty": _honesty_flags(),
    }


WORKFLOW_STEPS: tuple[dict[str, Any], ...] = (
    {
        "id": "nl-to-structured-claim",
        "coverage": "uncovered",
        "fixedRule": None,
        "obligationId": None,
        "covers": None,
        "doesNotCover": "Caller prose or a natural-language task statement.",
        "note": "Inputs are already structured JSON. There is no NL→claim compiler.",
    },
    {
        "id": "parse-univariate-qq-polynomial",
        "coverage": "fixed-python-rule",
        "fixedRule": "research.polynomial_finite_sum_proposal.polynomials.parse_summand",
        "obligationId": None,
        "covers": (
            "Original summand is a univariate QQ-polynomial with nonzero "
            "rational constant denominators only, checked before cancellation."
        ),
        "doesNotCover": "Special functions, 1/k, k/k, extra symbols, inexact floats.",
    },
    {
        "id": "integer-bounds-convention",
        "coverage": "fixed-python-rule",
        "fixedRule": "require_integer + reversed-bound DomainError + combination-rule gate",
        "obligationId": None,
        "covers": "Inclusive integer bounds; empty sum; reject upper < lower - 1.",
        "doesNotCover": "The difference-identity obligation does not mention bounds.",
        "note": "Deleting this step leaves a checked identity that does not establish a finite sum.",
    },
    {
        "id": "construct-antidifference",
        "coverage": "untrusted-construction",
        "fixedRule": "sympy.concrete.gosper.gosper_sum (summation fallback)",
        "obligationId": None,
        "covers": None,
        "doesNotCover": "Construction is not a proof that G(k+1)-G(k)=p(k).",
    },
    {
        "id": "difference-identity",
        "coverage": "obligation",
        "fixedRule": "math_anchor.obligations polynomial_identity + stdlib certificate checker",
        "obligationId": DIFFERENCE_IDENTITY_OBLIGATION_ID,
        "kind": DIFFERENCE_IDENTITY_KIND,
        "covers": "G(k+1)-G(k)=p(k) as rational polynomials with constant denominators.",
        "doesNotCover": list(IDENTITY_DOES_NOT_COVER),
    },
    {
        "id": "evaluate-endpoints",
        "coverage": "fixed-python-rule",
        "fixedRule": "certificate_checker polynomial parser at integer points",
        "obligationId": None,
        "covers": "Exact rational values G(upper+1) and G(lower) in the checker language.",
        "doesNotCover": "Not a kernel check; not the combination step.",
    },
    {
        "id": "telescoping-combination",
        "coverage": "hand-provided-infrastructure",
        "fixedRule": TELESCOPING_RULE_ID,
        "obligationId": None,
        "agentExtracted": False,
        "covers": (
            "Given a checked difference identity and in-domain integer bounds, "
            "the inclusive sum equals G(upper+1)-G(lower)."
        ),
        "doesNotCover": "Not an obligation. Not Agent-extracted A2 novelty. Not Lean.",
        "note": "Combination-rule tests live in test_polynomial_finite_sum_proposal.py, separate from hash binding.",
    },
    {
        "id": "typed-binding-into-later-parameters",
        "coverage": "domain-python-binding",
        "fixedRule": "research.polynomial_finite_sum_proposal.coverage.verify_typed_binding",
        "obligationId": None,
        "covers": (
            "The computed exact rational is the same G(b+1)-G(a) recorded as "
            "value/downstream, and current G is the G named by the checked identity."
        ),
        "doesNotCover": "No general obligation dataflow; dependsOn is unused.",
    },
    {
        "id": "binomial-rewrite",
        "coverage": "uncovered-conditional-premise",
        "fixedRule": None,
        "obligationId": None,
        "covers": None,
        "doesNotCover": "C(k,r) identities such as C(k,2)=k(k-1)/2. Hockey-stick stays conditional.",
    },
    {
        "id": "whole-finite-sum-kernel",
        "coverage": "uncovered",
        "fixedRule": None,
        "obligationId": None,
        "formalKernelChecked": False,
        "covers": None,
        "doesNotCover": "The finite-sum conclusion is never marked formal_kernel_checked.",
    },
    {
        "id": "universal-quantification",
        "coverage": "uncovered",
        "fixedRule": None,
        "obligationId": None,
        "covers": None,
        "doesNotCover": "Checked instances are not a proof for every polynomial below the degree limit.",
    },
)


def record_coverage(
    task: dict[str, Any] | None,
    result: dict[str, Any] | None,
    *,
    error: BaseException | None = None,
    pack: dict[str, Any] | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """Build an instance coverage record from a structured task and a runner/apply result."""

    task = task if isinstance(task, dict) else {}
    result = result if isinstance(result, dict) else {}
    view = _task_view(task, result)
    identity = result.get("identity") if isinstance(result.get("identity"), dict) else {}
    receipt = result.get("obligationReceipt") if isinstance(result.get("obligationReceipt"), dict) else {}
    status = _status(result, error)
    generated = _generated_obligations(identity, receipt)
    steps = _instantiate_steps(view, result, generated, status, error)
    procedure_established = _procedure_established(status, generated, steps, result)
    typed = _typed_binding(view, result, procedure_established)
    if result.get("formalKernelChecked") is True:
        raise CoverageIntegrityError(
            "E_INPUT",
            "forged or stale formal_kernel_checked cannot be recorded as coverage",
        )
    if pack is not None and pack.get("verification", {}).get("formalKernelChecked") is True:
        raise CoverageIntegrityError(
            "E_INPUT",
            "pack marks formal_kernel_checked; this workflow must not record that as true",
        )

    record: dict[str, Any] = {
        "kind": COVERAGE_KIND,
        "source": source or _infer_source(result),
        "taskClaim": {
            "form": "structured-task-json",
            "naturalLanguageUnchecked": True,
            "rendered": _render_sum_claim(view),
            "summand": view.get("summand"),
            "variable": view.get("variable"),
            "lower": view.get("lower"),
            "upper": view.get("upper"),
            "taskId": view.get("taskId"),
            "premises": view.get("premises"),
        },
        "declaredGoal": "exact inclusive finite sum of the structured summand on the given integer bounds",
        "bounds": {
            "inclusive": True,
            "lower": view.get("lower"),
            "upper": view.get("upper"),
            "emptySum": "upper == lower - 1 yields 0",
            "reversedBounds": "unsupported when upper < lower - 1",
            "coveredByDifferenceIdentityObligation": False,
        },
        "assumptions": {
            "setId": ASSUMPTION_SET_ID,
            "interpretation": "bound_not_evaluated",
            "text": [
                f"{view.get('variable', 'k')} is a commuting indeterminate over the rationals",
                "the summation index ranges over integers",
            ],
        },
        "generatedObligations": generated,
        "steps": steps,
        "typedBinding": typed,
        "claimCoverage": {
            "allSubmittedObligationsChecked": _all_obligations_checked(generated),
            "coversOriginalTaskClaim": False,
            "procedureEstablishedFiniteSumValue": procedure_established,
            "reason": _claim_coverage_reason(generated),
        },
        "evidenceScope": {
            "identityScope": identity.get("scope") or "polynomial_identity_over_rationals",
            "identityAssurance": identity.get("assuranceLevel"),
            "identityStatus": identity.get("status") or _identity_status_from_generated(generated),
            "formalKernelChecked": False,
            "instancesAreNotUniversalProof": True,
            "structureValidationIsNotMathematicalCorrectness": True,
            "hashBindsContentNotAuthorshipOrTruth": True,
            "unsupportedIsNotACounterexample": True,
        },
        "feedback": project_surface_feedback(result, error=error, pack=pack),
        "outcome": _outcome_record(status, error),
        "honesty": _honesty_flags(),
        "workflowStepsStatic": [step["id"] for step in WORKFLOW_STEPS],
    }
    pack_info = _pack_info(result, pack)
    if pack_info is not None:
        record["methodPack"] = pack_info
    verify_coverage_honesty(record, result=result)
    return record


def coverage_from_failure(
    task: dict[str, Any],
    error: BaseException,
    *,
    pack: dict[str, Any] | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    payload = {
        "status": "inapplicable"
        if isinstance(error, CalculatorError)
        and (getattr(error, "details", None) or {}).get("applicability") == "rejected"
        else "error",
        "error": {
            "code": getattr(error, "code", "E_RUNTIME"),
            "message": getattr(error, "message", str(error)),
        },
    }
    details = getattr(error, "details", None)
    if isinstance(details, dict):
        payload["error"]["details"] = details
    return record_coverage(task, payload, error=error, pack=pack, source=source)


def project_surface_feedback(
    result: dict[str, Any] | None,
    *,
    error: BaseException | None = None,
    pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Outer feedback using existing full/failures_only. No new public responseMode."""

    result = result if isinstance(result, dict) else {}
    status = _status(result, error)
    receipt = result.get("obligationReceipt") if isinstance(result.get("obligationReceipt"), dict) else {}
    summary = receipt.get("summary") if isinstance(receipt.get("summary"), dict) else None
    failures = []
    if isinstance(receipt.get("obligations"), list):
        failures = [
            {
                "id": entry.get("id"),
                "status": entry.get("status"),
                "kind": entry.get("kind"),
            }
            for entry in receipt["obligations"]
            if isinstance(entry, dict) and entry.get("status") != "checked"
        ]
    all_checked = bool(summary) and summary.get("checked") == summary.get("total")
    compute = {
        "intent": "compute",
        "returns": "value_and_necessary_conditions" if status == "ok" else "no_value",
        "value": result.get("value") if status == "ok" else None,
        "formula": result.get("formula") if status == "ok" else None,
        "necessaryConditions": [
            "univariate QQ-polynomial summand with constant denominators",
            "integer bounds with upper >= lower - 1",
            "independently checked G(k+1)-G(k)=p(k)",
            "hand-provided telescoping combination (infrastructure)",
        ],
        "limitations": result.get("limitations") or [],
        "fullReceipt": "local artifact, not inlined on the compute surface",
    }
    background = {
        "intent": "background_check",
        "responseMode": "failures_only",
        "status": "checked" if status == "ok" and (all_checked or result.get("identity", {}).get("status") == "checked") else "attention_required",
        "obligations": []
        if status == "ok" and not failures
        else failures
        or (
            [{"status": status, "code": _error_code(result, error)}]
            if status not in {"ok", "checked"}
            else []
        ),
        "note": "Successful identity evidence stays on disk; this surface does not add a new responseMode.",
    }
    index = {
        "intent": "research_index",
        "methods": [],
        "note": "Research extraction is indexed compactly at the task-stage boundary; success must not hide it.",
    }
    pack_info = _pack_info(result, pack)
    if pack_info is not None:
        index["methods"].append(
            {
                "id": pack_info.get("id"),
                "version": pack_info.get("version"),
                "status": pack_info.get("statusAtApplication") or pack_info.get("status"),
                "novelty": pack_info.get("novelty"),
                "formalKernelChecked": False,
            }
        )
    return {
        "identityCheckInsideRunner": "full",
        "identityCheckNote": (
            "The A1 runner requests responseMode full so it can read receipt "
            "fields. That is not a new public responseMode. Outer compute vs "
            "background-check surfaces below reuse full/failures_only."
        ),
        "compute": compute,
        "backgroundCheck": background,
        "researchIndex": index,
        "unsupportedMustNotBeSwallowed": True,
        "unsupportedIsNotPropositionFalse": True,
    }


def certificate_binds_claim(certificate: dict[str, Any], claim: dict[str, Any]) -> dict[str, Any]:
    """Bind a polynomial certificate to a claim by content.

    Hash consistency binds content. It does not certify authorship, prove the
    surrounding prose, or apply the telescoping combination rule.
    """

    base = {
        "bindsAuthorship": False,
        "establishesFiniteSum": False,
        "establishesMathematicalTruthBeyondStatement": False,
        "appliesCombinationRule": False,
        "note": (
            "Hash consistency binds content, not authorship or math truth. "
            "A matching certificate is not the finite-sum combination rule."
        ),
    }
    try:
        check = verify_polynomial_identity_certificate(certificate)
    except CertificateValidationError as error:
        return {
            **base,
            "binds": False,
            "reason": "certificate_internally_inconsistent",
            "message": str(error),
        }
    try:
        expected = _normalized_claim(claim)
    except (KeyError, TypeError, AttributeError) as error:
        return {
            **base,
            "binds": False,
            "reason": "claim_is_not_a_polynomial_statement",
            "message": str(error),
        }
    if certificate.get("statement") != expected:
        return {
            **base,
            "binds": False,
            "reason": "certificate_statement_does_not_match_claim",
            "certificateStatement": certificate.get("statement"),
            "claim": expected,
            "message": "A valid certificate for another proposition does not cover this task.",
        }
    return {
        **base,
        "binds": True,
        "reason": "statement_and_internal_digests_match",
        "certificateDigest": check["certificateDigest"],
        "identity": check["identity"],
        "checker": check["checker"],
    }


def interpret_outcome(status: str | None, *, code: str | None = None) -> dict[str, Any]:
    """Classify a runner/apply outcome. Unsupported is not a counterexample."""

    normalized = (status or "unknown").lower()
    unsupported = normalized in {"unsupported", "inapplicable", "error"} and code in {
        "E_UNSUPPORTED",
        "E_DOMAIN",
        "E_LIMIT",
        "E_INPUT",
        "E_AST_BLOCK",
        "E_NAME",
        "E_SYNTAX",
    }
    if normalized == "falsified":
        return {
            "status": "falsified",
            "propositionFalsified": True,
            "falsifies": "the submitted difference identity (this G is not an antidifference of this p)",
            "doesNotFalsify": "an unstated surrounding prose claim",
            "isCounterexampleToFiniteSumExisting": False,
            "unsupportedTreatedAsCounterexample": False,
        }
    if unsupported or normalized in {"unsupported", "inapplicable"}:
        return {
            "status": "unsupported" if code == "E_UNSUPPORTED" or normalized == "unsupported" else normalized,
            "propositionFalsified": False,
            "isCounterexample": False,
            "unsupportedTreatedAsCounterexample": False,
            "note": "Out-of-domain or inapplicable input is not evidence that a mathematical proposition is false.",
        }
    if normalized == "ok":
        return {
            "status": "ok",
            "propositionFalsified": False,
            "isCounterexample": False,
            "unsupportedTreatedAsCounterexample": False,
            "coversOriginalTaskClaim": False,
        }
    return {
        "status": normalized,
        "propositionFalsified": False,
        "isCounterexample": False,
        "unsupportedTreatedAsCounterexample": False,
    }


def verify_typed_binding(
    result: dict[str, Any],
    *,
    task: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Recompute G(b+1)-G(a) and require recorded value/downstream copies to match.

    Current G must be the antidifference named by the checked identity
    statement. A joint rewrite of G and value that leaves a stale
    ``identity.status=checked`` fail-closes.
    """

    view = _task_view(task or {}, result)
    identity = result.get("identity") if isinstance(result.get("identity"), dict) else {}
    identity_status = identity.get("status")
    if identity_status is None:
        receipt = result.get("obligationReceipt")
        if isinstance(receipt, dict) and isinstance(receipt.get("obligations"), list) and receipt["obligations"]:
            identity_status = receipt["obligations"][0].get("status")
    if result.get("status") != "ok" or identity_status != "checked":
        raise CoverageIntegrityError(
            "E_INPUT",
            "typed binding requires a checked difference identity and an ok finite-sum result",
        )
    g_source = result.get("antidifference")
    variable = view.get("variable")
    lower = view.get("lower")
    upper = view.get("upper")
    if not isinstance(g_source, str) or not isinstance(variable, str):
        raise CoverageIntegrityError("E_INPUT", "typed binding requires checker-language G and a variable")
    if type(lower) is not int or type(upper) is not int:
        raise CoverageIntegrityError("E_DOMAIN", "typed binding requires integer bounds")
    if upper < lower - 1:
        raise CoverageIntegrityError(
            "E_DOMAIN",
            "reversed bounds are unsupported; raw endpoint subtraction is not a covered finite sum",
        )
    _require_current_g_bound_to_checked_identity(
        result,
        g_source=g_source,
        variable=variable,
        identity=identity,
    )
    task_summand = view.get("summand")
    if not isinstance(task_summand, str) or not task_summand.strip():
        raise CoverageIntegrityError("E_INPUT", "typed binding requires the original task summand")
    _require_right_matches_original_summand(
        result,
        identity=identity,
        summand=task_summand,
        variable=variable,
    )
    try:
        g_at_upper_plus_one = evaluate_univariate(g_source, variable, upper + 1)
        g_at_lower = evaluate_univariate(g_source, variable, lower)
        recomputed = apply_finite_telescoping_sum(
            difference_identity_checked=True,
            lower=lower,
            upper=upper,
            g_at_upper_plus_one=g_at_upper_plus_one,
            g_at_lower=g_at_lower,
        )
    except (DomainError, TelescopingRuleError) as error:
        raise CoverageIntegrityError(error.code, error.message) from error

    recorded = _fraction_from_payload(result.get("value"))
    if recorded != recomputed:
        raise CoverageIntegrityError(
            "E_RUNTIME",
            "recorded value was rewritten relative to G(upper+1)-G(lower)",
            {
                "recomputed": fraction_payload(recomputed),
                "recorded": result.get("value"),
            },
        )
    endpoints = result.get("endpoints")
    if isinstance(endpoints, dict):
        if "gAtUpperPlusOne" in endpoints:
            _require_same_rational("endpoints.gAtUpperPlusOne", endpoints, "gAtUpperPlusOne", g_at_upper_plus_one)
        if "gAtLower" in endpoints:
            _require_same_rational("endpoints.gAtLower", endpoints, "gAtLower", g_at_lower)
    downstream = result.get("downstream")
    if isinstance(downstream, dict) and "value" in downstream:
        if _fraction_from_payload(downstream.get("value")) != recomputed:
            raise CoverageIntegrityError(
                "E_RUNTIME",
                "downstream value was rewritten relative to G(upper+1)-G(lower)",
            )
    chain = result.get("chain")
    if isinstance(chain, list):
        for step in chain:
            if not isinstance(step, dict):
                continue
            if step.get("step") == "combine_with_infrastructure_telescoping" and "valueEnteredLaterSteps" in step:
                if _fraction_from_payload(step.get("valueEnteredLaterSteps")) != recomputed:
                    raise CoverageIntegrityError(
                        "E_RUNTIME",
                        "chain valueEnteredLaterSteps was rewritten relative to G(upper+1)-G(lower)",
                    )
    return {
        "ok": True,
        "formula": "G(upper + 1) - G(lower)",
        "recomputed": fraction_payload(recomputed),
        "matchesRecordedValue": True,
        "currentGBoundToCheckedIdentity": True,
        "combinationRuleId": TELESCOPING_RULE_ID,
        "combinationRuleOrigin": TELESCOPING_RULE_ORIGIN,
        "agentExtracted": False,
    }


def verify_coverage_honesty(
    coverage: dict[str, Any],
    *,
    result: dict[str, Any] | None = None,
) -> None:
    honesty = coverage.get("honesty") if isinstance(coverage.get("honesty"), dict) else {}
    evidence = coverage.get("evidenceScope") if isinstance(coverage.get("evidenceScope"), dict) else {}
    claim = coverage.get("claimCoverage") if isinstance(coverage.get("claimCoverage"), dict) else {}
    if coverage.get("kind") != COVERAGE_KIND:
        raise CoverageIntegrityError("E_INPUT", "coverage kind is not the polynomial-finite-sum coverage record")
    if honesty.get("formalKernelChecked") is not False or evidence.get("formalKernelChecked") is not False:
        raise CoverageIntegrityError("E_INPUT", "coverage must not mark formal_kernel_checked")
    if result is not None and result.get("formalKernelChecked") is True:
        raise CoverageIntegrityError("E_INPUT", "result forges formal_kernel_checked")
    if claim.get("coversOriginalTaskClaim") is not False:
        raise CoverageIntegrityError(
            "E_INPUT",
            "coverage must not claim that submitted obligations cover the original task",
        )
    if honesty.get("obligationSuccessIsNotClaimCoverage") is not True:
        raise CoverageIntegrityError("E_INPUT", "coverage must keep obligation success distinct from claim coverage")
    if honesty.get("hashBindsContentNotAuthorshipOrTruth") is not True:
        raise CoverageIntegrityError("E_INPUT", "coverage must not treat hash binding as authorship or truth")
    if honesty.get("telescopingIsHandProvidedInfrastructure") is not True:
        raise CoverageIntegrityError("E_INPUT", "telescoping must remain hand-provided infrastructure")
    outcome = coverage.get("outcome") if isinstance(coverage.get("outcome"), dict) else {}
    if outcome.get("unsupportedTreatedAsCounterexample") is True:
        raise CoverageIntegrityError("E_INPUT", "unsupported must not be treated as a counterexample")
    if outcome.get("status") in {"unsupported", "inapplicable"} and outcome.get("propositionFalsified") is True:
        raise CoverageIntegrityError("E_INPUT", "unsupported/inapplicable must not be recorded as a falsified proposition")
    if claim.get("procedureEstablishedFiniteSumValue") is True:
        identity_status = evidence.get("identityStatus")
        if identity_status != "checked":
            raise CoverageIntegrityError(
                "E_INPUT",
                "finite-sum value cannot be established without a checked difference identity",
            )
        generated = coverage.get("generatedObligations") or []
        if not generated:
            raise CoverageIntegrityError("E_INPUT", "finite-sum value cannot be established with no generated obligation")
        bounds_step = _step(coverage, "integer-bounds-convention")
        combine_step = _step(coverage, "telescoping-combination")
        if bounds_step.get("executed") is not True or combine_step.get("executed") is not True:
            raise CoverageIntegrityError(
                "E_INPUT",
                "finite-sum value cannot be established if the bound step or combination rule was deleted",
            )
        kernel_step = _step(coverage, "whole-finite-sum-kernel")
        if kernel_step.get("coverage") != "uncovered" or kernel_step.get("formalKernelChecked") is not False:
            raise CoverageIntegrityError("E_INPUT", "kernel step must stay uncovered")
        binding = coverage.get("typedBinding") if isinstance(coverage.get("typedBinding"), dict) else {}
        if binding.get("status") != "bound":
            raise CoverageIntegrityError("E_INPUT", "established finite-sum value must carry a typed binding")
        if binding.get("currentGBoundToCheckedIdentity") is not True:
            raise CoverageIntegrityError(
                "E_INPUT",
                "established finite-sum value must bind current G to the checked identity",
            )
        if result is not None and result.get("status") == "ok":
            verify_typed_binding(result, task=coverage.get("taskClaim"))
    nl_step = _step(coverage, "nl-to-structured-claim")
    if nl_step.get("coverage") != "uncovered":
        raise CoverageIntegrityError("E_INPUT", "NL→claim must remain uncovered")
    binomial = _step(coverage, "binomial-rewrite")
    if binomial.get("coverage") not in {"uncovered-conditional-premise", "uncovered"}:
        raise CoverageIntegrityError("E_INPUT", "binomial rewrite must not be marked covered")
    telescoping = _step(coverage, "telescoping-combination")
    if telescoping.get("agentExtracted") is True:
        raise CoverageIntegrityError("E_INPUT", "telescoping must not be counted as Agent-extracted")
    if telescoping.get("coverage") != "hand-provided-infrastructure":
        raise CoverageIntegrityError("E_INPUT", "telescoping must remain infrastructure, not an obligation")


def load_frozen_workflow_coverage() -> dict[str, Any]:
    return json.loads(FROZEN_WORKFLOW_PATH.read_text(encoding="utf-8"))


def _honesty_flags() -> dict[str, Any]:
    return {
        "obligationSuccessIsNotClaimCoverage": True,
        "hashBindsContentNotAuthorshipOrTruth": True,
        "formalKernelChecked": False,
        "telescopingIsHandProvidedInfrastructure": True,
        "instancesAreNotUniversalProof": True,
        "unsupportedIsNotACounterexample": True,
        "structureValidationIsNotMathematicalCorrectness": True,
        "packJsonIsNotAnInterpreter": True,
    }


def _render_sum_claim(view: dict[str, Any]) -> str:
    variable = view.get("variable") or "k"
    lower = view.get("lower")
    upper = view.get("upper")
    summand = view.get("summand") or "?"
    return f"sum_{{{variable}={lower}}}^{{{upper}}} ({summand})"


def _task_view(task: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Original task identity is immutable. Result metadata may fill gaps only."""

    task = task if isinstance(task, dict) else {}
    result = result if isinstance(result, dict) else {}
    params = result.get("params") if isinstance(result.get("params"), dict) else {}
    observed = {
        "summand": result.get("summand") if result.get("summand") is not None else params.get("summand"),
        "variable": result.get("variable") if result.get("variable") is not None else params.get("variable"),
        "lower": result.get("lower") if result.get("lower") is not None else params.get("lower"),
        "upper": result.get("upper") if result.get("upper") is not None else params.get("upper"),
    }
    variable_hint = task.get("variable") or observed.get("variable") or "k"
    if not isinstance(variable_hint, str) or not variable_hint.strip():
        variable_hint = "k"
    merged: dict[str, Any] = {}
    for name in ("summand", "variable", "lower", "upper"):
        original = task.get(name)
        other = observed.get(name)
        if original is not None and other is not None:
            conflict = (
                not _same_summand(original, other, variable_hint)
                if name == "summand"
                else original != other
            )
            if conflict:
                raise CoverageIntegrityError(
                    "E_INPUT",
                    f"original task {name} conflicts with the result; refusing silent override",
                )
        merged[name] = original if original is not None else other
    premises = result.get("conditionalPremises")
    if not isinstance(premises, list):
        premises = task.get("premises") if isinstance(task.get("premises"), list) else []
    return {
        "summand": merged.get("summand"),
        "variable": merged.get("variable") or "k",
        "lower": merged.get("lower"),
        "upper": merged.get("upper"),
        "taskId": task.get("taskId") or params.get("taskId"),
        "premises": premises,
        "antidifference": result.get("antidifference") or task.get("antidifference"),
    }


def _same_summand(left: object, right: object, variable: str) -> bool:
    if not isinstance(left, str) or not isinstance(right, str):
        return left == right
    if normalize_expression_source(left) == normalize_expression_source(right):
        return True
    try:
        return parse_summand(left, variable)[1] == parse_summand(right, variable)[1]
    except CalculatorError:
        return False


def _infer_source(result: dict[str, Any]) -> str:
    kind = result.get("kind")
    if kind == "math-anchor.research.experimental-method-pack-application.v0":
        return "method-pack-apply"
    if kind == "math-anchor.research.polynomial-finite-sum.v0":
        return "polynomial-finite-sum-runner"
    if kind == "sympy_summation_baseline":
        return "sympy-summation-baseline"
    if isinstance(kind, str) and kind:
        return kind
    return "unknown"


def _status(result: dict[str, Any], error: BaseException | None) -> str:
    if error is not None:
        details = getattr(error, "details", None) or {}
        if isinstance(details, dict) and details.get("applicability") == "rejected":
            return "inapplicable"
        code = getattr(error, "code", None)
        if code == "E_UNSUPPORTED":
            return "unsupported"
        if code == "E_DOMAIN":
            return "unsupported"
        return "error"
    status = result.get("status")
    if isinstance(status, str):
        if status == "error":
            code = _error_code(result, None)
            if code == "E_UNSUPPORTED":
                return "unsupported"
            if code == "E_DOMAIN" and "reversed" in str(result.get("error", {}).get("message", "")).lower():
                return "unsupported"
        return status
    return "unknown"


def _error_code(result: dict[str, Any], error: BaseException | None) -> str | None:
    if error is not None:
        return getattr(error, "code", None)
    payload = result.get("error")
    if isinstance(payload, dict) and isinstance(payload.get("code"), str):
        return payload["code"]
    return None


def _outcome_record(status: str, error: BaseException | None) -> dict[str, Any]:
    code = getattr(error, "code", None) if error is not None else None
    interpreted = interpret_outcome(status, code=code)
    interpreted["code"] = code
    return interpreted


def _generated_obligations(
    identity: dict[str, Any],
    receipt: dict[str, Any],
) -> list[dict[str, Any]]:
    entries = receipt.get("obligations") if isinstance(receipt.get("obligations"), list) else []
    generated: list[dict[str, Any]] = []
    if entries:
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            generated.append(
                {
                    "id": entry.get("id"),
                    "kind": entry.get("kind"),
                    "status": entry.get("status"),
                    "assuranceLevel": entry.get("assuranceLevel"),
                    "scope": entry.get("scope"),
                    "claimDigest": entry.get("claimDigest"),
                    "certificateDigest": (entry.get("detail") or {}).get("certificateDigest")
                    if isinstance(entry.get("detail"), dict)
                    else None,
                    "covers": "G(k+1)-G(k)=p(k) as rational polynomials with constant denominators",
                    "doesNotCover": list(IDENTITY_DOES_NOT_COVER),
                }
            )
        return generated
    if identity:
        generated.append(
            {
                "id": DIFFERENCE_IDENTITY_OBLIGATION_ID,
                "kind": DIFFERENCE_IDENTITY_KIND,
                "status": identity.get("status"),
                "assuranceLevel": identity.get("assuranceLevel"),
                "scope": identity.get("scope") or "polynomial_identity_over_rationals",
                "claimDigest": identity.get("claimDigest"),
                "certificateDigest": identity.get("certificateDigest"),
                "left": identity.get("left"),
                "right": identity.get("right"),
                "covers": "G(k+1)-G(k)=p(k) as rational polynomials with constant denominators",
                "doesNotCover": list(IDENTITY_DOES_NOT_COVER),
            }
        )
    return generated


def _instantiate_steps(
    view: dict[str, Any],
    result: dict[str, Any],
    generated: list[dict[str, Any]],
    status: str,
    error: BaseException | None,
) -> list[dict[str, Any]]:
    identity_status = None
    if generated:
        identity_status = generated[0].get("status")
    elif isinstance(result.get("identity"), dict):
        identity_status = result["identity"].get("status")
    if status in {"unsupported", "inapplicable", "error"}:
        domain_failed = True
    else:
        domain_failed = False
    bounds_ok = False
    lower, upper = view.get("lower"), view.get("upper")
    if type(lower) is int and type(upper) is int and not isinstance(lower, bool) and not isinstance(upper, bool):
        bounds_ok = upper >= lower - 1
    combination_ran = result.get("status") == "ok" and identity_status == "checked" and bounds_ok
    premises = view.get("premises") or []
    has_binomial_premise = any(
        isinstance(item, dict)
        and (
            "C(" in str(item.get("statement", ""))
            or "binomial" in str(item.get("id", "")).lower()
            or "C(" in str(item.get("id", ""))
        )
        for item in premises
    )
    instantiated: list[dict[str, Any]] = []
    for step in WORKFLOW_STEPS:
        item = dict(step)
        step_id = step["id"]
        if step_id == "nl-to-structured-claim":
            item["executed"] = False
            item["status"] = "uncovered"
        elif step_id == "parse-univariate-qq-polynomial":
            item["executed"] = status in {"ok", "falsified"} or (
                domain_failed and _error_code(result, error) == "E_UNSUPPORTED"
            )
            item["status"] = "ok" if status in {"ok", "falsified"} else status
        elif step_id == "integer-bounds-convention":
            item["executed"] = bounds_ok and status in {"ok", "falsified"}
            item["status"] = "ok" if bounds_ok and status in {"ok", "falsified"} else status
            item["deleted"] = False
        elif step_id == "construct-antidifference":
            item["executed"] = result.get("antidifference") is not None
            item["constructor"] = result.get("constructor")
        elif step_id == "difference-identity":
            item["executed"] = bool(generated)
            item["status"] = identity_status
            item["obligationId"] = DIFFERENCE_IDENTITY_OBLIGATION_ID
        elif step_id == "evaluate-endpoints":
            item["executed"] = isinstance(result.get("endpoints"), dict) and status == "ok"
        elif step_id == "telescoping-combination":
            item["executed"] = combination_ran
            item["agentExtracted"] = False
        elif step_id == "typed-binding-into-later-parameters":
            item["executed"] = combination_ran and isinstance(result.get("value"), dict)
        elif step_id == "binomial-rewrite":
            item["executed"] = False
            item["presentAsConditionalPremise"] = has_binomial_premise
            item["verifiedByPack"] = False
            item["status"] = "conditional" if has_binomial_premise else "not_applicable"
        elif step_id == "whole-finite-sum-kernel":
            item["executed"] = False
            item["formalKernelChecked"] = False
            item["status"] = "uncovered"
        elif step_id == "universal-quantification":
            item["executed"] = False
            item["status"] = "uncovered"
        instantiated.append(item)
    return instantiated


def _procedure_established(
    status: str,
    generated: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    result: dict[str, Any],
) -> bool:
    if status != "ok":
        return False
    if not generated or generated[0].get("status") != "checked":
        return False
    by_id = {step["id"]: step for step in steps}
    if by_id.get("integer-bounds-convention", {}).get("executed") is not True:
        return False
    if by_id.get("telescoping-combination", {}).get("executed") is not True:
        return False
    if by_id.get("whole-finite-sum-kernel", {}).get("formalKernelChecked") is True:
        return False
    return isinstance(result.get("value"), dict)


def _typed_binding(
    view: dict[str, Any],
    result: dict[str, Any],
    procedure_established: bool,
) -> dict[str, Any]:
    hash_binding = {
        "claimDigest": (result.get("identity") or {}).get("claimDigest")
        if isinstance(result.get("identity"), dict)
        else None,
        "certificateDigest": (result.get("identity") or {}).get("certificateDigest")
        if isinstance(result.get("identity"), dict)
        else None,
        "binds": "byte-identity of the polynomial_identity claim JSON and of the certificate content",
        "doesNotBind": [
            "authorship",
            "mathematical truth beyond the checker statement",
            "the finite-sum combination rule",
            "natural-language task wording",
            "universal quantification over the declared family",
        ],
    }
    if not procedure_established:
        return {
            "status": "not_bound",
            "formula": "G(upper + 1) - G(lower)",
            "reason": "finite-sum value was not established by the checked procedure",
            "hashBinding": hash_binding,
            "notAGeneralDataflowLanguage": True,
        }
    outputs = [{"path": "value", "role": "task-answer", "present": True, "value": result.get("value")}]
    downstream = result.get("downstream")
    if isinstance(downstream, dict):
        outputs.append(
            {
                "path": "downstream.value",
                "role": "later-parameter",
                "present": True,
                "entered": downstream.get("entered"),
                "ruleId": downstream.get("ruleId"),
                "value": downstream.get("value"),
            }
        )
    chain = result.get("chain")
    if isinstance(chain, list):
        for index, step in enumerate(chain):
            if isinstance(step, dict) and step.get("step") == "combine_with_infrastructure_telescoping":
                outputs.append(
                    {
                        "path": f"chain[{index}].valueEnteredLaterSteps",
                        "role": "later-parameter",
                        "present": "valueEnteredLaterSteps" in step,
                        "value": step.get("valueEnteredLaterSteps"),
                    }
                )
    recomputed = None
    try:
        verified = verify_typed_binding(result, task=view)
        recomputed = verified["recomputed"]
    except CoverageIntegrityError:
        raise
    return {
        "status": "bound",
        "name": "finite-sum-value",
        "formula": "G(upper + 1) - G(lower)",
        "type": {
            "kind": "exact_rational",
            "python": "fractions.Fraction",
            "payloadFields": ["exact", "numerator", "denominator"],
        },
        "producedBy": {
            "ruleId": TELESCOPING_RULE_ID,
            "origin": TELESCOPING_RULE_ORIGIN,
            "agentExtracted": False,
            "notAnObligation": True,
        },
        "inputs": {
            "G": result.get("antidifference"),
            "variable": view.get("variable"),
            "lower": view.get("lower"),
            "upper": view.get("upper"),
            "gAtUpperPlusOne": (result.get("endpoints") or {}).get("gAtUpperPlusOne"),
            "gAtLower": (result.get("endpoints") or {}).get("gAtLower"),
        },
        "outputs": outputs,
        "recomputed": recomputed,
        "hashBinding": hash_binding,
        "currentGBoundToCheckedIdentity": True,
        "notAGeneralDataflowLanguage": True,
    }


def _claim_coverage_reason(generated: list[dict[str, Any]]) -> str:
    if generated:
        return (
            "The only generated obligation is the difference identity. "
            "Natural-language translation, binomial rewrite, telescoping "
            "combination (infrastructure), and the kernel-checked conclusion "
            "are not covered by that obligation. Obligation success is not "
            "claim coverage."
        )
    return (
        "No difference-identity obligation was submitted: this result has "
        "neither an obligation receipt nor an identity object. "
        "Obligation success is not claim coverage."
    )


def _identity_side(result: dict[str, Any], identity: dict[str, Any], side: str) -> str | None:
    value = identity.get(side)
    if isinstance(value, str) and value.strip():
        return value
    receipt = result.get("obligationReceipt")
    if not isinstance(receipt, dict) or not isinstance(receipt.get("obligations"), list):
        return None
    for entry in receipt["obligations"]:
        if not isinstance(entry, dict):
            continue
        claim = entry.get("claim")
        if isinstance(claim, dict) and isinstance(claim.get(side), str) and claim[side].strip():
            return claim[side]
        detail = entry.get("detail")
        if isinstance(detail, dict) and isinstance(detail.get(side), str) and detail[side].strip():
            return detail[side]
    return None


def _identity_left(result: dict[str, Any], identity: dict[str, Any]) -> str | None:
    return _identity_side(result, identity, "left")


def _require_right_matches_original_summand(
    result: dict[str, Any],
    *,
    identity: dict[str, Any],
    summand: str,
    variable: str,
) -> None:
    identity_right = identity.get("right") if isinstance(identity.get("right"), str) else None
    receipt_right = None
    receipt = result.get("obligationReceipt")
    if isinstance(receipt, dict) and isinstance(receipt.get("obligations"), list):
        for entry in receipt["obligations"]:
            if not isinstance(entry, dict):
                continue
            claim = entry.get("claim")
            if isinstance(claim, dict) and isinstance(claim.get("right"), str) and claim["right"].strip():
                receipt_right = claim["right"]
                break
    if not identity_right:
        identity_right = _identity_side(result, identity, "right")
    if not isinstance(identity_right, str) or not identity_right.strip():
        raise CoverageIntegrityError(
            "E_INPUT",
            "typed binding requires identity.right for the original task summand",
        )
    if not _same_summand(summand, identity_right, variable):
        raise CoverageIntegrityError(
            "E_INPUT",
            "identity.right does not match the original task summand",
            {"taskSummand": summand, "identityRight": identity_right},
        )
    if isinstance(receipt_right, str) and not _same_summand(summand, receipt_right, variable):
        raise CoverageIntegrityError(
            "E_INPUT",
            "receipt claim.right does not match the original task summand",
            {"taskSummand": summand, "receiptRight": receipt_right},
        )
    if isinstance(receipt_right, str) and not _same_summand(identity_right, receipt_right, variable):
        raise CoverageIntegrityError(
            "E_INPUT",
            "identity.right disagrees with receipt claim.right",
            {"identityRight": identity_right, "receiptRight": receipt_right},
        )


def _require_current_g_bound_to_checked_identity(
    result: dict[str, Any],
    *,
    g_source: str,
    variable: str,
    identity: dict[str, Any],
) -> None:
    """Fail closed if current G is not the G named by the checked identity."""

    left = _identity_left(result, identity)
    if not isinstance(left, str) or not left.strip():
        raise CoverageIntegrityError(
            "E_INPUT",
            "typed binding requires a checked identity statement that mentions current G",
        )
    try:
        g_terms = parse_antidifference(g_source, variable)
    except DomainError as error:
        raise CoverageIntegrityError(error.code, error.message) from error
    canonical_g = polynomial_source(g_terms, variable)
    expected_left = (
        f"({polynomial_source(g_terms, variable, shifted=True)}) - ({canonical_g})"
    )
    left_norm = normalize_expression_source(left)
    expected_norm = normalize_expression_source(expected_left)
    mentions_current_g = f"({canonical_g})" in left or canonical_g in left
    if not mentions_current_g or left_norm != expected_norm:
        raise CoverageIntegrityError(
            "E_RUNTIME",
            "current G is inconsistent with the checked identity statement",
            {
                "antidifference": g_source,
                "canonicalG": canonical_g,
                "identityLeft": left,
                "expectedLeft": expected_left,
            },
        )


def _all_obligations_checked(generated: list[dict[str, Any]]) -> bool:
    return bool(generated) and all(entry.get("status") == "checked" for entry in generated)


def _identity_status_from_generated(generated: list[dict[str, Any]]) -> str | None:
    if not generated:
        return None
    return generated[0].get("status")


def _pack_info(result: dict[str, Any], pack: dict[str, Any] | None) -> dict[str, Any] | None:
    info: dict[str, Any] = {}
    method = result.get("methodPack")
    if isinstance(method, dict):
        info.update(
            {
                "id": method.get("id"),
                "version": method.get("version"),
                "statusAtApplication": method.get("statusAtApplication"),
                "novelty": method.get("novelty"),
            }
        )
    if pack is not None:
        info.setdefault("id", pack.get("id"))
        info.setdefault("version", pack.get("version"))
        info.setdefault("status", pack.get("status"))
        novelty = pack.get("novelty")
        if isinstance(novelty, dict):
            info.setdefault("novelty", novelty.get("status"))
        info["formalKernelChecked"] = False
    return info or None


def _step(coverage: dict[str, Any], step_id: str) -> dict[str, Any]:
    for step in coverage.get("steps") or []:
        if isinstance(step, dict) and step.get("id") == step_id:
            return step
    raise CoverageIntegrityError("E_INPUT", f"coverage is missing step {step_id}")


def _normalized_claim(claim: dict[str, Any]) -> dict[str, Any]:
    return {
        "left": normalize_expression_source(claim["left"]),
        "right": normalize_expression_source(claim["right"]),
        "variables": [name.strip() for name in claim["variables"]],
    }


def _fraction_from_payload(payload: object) -> Fraction:
    try:
        return rational_from_payload(payload)
    except DomainError as error:
        raise CoverageIntegrityError(error.code, error.message, error.details) from error


def _require_same_rational(label: str, container: object, key: str, expected: Fraction) -> None:
    if not isinstance(container, dict) or key not in container:
        raise CoverageIntegrityError("E_RUNTIME", f"{label} missing while verifying typed binding")
    if _fraction_from_payload(container.get(key)) != expected:
        raise CoverageIntegrityError("E_RUNTIME", f"{label} was rewritten relative to independent evaluation of G")
