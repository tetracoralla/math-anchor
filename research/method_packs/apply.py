"""Retrieve an experimental method pack and instantiate it on a new task.

The pack JSON is declarative. It does not eval pack text or import caller
code. Gosper packs still reuse the A1 polynomial finite-sum procedure
(construction via gosper_sum / construct_antidifference). The shifted-square
pack (PARAM_PACK_ID) instantiates the saved parametric G and must not
reconstruct; reconstruction is disabled on that path. The hand-provided
telescoping combination rule remains infrastructure, not pack novelty.
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

from research.polynomial_finite_sum_proposal.polynomials import DomainError, parse_summand
from research.polynomial_finite_sum_proposal.runner import run_polynomial_finite_sum
from research.polynomial_finite_sum_proposal.telescoping import (
    TELESCOPING_RULE_ID,
    TELESCOPING_RULE_ORIGIN,
    rule_metadata,
)

from .format import (
    APPLICATION_KIND,
    LIFECYCLE_CROSS_TASK,
    PACK_ID,
    PACK_VERSION,
    PARAM_PACK_ID,
    PARAM_PACK_VERSION,
)
from .loader import load_pack, require_executable, validate_pack


class PackApplicationError(CalculatorError):
    """Applicability or instantiation failure for an experimental method pack."""


_TASK_FIELDS = {
    "summand",
    "variable",
    "lower",
    "upper",
    "antidifference",
    "compareBaseline",
    "taskId",
    "premises",
    "notes",
}


def apply_method_pack(
    task: dict[str, Any],
    *,
    pack: dict[str, Any] | None = None,
    pack_path: object | None = None,
    compare_baseline: bool = True,
    include_backend_receipt: bool = False,
    require_pack_version: str | None = PACK_VERSION,
) -> dict[str, Any]:
    if pack is not None:
        if not isinstance(pack, dict):
            raise PackApplicationError("E_INPUT", "pack must be a JSON object")
        validate_pack(pack)
        loaded = pack
    else:
        loaded = load_pack(pack_path)
    require_executable(loaded)
    if loaded.get("id") == PARAM_PACK_ID:
        from .shifted_square_apply import apply_shifted_square_pack

        required = require_pack_version
        if required in (None, PACK_VERSION):
            required = PARAM_PACK_VERSION
        return apply_shifted_square_pack(
            task,
            pack=loaded,
            compare_baseline=compare_baseline,
            include_backend_receipt=include_backend_receipt,
            require_pack_version=required,
        )
    _require_pack_version(loaded, require_pack_version)
    parsed = _parse_task(task)
    premises = _conditional_premises(parsed["premises"])
    try:
        backend = run_polynomial_finite_sum(
            summand=parsed["summand"],
            variable=parsed["variable"],
            lower=parsed["lower"],
            upper=parsed["upper"],
            antidifference=parsed["antidifference"],
            compare_baseline=parsed["compareBaseline"]
            if parsed["compareBaseline"] is not None
            else compare_baseline,
        )
    except DomainError as error:
        details: dict[str, Any] = {"methodPackId": loaded["id"]}
        if error.code == "E_RUNTIME":
            details.update(
                {
                    "reason": "runtime_inconsistency",
                    "phase": "execution",
                }
            )
        else:
            details.update(
                {
                    "applicability": "rejected",
                    "reason": "input_outside_declared_pack_domain",
                    "unsupportedInputs": loaded["mathSemantics"]["unsupportedInputs"],
                    "phase": "input",
                }
            )
        raise PackApplicationError(error.code, error.message, details) from error

    chain = _chain(loaded, parsed, backend)
    verification = _verification_record(loaded, backend)
    adoption = _adoption_record(loaded, parsed, backend, premises)
    result: dict[str, Any] = {
        "status": backend["status"],
        "kind": APPLICATION_KIND,
        "runtime": {"name": "math-anchor", "version": __version__},
        "methodPack": {
            "id": loaded["id"],
            "version": loaded["version"],
            "statusAtApplication": loaded["status"],
            "novelty": loaded["novelty"]["status"],
            "publicPromotion": False,
            "path": loaded.get("_packPath"),
        },
        "params": {
            "summand": parsed["summand"],
            "variable": parsed["variable"],
            "lower": parsed["lower"],
            "upper": parsed["upper"],
            "taskId": parsed["taskId"],
            "antidifferenceSupplied": parsed["antidifference"] is not None,
        },
        "verification": verification,
        "conditionalPremises": premises,
        "chain": chain,
        "adoption": adoption,
        "formalKernelChecked": False,
        "infrastructureTelescoping": rule_metadata(),
        "limitations": [
            "experimental_method_pack_not_a_public_capability",
            "formal_kernel_not_used",
            "combination_rule_is_hand_provided_infrastructure",
            "unverified_premises_remain_conditional",
            "in_scope_instances_are_not_a_universal_proof",
        ],
    }
    if backend.get("status") == "ok":
        result["value"] = backend["value"]
        result["antidifference"] = backend["antidifference"]
        result["constructor"] = backend["constructor"]
        result["downstream"] = {
            "entered": "infrastructure_telescoping_combination",
            "ruleId": TELESCOPING_RULE_ID,
            "ruleOrigin": TELESCOPING_RULE_ORIGIN,
            "agentExtracted": False,
            "formula": "G(upper + 1) - G(lower)",
            "value": backend["value"],
        }
        if "baseline" in backend:
            result["baseline"] = backend["baseline"]
    else:
        result["reason"] = backend.get("reason", "difference_identity_not_checked")
        result["antidifference"] = backend.get("antidifference")
        result["constructor"] = backend.get("constructor")

    if include_backend_receipt:
        result["obligationReceipt"] = backend.get("obligationReceipt")
    elif backend.get("identity"):
        result["identity"] = {
            key: backend["identity"][key]
            for key in (
                "left",
                "right",
                "status",
                "assuranceLevel",
                "certificateDigest",
                "checker",
                "claimDigest",
            )
            if key in backend["identity"]
        }
    return result


def _require_pack_version(loaded: dict[str, Any], required: str | None) -> None:
    if required is None:
        return
    actual = loaded.get("version")
    if actual != required:
        raise PackApplicationError(
            "E_INPUT",
            (
                f"method-pack version {actual!r} is stale or unexpected; "
                f"required {required!r}"
            ),
            {
                "reason": "stale_or_unexpected_pack_version",
                "methodPackId": loaded.get("id"),
                "packVersion": actual,
                "requiredVersion": required,
                "phase": "input",
            },
        )


def _parse_task(task: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(task, dict):
        raise PackApplicationError("E_INPUT", "task must be a JSON object")
    unknown = set(task) - _TASK_FIELDS
    if unknown:
        raise PackApplicationError(
            "E_INPUT",
            f"unknown task fields: {', '.join(sorted(unknown))}",
        )
    for required in ("summand", "lower", "upper"):
        if required not in task:
            raise PackApplicationError("E_INPUT", f"task requires {required}")
    variable = task.get("variable", "k")
    if not isinstance(variable, str) or not variable:
        raise PackApplicationError("E_INPUT", "variable must be a non-empty string")
    summand = task["summand"]
    if not isinstance(summand, str) or not summand.strip():
        raise PackApplicationError("E_INPUT", "summand must be a non-empty string")
    compare = task.get("compareBaseline")
    if compare is not None and not isinstance(compare, bool):
        raise PackApplicationError("E_INPUT", "compareBaseline must be a boolean")
    antidifference = task.get("antidifference")
    if antidifference is not None and not isinstance(antidifference, str):
        raise PackApplicationError("E_INPUT", "antidifference must be a string when supplied")
    task_id = task.get("taskId")
    if task_id is not None and not isinstance(task_id, str):
        raise PackApplicationError("E_INPUT", "taskId must be a string")
    premises = task.get("premises", [])
    if premises is None:
        premises = []
    if not isinstance(premises, list):
        raise PackApplicationError("E_INPUT", "premises must be a list")
    notes = task.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise PackApplicationError("E_INPUT", "notes must be a string")
    return {
        "summand": summand,
        "variable": variable,
        "lower": task["lower"],
        "upper": task["upper"],
        "antidifference": antidifference,
        "compareBaseline": compare,
        "taskId": task_id,
        "premises": premises,
        "notes": notes,
    }


def _conditional_premises(premises: list[object]) -> list[dict[str, Any]]:
    recorded: list[dict[str, Any]] = []
    for index, premise in enumerate(premises):
        if not isinstance(premise, dict):
            raise PackApplicationError("E_INPUT", f"premises[{index}] must be an object")
        if premise.get("verifiedByPack") is True:
            raise PackApplicationError(
                "E_INPUT",
                "a premise may not claim verifiedByPack unless this pack checked it; "
                "unverified premises stay conditional",
            )
        statement = premise.get("statement")
        if not isinstance(statement, str) or not statement.strip():
            raise PackApplicationError("E_INPUT", f"premises[{index}] needs a statement")
        recorded.append(
            {
                "id": premise.get("id", f"premise-{index}"),
                "statement": statement,
                "verifiedByPack": False,
                "status": "conditional",
            }
        )
    return recorded


def _verification_record(pack: dict[str, Any], backend: dict[str, Any]) -> dict[str, Any]:
    identity = backend.get("identity") if isinstance(backend.get("identity"), dict) else {}
    checker = identity.get("checker") if isinstance(identity.get("checker"), dict) else {}
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
        "certificateDigest": identity.get("certificateDigest"),
        "claimDigest": identity.get("claimDigest"),
        "checker": identity.get("checker") or {"system": runtime_id, "version": runtime_version},
        "formalKernelChecked": False,
        "unverifiedPremisesStayConditional": True,
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
    backend: dict[str, Any],
) -> list[dict[str, Any]]:
    steps = [
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
                "lower": parsed["lower"],
                "upper": parsed["upper"],
            },
        },
        {
            "step": "instantiate",
            "rules": [rule["id"] for rule in pack["useInterface"]["instantiationRules"]],
            "untrustedCode": False,
            "sourceSolutionCarried": parsed["antidifference"] is not None,
        },
        {
            "step": "construct_antidifference",
            "constructor": backend.get("constructor"),
            "antidifference": backend.get("antidifference"),
        },
        {
            "step": "verify_difference_identity",
            "obligationKind": "polynomial_identity",
            "status": (backend.get("identity") or {}).get("status"),
            "assuranceLevel": (backend.get("identity") or {}).get("assuranceLevel"),
            "checker": (backend.get("identity") or {}).get("checker"),
            "certificateDigest": (backend.get("identity") or {}).get("certificateDigest"),
        },
    ]
    if backend.get("status") == "ok":
        steps.append(
            {
                "step": "combine_with_infrastructure_telescoping",
                "ruleId": TELESCOPING_RULE_ID,
                "ruleOrigin": TELESCOPING_RULE_ORIGIN,
                "agentExtracted": False,
                "formula": "G(upper + 1) - G(lower)",
                "valueEnteredLaterSteps": backend["value"],
            }
        )
    return steps


def _adoption_record(
    pack: dict[str, Any],
    parsed: dict[str, Any],
    backend: dict[str, Any],
    premises: list[dict[str, Any]],
) -> dict[str, Any]:
    used = backend.get("status") == "ok"
    same_task = _is_extraction_task(pack, parsed)
    return {
        "methodId": pack["id"],
        "methodVersion": pack["version"],
        "taskId": parsed["taskId"],
        "used": used,
        "lifecycleEvidence": LIFECYCLE_CROSS_TASK if used and not same_task else pack["status"],
        "semanticAdoptionRequires": [
            "retrieve_named_pack",
            "instantiate_declared_params",
            "independent_identity_check",
            "value_entered_later_step",
        ],
        "callAloneIsNotAdoption": True,
        "conditionalPremises": premises,
        "extractionTaskIdNotReusedAsAnswer": _extraction_task_id_not_reused(pack, parsed),
        "packId": PACK_ID,
    }


def _nonempty_task_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or type(value) is not int:
        return None
    return value


def _inputs_match_extraction_task(parsed: dict[str, Any]) -> bool:
    if _as_int(parsed["lower"]) != 1 or _as_int(parsed["upper"]) != 10:
        return False
    try:
        _source, terms, _expression = parse_summand(parsed["summand"], parsed["variable"])
    except CalculatorError:
        return False
    return terms == {2: Fraction(1)}


def _is_extraction_task(pack: dict[str, Any], parsed: dict[str, Any]) -> bool:
    task_id = _nonempty_task_id(parsed["taskId"])
    extraction_id = pack["provenance"]["extractionTaskId"]
    if task_id is not None and task_id == extraction_id:
        return True
    return _inputs_match_extraction_task(parsed)


def _extraction_task_id_not_reused(pack: dict[str, Any], parsed: dict[str, Any]) -> bool:
    task_id = _nonempty_task_id(parsed["taskId"])
    if task_id is None:
        return False
    if _inputs_match_extraction_task(parsed):
        return False
    return task_id != pack["provenance"]["extractionTaskId"]
