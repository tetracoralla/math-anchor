"""Apply the shifted-square parametric pack without reconstructing G.

Reconstruction (Gosper / undetermined coefficients / caller-supplied G) is
disabled on this path. The saved G(k,c) is instantiated, the difference
identity is checked independently, then the A1 telescoping rule is applied.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from math_anchor import __version__
from math_anchor.certificate_checker import (
    CERTIFICATE_FORMAT,
    CHECKER_SYSTEM,
    CHECKER_VERSION,
)
from math_anchor.errors import CalculatorError
from math_anchor.obligations import OBLIGATION_SET_SCHEMA_VERSION, check_obligation_set

from research.polynomial_finite_sum_proposal.baseline import sympy_finite_sum
from research.polynomial_finite_sum_proposal.polynomials import (
    difference_identity_sources,
    evaluate_univariate,
    fraction_payload,
    require_integer,
)
from research.polynomial_finite_sum_proposal.telescoping import (
    TELESCOPING_RULE_ID,
    TELESCOPING_RULE_ORIGIN,
    TelescopingRuleError,
    apply_finite_telescoping_sum,
    rule_metadata,
)

from .apply import PackApplicationError
from .format import (
    LIFECYCLE_CROSS_TASK,
    PARAM_APPLICATION_KIND,
    PARAM_EXTRACTION_TASK_ID,
    PARAM_PACK_ID,
    PARAM_PACK_VERSION,
)
from .loader import require_executable, validate_pack
from .shifted_square import (
    INDEX_VARIABLE,
    PARAMETER_VARIABLE,
    ShiftedSquareError,
    g_payload_from_pack,
    general_identity_sources,
    instance_summand_terms,
    instantiate_univariate,
    instantiated_g_source,
    match_shifted_square,
    parse_rational_parameter,
    summand_source_for_c,
)


_TASK_FIELDS = {
    "summand",
    "variable",
    "lower",
    "upper",
    "parameterC",
    "antidifference",
    "compareBaseline",
    "taskId",
    "premises",
    "notes",
}


def apply_shifted_square_pack(
    task: dict[str, Any],
    *,
    pack: dict[str, Any],
    compare_baseline: bool = True,
    include_backend_receipt: bool = False,
    require_pack_version: str = PARAM_PACK_VERSION,
) -> dict[str, Any]:
    if not isinstance(pack, dict):
        raise PackApplicationError("E_INPUT", "pack must be a JSON object")
    validate_pack(pack)
    require_executable(pack)
    if pack.get("id") != PARAM_PACK_ID:
        raise PackApplicationError(
            "E_INPUT",
            "shifted-square apply requires the parameterized shifted-square pack",
            {"reason": "wrong_pack_implementation_binding", "methodPackId": pack.get("id")},
        )
    actual_version = pack.get("version")
    if actual_version != require_pack_version:
        raise PackApplicationError(
            "E_INPUT",
            (
                f"method-pack version {actual_version!r} is stale or unexpected; "
                f"required {require_pack_version!r}"
            ),
            {
                "reason": "stale_or_unexpected_pack_version",
                "methodPackId": pack.get("id"),
                "packVersion": actual_version,
                "requiredVersion": require_pack_version,
                "phase": "input",
            },
        )

    parsed = _parse_task(task)
    try:
        payload = g_payload_from_pack(pack)
        g_terms = payload["terms"]
        general_sources = general_identity_sources(
            g_terms,
            index=INDEX_VARIABLE,
            parameter=PARAMETER_VARIABLE,
        )
        general_identity = _check_identity(
            general_sources["left"],
            general_sources["right"],
            [INDEX_VARIABLE, PARAMETER_VARIABLE],
            obligation_id="general-difference-identity",
        )
        if general_identity["status"] != "checked":
            return _falsified_result(
                pack,
                parsed,
                payload,
                general_identity=general_identity,
                instance_identity=None,
                reason="general_difference_identity_not_checked",
                include_backend_receipt=include_backend_receipt,
            )

        univariate = instantiate_univariate(g_terms, parsed["parameterC"])
        instance_sources = difference_identity_sources(
            univariate,
            instance_summand_terms(parsed["parameterC"]),
            parsed["variable"],
        )
        instance_identity = _check_identity(
            instance_sources["left"],
            instance_sources["right"],
            [parsed["variable"]],
            obligation_id="difference-identity",
        )
        if instance_identity["status"] != "checked":
            return _falsified_result(
                pack,
                parsed,
                payload,
                general_identity=general_identity,
                instance_identity=instance_identity,
                reason="instance_difference_identity_not_checked",
                include_backend_receipt=include_backend_receipt,
                antidifference=instance_sources["antidifference"],
            )

        g_source = instance_sources["antidifference"]
        g_at_upper_plus_one = evaluate_univariate(
            g_source, parsed["variable"], parsed["upper"] + 1
        )
        g_at_lower = evaluate_univariate(g_source, parsed["variable"], parsed["lower"])
        try:
            value = apply_finite_telescoping_sum(
                difference_identity_checked=True,
                lower=parsed["lower"],
                upper=parsed["upper"],
                g_at_upper_plus_one=g_at_upper_plus_one,
                g_at_lower=g_at_lower,
            )
        except TelescopingRuleError as error:
            raise PackApplicationError(error.code, error.message) from error
    except ShiftedSquareError as error:
        raise _application_from_shifted(error, pack) from error

    use_baseline = (
        parsed["compareBaseline"] if parsed["compareBaseline"] is not None else compare_baseline
    )

    chain = _chain(pack, parsed, payload, general_identity, instance_identity, value)
    result: dict[str, Any] = {
        "status": "ok",
        "kind": PARAM_APPLICATION_KIND,
        "runtime": {"name": "math-anchor", "version": __version__},
        "methodPack": {
            "id": pack["id"],
            "version": pack["version"],
            "statusAtApplication": pack["status"],
            "novelty": pack["novelty"]["status"],
            "publicPromotion": False,
            "path": pack.get("_packPath"),
        },
        "params": {
            "summand": parsed["summand"],
            "variable": parsed["variable"],
            "lower": parsed["lower"],
            "upper": parsed["upper"],
            "parameterC": str(parsed["parameterC"]),
            "parameterCNumerator": int(parsed["parameterC"].numerator),
            "parameterCDenominator": int(parsed["parameterC"].denominator),
            "taskId": parsed["taskId"],
            "reconstructionDisabled": True,
            "gosperCalled": False,
        },
        "reconstructionDisabled": True,
        "gosperCalled": False,
        "constructor": "instantiated-saved-parametric-antidifference",
        "antidifference": g_source,
        "parametricAntidifference": payload["source"],
        "identity": {
            "left": instance_sources["left"],
            "right": instance_sources["right"],
            "status": instance_identity["status"],
            "assuranceLevel": instance_identity["assuranceLevel"],
            "certificateDigest": instance_identity["detail"].get("certificateDigest"),
            "checker": instance_identity["detail"].get("checker"),
            "claimDigest": instance_identity.get("claimDigest"),
            "scope": instance_identity.get("scope"),
        },
        "generalIdentity": {
            "left": general_sources["left"],
            "right": general_sources["right"],
            "variables": [INDEX_VARIABLE, PARAMETER_VARIABLE],
            "status": general_identity["status"],
            "assuranceLevel": general_identity["assuranceLevel"],
            "certificateDigest": general_identity["detail"].get("certificateDigest"),
            "checker": general_identity["detail"].get("checker"),
            "note": (
                "General identity G(k+1,c)-G(k,c)=(k+c)^2 is checked on apply "
                "from the pack payload as a bivariate polynomial identity. "
                "The instance check after substituting this task's c is a "
                "separate program step, not a second general proof."
            ),
        },
        "verification": _verification_record(pack, instance_identity),
        "conditionalPremises": parsed["premises"],
        "chain": chain,
        "adoption": _adoption_record(pack, parsed, used=True),
        "formalKernelChecked": False,
        "infrastructureTelescoping": rule_metadata(),
        "value": fraction_payload(value),
        "formula": "G(upper + 1) - G(lower)",
        "downstream": {
            "entered": "infrastructure_telescoping_combination",
            "ruleId": TELESCOPING_RULE_ID,
            "ruleOrigin": TELESCOPING_RULE_ORIGIN,
            "agentExtracted": False,
            "formula": "G(upper + 1) - G(lower)",
            "value": fraction_payload(value),
        },
        "endpoints": {
            "gAtUpperPlusOne": fraction_payload(g_at_upper_plus_one),
            "gAtLower": fraction_payload(g_at_lower),
        },
        "limitations": [
            "experimental_method_pack_not_a_public_capability",
            "formal_kernel_not_used",
            "combination_rule_is_hand_provided_infrastructure",
            "family_is_only_sums_of_shifted_squares",
            "checked_general_identity_is_not_a_kernel_theorem",
            "instance_check_is_not_a_universal_proof",
        ],
    }
    if include_backend_receipt:
        result["obligationReceipt"] = instance_identity.get("receipt")
    if use_baseline:
        baseline = sympy_finite_sum(
            summand=parsed["summand"],
            variable=parsed["variable"],
            lower=parsed["lower"],
            upper=parsed["upper"],
        )
        result["baseline"] = {
            "engine": baseline["engine"],
            "value": baseline["value"],
            "agrees": baseline["value"] == result["value"],
            "note": (
                "Fair value baseline (SymPy summation). It may construct a closed "
                "form. The pack apply path did not."
            ),
        }
        if not result["baseline"]["agrees"]:
            raise PackApplicationError(
                "E_RUNTIME",
                "checked telescoping value disagrees with the SymPy summation baseline",
                {
                    "reason": "runtime_inconsistency",
                    "phase": "execution",
                    "methodPackId": pack["id"],
                },
            )
    return result


def _parse_task(task: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(task, dict):
        raise PackApplicationError("E_INPUT", "task must be a JSON object")
    unknown = set(task) - _TASK_FIELDS
    if unknown:
        raise PackApplicationError(
            "E_INPUT",
            f"unknown task fields: {', '.join(sorted(unknown))}",
        )
    if "antidifference" in task:
        raise PackApplicationError(
            "E_INPUT",
            "shifted-square apply instantiates the saved G; caller antidifference is rejected",
            {"reason": "reconstruction_disabled", "reconstructionDisabled": True},
        )
    variable = task.get("variable", INDEX_VARIABLE)
    if not isinstance(variable, str) or not variable:
        raise PackApplicationError("E_INPUT", "variable must be a non-empty string")
    if variable == PARAMETER_VARIABLE:
        raise PackApplicationError(
            "E_DOMAIN",
            "summation variable cannot be the reserved parameter name c",
            {"applicability": "rejected", "reason": "parameter_name_collision", "phase": "input"},
        )
    for required in ("lower", "upper"):
        if required not in task:
            raise PackApplicationError("E_INPUT", f"task requires {required}")
    try:
        lower = require_integer("lower", task["lower"])
        upper = require_integer("upper", task["upper"])
    except CalculatorError as error:
        raise PackApplicationError(
            error.code,
            error.message,
            {
                "applicability": "rejected",
                "reason": "input_outside_declared_pack_domain",
                "phase": "input",
                "methodPackId": PARAM_PACK_ID,
            },
        ) from error
    if upper < lower - 1:
        raise PackApplicationError(
            "E_DOMAIN",
            "reversed bounds with upper < lower - 1 are unsupported; "
            "empty sums are only the case upper == lower - 1",
            {
                "applicability": "rejected",
                "reason": "input_outside_declared_pack_domain",
                "phase": "input",
                "methodPackId": PARAM_PACK_ID,
            },
        )

    summand = task.get("summand")
    raw_c = task.get("parameterC")
    if summand is None and raw_c is None:
        raise PackApplicationError("E_INPUT", "task requires summand and/or parameterC")
    if summand is not None and (not isinstance(summand, str) or not summand.strip()):
        raise PackApplicationError("E_INPUT", "summand must be a non-empty string")

    try:
        matched: Fraction | None = None
        if summand is not None:
            matched = match_shifted_square(summand, variable)
        declared: Fraction | None = None
        if raw_c is not None:
            declared = parse_rational_parameter(raw_c)
        if matched is not None and declared is not None and matched != declared:
            raise ShiftedSquareError(
                "E_DOMAIN",
                "parameterC does not match the (k+c)^2 template implied by the summand",
                {
                    "reason": "parameter_summand_mismatch",
                    "parameterC": str(declared),
                    "impliedC": str(matched),
                },
            )
        parameter = declared if declared is not None else matched
        if parameter is None:
            raise ShiftedSquareError("E_INPUT", "task requires summand and/or parameterC")
        if summand is None:
            summand = summand_source_for_c(parameter, variable)
    except ShiftedSquareError as error:
        raise _application_from_shifted(error, {"id": PARAM_PACK_ID}) from error

    compare = task.get("compareBaseline")
    if compare is not None and not isinstance(compare, bool):
        raise PackApplicationError("E_INPUT", "compareBaseline must be a boolean")
    task_id = task.get("taskId")
    if task_id is not None and not isinstance(task_id, str):
        raise PackApplicationError("E_INPUT", "taskId must be a string")
    premises = task.get("premises", [])
    if premises is None:
        premises = []
    if not isinstance(premises, list):
        raise PackApplicationError("E_INPUT", "premises must be a list")
    if premises:
        raise PackApplicationError(
            "E_INPUT",
            "shifted-square pack does not accept unverified extra premises",
        )
    notes = task.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise PackApplicationError("E_INPUT", "notes must be a string")
    return {
        "summand": summand,
        "variable": variable,
        "lower": lower,
        "upper": upper,
        "parameterC": parameter,
        "compareBaseline": compare,
        "taskId": task_id,
        "premises": [],
        "notes": notes,
    }


def _check_identity(
    left: str,
    right: str,
    variables: list[str],
    *,
    obligation_id: str,
) -> dict[str, Any]:
    _feedback, receipt = check_obligation_set(
        {
            "schemaVersion": OBLIGATION_SET_SCHEMA_VERSION,
            "assumptionSets": [
                {
                    "id": "discrete-sum-domain",
                    "assumptions": [
                        "the summation index and shift parameter are commuting indeterminates over the rationals",
                        "the summation index ranges over integers",
                    ],
                }
            ],
            "obligations": [
                {
                    "id": obligation_id,
                    "kind": "polynomial_identity",
                    "claim": {"left": left, "right": right, "variables": variables},
                    "assumptionSet": "discrete-sum-domain",
                }
            ],
            "responseMode": "full",
        }
    )
    entry = dict(receipt["obligations"][0])
    entry["receipt"] = receipt
    return entry


def _verification_record(pack: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    checker = identity.get("detail", {}).get("checker")
    if not isinstance(checker, dict):
        checker = {}
    runtime_id = checker.get("system") or CHECKER_SYSTEM
    runtime_version = checker.get("version") or CHECKER_VERSION
    declared = pack.get("verification") if isinstance(pack.get("verification"), dict) else {}
    return {
        "obligationKind": "polynomial_identity",
        "checkerId": runtime_id,
        "checkerVersion": runtime_version,
        "certificateFormat": CERTIFICATE_FORMAT,
        "status": identity.get("status"),
        "assuranceLevel": identity.get("assuranceLevel"),
        "certificateDigest": identity.get("detail", {}).get("certificateDigest"),
        "claimDigest": identity.get("claimDigest"),
        "checker": checker or {"system": runtime_id, "version": runtime_version},
        "formalKernelChecked": False,
        "unverifiedPremisesStayConditional": True,
        "reconstructionDisabled": True,
        "declaredCheckerId": declared.get("checkerId"),
        "declaredCheckerVersion": declared.get("checkerVersion"),
        "declaredMatchesRuntime": (
            declared.get("checkerId") == runtime_id
            and declared.get("checkerVersion") == runtime_version
            and declared.get("certificateFormat") == CERTIFICATE_FORMAT
            and declared.get("obligationKind") == "polynomial_identity"
        ),
    }


def _chain(
    pack: dict[str, Any],
    parsed: dict[str, Any],
    payload: dict[str, Any],
    general_identity: dict[str, Any],
    instance_identity: dict[str, Any],
    value: Fraction,
) -> list[dict[str, Any]]:
    return [
        {
            "step": "retrieve",
            "methodId": pack["id"],
            "methodVersion": pack["version"],
            "status": pack["status"],
            "novelty": pack["novelty"]["status"],
        },
        {
            "step": "applicability",
            "result": "in_declared_domain",
            "params": {
                "summand": parsed["summand"],
                "variable": parsed["variable"],
                "parameterC": str(parsed["parameterC"]),
                "lower": parsed["lower"],
                "upper": parsed["upper"],
            },
            "family": "sum-(k+c)^2",
        },
        {
            "step": "instantiate",
            "rules": [rule["id"] for rule in pack["useInterface"]["instantiationRules"]],
            "untrustedCode": False,
            "sourceSolutionCarried": False,
            "reconstructionDisabled": True,
            "gosperCalled": False,
            "savedAntidifference": payload["source"],
            "instantiatedAntidifference": instantiated_g_source(
                payload["terms"], parsed["parameterC"], parsed["variable"]
            ),
        },
        {
            "step": "verify_general_difference_identity",
            "obligationKind": "polynomial_identity",
            "variables": [INDEX_VARIABLE, PARAMETER_VARIABLE],
            "status": general_identity.get("status"),
            "assuranceLevel": general_identity.get("assuranceLevel"),
            "certificateDigest": general_identity.get("detail", {}).get("certificateDigest"),
            "note": "bivariate identity in (k,c); not an instance-only check",
        },
        {
            "step": "verify_difference_identity",
            "obligationKind": "polynomial_identity",
            "status": instance_identity.get("status"),
            "assuranceLevel": instance_identity.get("assuranceLevel"),
            "checker": instance_identity.get("detail", {}).get("checker"),
            "certificateDigest": instance_identity.get("detail", {}).get("certificateDigest"),
            "note": "univariate instance after substituting this task's c",
        },
        {
            "step": "combine_with_infrastructure_telescoping",
            "ruleId": TELESCOPING_RULE_ID,
            "ruleOrigin": TELESCOPING_RULE_ORIGIN,
            "agentExtracted": False,
            "formula": "G(upper + 1) - G(lower)",
            "valueEnteredLaterSteps": fraction_payload(value),
        },
    ]


def _adoption_record(pack: dict[str, Any], parsed: dict[str, Any], *, used: bool) -> dict[str, Any]:
    same_task = _is_extraction_task(parsed)
    return {
        "methodId": pack["id"],
        "methodVersion": pack["version"],
        "taskId": parsed["taskId"],
        "used": used,
        "lifecycleEvidence": LIFECYCLE_CROSS_TASK if used and not same_task else pack["status"],
        "semanticAdoptionRequires": [
            "retrieve_named_pack",
            "instantiate_saved_parametric_antidifference",
            "independent_identity_check",
            "value_entered_later_step",
        ],
        "callAloneIsNotAdoption": True,
        "conditionalPremises": parsed["premises"],
        "extractionTaskIdNotReusedAsAnswer": _extraction_not_reused(parsed),
        "packId": PARAM_PACK_ID,
        "reconstructionDisabled": True,
        "gosperCalled": False,
    }


def _is_extraction_task(parsed: dict[str, Any]) -> bool:
    task_id = parsed["taskId"]
    if isinstance(task_id, str) and task_id.strip() == PARAM_EXTRACTION_TASK_ID:
        return True
    return (
        parsed["parameterC"] == Fraction(1)
        and parsed["lower"] == 0
        and parsed["upper"] == 4
        and parsed["variable"] == INDEX_VARIABLE
    )


def _extraction_not_reused(parsed: dict[str, Any]) -> bool:
    task_id = parsed["taskId"]
    if not isinstance(task_id, str) or not task_id.strip():
        return False
    if _is_extraction_task(parsed):
        return False
    return task_id != PARAM_EXTRACTION_TASK_ID


def _application_from_shifted(error: ShiftedSquareError, pack: dict[str, Any]) -> PackApplicationError:
    details = dict(error.details or {})
    details.setdefault("methodPackId", pack.get("id", PARAM_PACK_ID))
    details.setdefault("reconstructionDisabled", True)
    details.setdefault("gosperCalled", False)
    if error.code in {"E_UNSUPPORTED", "E_DOMAIN", "E_LIMIT"}:
        details.setdefault("applicability", "rejected")
        details.setdefault("reason", details.get("reason", "input_outside_declared_pack_domain"))
        details.setdefault("phase", "input")
    return PackApplicationError(error.code, error.message, details)


def _falsified_result(
    pack: dict[str, Any],
    parsed: dict[str, Any],
    payload: dict[str, Any],
    *,
    general_identity: dict[str, Any] | None,
    instance_identity: dict[str, Any] | None,
    reason: str,
    include_backend_receipt: bool,
    antidifference: str | None = None,
) -> dict[str, Any]:
    identity = instance_identity or general_identity or {}
    result: dict[str, Any] = {
        "status": identity.get("status", "falsified"),
        "kind": PARAM_APPLICATION_KIND,
        "reason": reason,
        "reconstructionDisabled": True,
        "gosperCalled": False,
        "constructor": "instantiated-saved-parametric-antidifference",
        "antidifference": antidifference or payload.get("source"),
        "methodPack": {
            "id": pack["id"],
            "version": pack["version"],
            "statusAtApplication": pack["status"],
            "novelty": pack["novelty"]["status"],
            "publicPromotion": False,
            "path": pack.get("_packPath"),
        },
        "params": {
            "summand": parsed["summand"],
            "variable": parsed["variable"],
            "lower": parsed["lower"],
            "upper": parsed["upper"],
            "parameterC": str(parsed["parameterC"]),
            "taskId": parsed["taskId"],
            "reconstructionDisabled": True,
            "gosperCalled": False,
        },
        "verification": _verification_record(pack, identity),
        "chain": [
            {"step": "retrieve", "methodId": pack["id"], "methodVersion": pack["version"]},
            {"step": "applicability", "result": "in_declared_domain"},
            {
                "step": "instantiate",
                "reconstructionDisabled": True,
                "gosperCalled": False,
            },
            {
                "step": "verify_general_difference_identity"
                if general_identity is not None and instance_identity is None
                else "verify_difference_identity",
                "status": identity.get("status"),
            },
        ],
        "adoption": _adoption_record(pack, parsed, used=False),
        "formalKernelChecked": False,
        "limitations": [
            "difference_identity_was_not_established",
            "formal_kernel_not_used",
            "reconstruction_disabled",
        ],
    }
    if include_backend_receipt and identity.get("receipt"):
        result["obligationReceipt"] = identity["receipt"]
    return result
