"""Extract a candidate method pack from T1 artifacts, then verify declared scope.

Steps follow the A2 brief: propose from T1, dedup against existing libraries,
state domain and try negatives, generate checkable evidence. Only in-scope
verified candidates are marked executable. The held-out second task is not
run here and must not be baked into the pack as an answer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import sympy as sp
from sympy.concrete.gosper import gosper_sum

from math_anchor import __version__
from math_anchor.certificate_checker import CERTIFICATE_FORMAT, CHECKER_SYSTEM, CHECKER_VERSION
from math_anchor.errors import CalculatorError

from research.polynomial_finite_sum_proposal.polynomials import DomainError
from research.polynomial_finite_sum_proposal.runner import run_polynomial_finite_sum
from research.polynomial_finite_sum_proposal.telescoping import (
    TELESCOPING_RULE_ID,
    TELESCOPING_RULE_ORIGIN,
)

from .format import (
    DEFAULT_PACK_DIR,
    EXTRACTION_TASK_ID,
    HELD_OUT_SECOND_TASK_ID,
    LIFECYCLE_CANDIDATE,
    LIFECYCLE_VERIFIED,
    NOVELTY_KNOWN_ADAPTATION,
    PACK_ID,
    PACK_VERSION,
    REPO_ROOT,
    SCHEMA_VERSION,
)
from .loader import load_pack


IN_SCOPE_CASES = (
    {
        "id": "T1",
        "summand": "k^2",
        "variable": "k",
        "lower": 1,
        "upper": 10,
        "expected": "385",
    },
    {
        "id": "T3-empty",
        "summand": "k^2",
        "variable": "k",
        "lower": 5,
        "upper": 4,
        "expected": "0",
    },
    {
        "id": "T4-rational",
        "summand": "(2*k + 1)/3",
        "variable": "k",
        "lower": 0,
        "upper": 2,
        "expected": "3",
    },
)

NEGATIVE_CASES = (
    {
        "id": "N3-harmonic",
        "summand": "1/k",
        "variable": "k",
        "lower": 1,
        "upper": 3,
        "expectCode": "E_UNSUPPORTED",
    },
    {
        "id": "N3-special-function",
        "summand": "sin(k)",
        "variable": "k",
        "lower": 1,
        "upper": 3,
        "expectCode": "E_UNSUPPORTED",
    },
    {
        "id": "N2-reversed-bounds",
        "summand": "k^2",
        "variable": "k",
        "lower": 5,
        "upper": 1,
        "expectCode": "E_DOMAIN",
    },
)


class ExtractionError(CalculatorError):
    """T1 extraction or in-scope verification failed."""


def extract_from_t1(*, output_dir: Path | None = None) -> dict[str, Any]:
    if any(case["id"] == HELD_OUT_SECOND_TASK_ID or "k^3" in case["summand"] for case in IN_SCOPE_CASES):
        raise ExtractionError("E_RUNTIME", "held-out second task leaked into in-scope extraction cases")

    t1_path = (
        REPO_ROOT
        / "research"
        / "polynomial_finite_sum_proposal"
        / "examples"
        / "sum-k-squared-1-to-10.json"
    )
    t1_task = json.loads(t1_path.read_text(encoding="utf-8"))
    t1 = run_polynomial_finite_sum(
        summand=str(t1_task["summand"]),
        variable=str(t1_task.get("variable", "k")),
        lower=t1_task["lower"],
        upper=t1_task["upper"],
    )
    if t1.get("status") != "ok" or t1["value"]["exact"] != "385":
        raise ExtractionError("E_RUNTIME", "T1 source artifact did not replay as a checked sum of squares")

    candidate = _propose_candidate(t1)
    dedup = _dedup()
    negatives = _run_negatives()
    in_scope = _run_in_scope()
    falsified = _wrong_antidifference()

    lifecycle = {
        "states": [LIFECYCLE_CANDIDATE, LIFECYCLE_VERIFIED, "cross-task-use-evidence"],
        "candidate": {
            "status": LIFECYCLE_CANDIDATE,
            "from": EXTRACTION_TASK_ID,
            "proposed": candidate["proposedRule"],
        },
        "verifiedInDeclaredScope": {
            "status": LIFECYCLE_VERIFIED if in_scope["allPassed"] and negatives["allRejected"] else LIFECYCLE_CANDIDATE,
            "inScopeCases": [case["id"] for case in IN_SCOPE_CASES],
            "heldOutSecondTaskId": HELD_OUT_SECOND_TASK_ID,
            "heldOutNotRun": True,
        },
        "crossTaskUseEvidence": {
            "status": "not_recorded_by_extraction",
            "note": "apply the frozen pack to a held-out task; do not carry T1's G or 385",
        },
    }
    if lifecycle["verifiedInDeclaredScope"]["status"] != LIFECYCLE_VERIFIED:
        raise ExtractionError("E_RUNTIME", "in-scope verification or negatives failed; pack stays candidate")

    evidence = {
        "schemaVersion": SCHEMA_VERSION,
        "packId": PACK_ID,
        "packVersion": PACK_VERSION,
        "t1SourceArtifact": _compact_t1(t1, t1_path),
        "candidate": candidate,
        "dedup": dedup,
        "domainAndNegatives": negatives,
        "inScopeVerification": in_scope,
        "falsifiedWrongAntidifference": falsified,
        "lifecycle": lifecycle,
        "runtime": {"name": "math-anchor", "version": __version__, "sympy": sp.__version__},
    }

    target = Path(output_dir) if output_dir is not None else DEFAULT_PACK_DIR / "evidence"
    target.mkdir(parents=True, exist_ok=True)
    _write_json(target / "t1_source_artifact.json", evidence["t1SourceArtifact"])
    _write_json(target / "candidate.json", candidate)
    _write_json(target / "dedup.json", dedup)
    _write_json(target / "domain_and_negatives.json", negatives)
    _write_json(target / "in_scope_verification.json", in_scope)
    _write_json(target / "lifecycle.json", lifecycle)
    _write_json(target / "extraction_bundle.json", evidence)

    frozen = load_pack(DEFAULT_PACK_DIR / "pack.json")
    _assert_frozen_pack_matches_extraction(frozen, evidence)
    evidence["frozenPackConsistent"] = True
    _write_json(target / "extraction_bundle.json", evidence)
    return evidence


def _propose_candidate(t1: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": PACK_ID,
        "extractionTaskId": EXTRACTION_TASK_ID,
        "proposedRule": (
            "From a univariate QQ-polynomial summand p(k), construct an antidifference "
            "G via SymPy Gosper (summation fallback), independently check "
            "G(k+1)-G(k)=p(k) as a polynomial identity, then combine integer endpoints "
            "with the hand-provided telescoping infrastructure rule."
        ),
        "observedFromT1": {
            "summand": t1["summand"],
            "constructor": t1["constructor"],
            "antidifference": t1["antidifference"],
            "identityStatus": t1["identity"]["status"],
            "value": t1["value"],
        },
        "notExtracted": {
            "id": TELESCOPING_RULE_ID,
            "origin": TELESCOPING_RULE_ORIGIN,
            "agentExtracted": False,
            "reason": "hand-provided combination rule is A1 infrastructure, not A2 novelty",
        },
        "novelty": {
            "status": NOVELTY_KNOWN_ADAPTATION,
            "autoClaimed": False,
            "note": (
                "Gosper, Faulhaber for p(k)=k^m, SymPy gosper_sum/summation, and the "
                "Math Anchor polynomial certificate checker already exist. This pack "
                "adapts them into a reusable experimental interface."
            ),
        },
        "hiddenModelReasoning": False,
    }


def _dedup() -> dict[str, Any]:
    k = sp.symbols("k")
    gosper_k2 = gosper_sum(k**2, k)
    gosper_exists = gosper_k2 is not None
    summation_k2 = sp.summation(k**2, (k, 1, 10))
    return {
        "libraries": [
            {
                "name": "sympy.concrete.gosper.gosper_sum",
                "version": sp.__version__,
                "present": gosper_exists,
                "sample": str(gosper_k2),
                "decision": "reuse-for-construction-do-not-reimplement",
            },
            {
                "name": "sympy.summation",
                "version": sp.__version__,
                "sample": str(summation_k2),
                "decision": "baseline-value-only-not-a-certificate",
            },
            {
                "name": "math_anchor.certificate_checker",
                "format": CERTIFICATE_FORMAT,
                "system": CHECKER_SYSTEM,
                "version": CHECKER_VERSION,
                "decision": "reuse-for-independent-identity-check",
            },
            {
                "name": "Faulhaber formula for sum k^m",
                "decision": "classical-closed-forms-not-claimed-as-new",
            },
            {
                "name": TELESCOPING_RULE_ID,
                "origin": TELESCOPING_RULE_ORIGIN,
                "decision": "infrastructure-not-agent-extracted",
            },
        ],
        "noveltyStatus": NOVELTY_KNOWN_ADAPTATION,
        "newMathematicsClaimed": False,
        "layerValueIfAny": (
            "checked evidence pipeline and a retrieve/instantiate interface; "
            "SymPy already computes the number"
        ),
    }


def _run_negatives() -> dict[str, Any]:
    results = []
    for case in NEGATIVE_CASES:
        try:
            outcome = run_polynomial_finite_sum(
                summand=case["summand"],
                variable=case["variable"],
                lower=case["lower"],
                upper=case["upper"],
                compare_baseline=False,
            )
            results.append(
                {
                    **case,
                    "happened": "unexpected_success",
                    "status": outcome.get("status"),
                    "passed": False,
                }
            )
        except DomainError as error:
            results.append(
                {
                    **case,
                    "happened": "rejected",
                    "code": error.code,
                    "message": error.message,
                    "passed": error.code == case["expectCode"],
                }
            )
    return {
        "note": (
            "Numerical or domain rejection can refute a too-wide claim. It does not "
            "prove the pack for every in-scope polynomial."
        ),
        "cases": results,
        "allRejected": all(item.get("happened") == "rejected" and item.get("passed") for item in results),
    }


def _run_in_scope() -> dict[str, Any]:
    results = []
    for case in IN_SCOPE_CASES:
        outcome = run_polynomial_finite_sum(
            summand=case["summand"],
            variable=case["variable"],
            lower=case["lower"],
            upper=case["upper"],
        )
        passed = (
            outcome.get("status") == "ok"
            and outcome["value"]["exact"] == case["expected"]
            and outcome["identity"]["status"] == "checked"
            and outcome["formalKernelChecked"] is False
        )
        results.append(
            {
                "id": case["id"],
                "summand": case["summand"],
                "lower": case["lower"],
                "upper": case["upper"],
                "expected": case["expected"],
                "got": None if outcome.get("status") != "ok" else outcome["value"]["exact"],
                "identity": outcome.get("identity", {}).get("status"),
                "passed": passed,
            }
        )
    return {
        "cases": results,
        "allPassed": all(item["passed"] for item in results),
        "heldOutSecondTaskId": HELD_OUT_SECOND_TASK_ID,
        "heldOutExcluded": True,
        "notAUniversalProof": True,
    }


def _wrong_antidifference() -> dict[str, Any]:
    outcome = run_polynomial_finite_sum(
        summand="k^2",
        lower=1,
        upper=10,
        antidifference="k^3 / 3",
        compare_baseline=False,
    )
    return {
        "id": "N1-wrong-antidifference",
        "status": outcome.get("status"),
        "passed": outcome.get("status") == "falsified" and "value" not in outcome,
        "note": "falsified identity does not yield a sum and does not enter the executable library as verified",
    }


def _compact_t1(t1: dict[str, Any], path: Path) -> dict[str, Any]:
    identity = t1["identity"]
    return {
        "extractionTaskId": EXTRACTION_TASK_ID,
        "taskPath": str(path.relative_to(REPO_ROOT)),
        "summand": t1["summand"],
        "variable": t1["variable"],
        "lower": t1["lower"],
        "upper": t1["upper"],
        "constructor": t1["constructor"],
        "antidifference": t1["antidifference"],
        "value": t1["value"],
        "identity": {
            "status": identity["status"],
            "assuranceLevel": identity["assuranceLevel"],
            "certificateDigest": identity.get("certificateDigest"),
            "checker": identity.get("checker"),
            "claimDigest": identity.get("claimDigest"),
        },
        "formalKernelChecked": False,
        "combinationRule": t1["combinationRule"]["id"],
        "combinationRuleAgentExtracted": t1["combinationRule"]["agentExtracted"],
    }


def _assert_frozen_pack_matches_extraction(pack: dict[str, Any], evidence: dict[str, Any]) -> None:
    if pack["id"] != PACK_ID or pack["schemaVersion"] != SCHEMA_VERSION:
        raise ExtractionError("E_INPUT", "frozen pack id/schema drifted from extraction constants")
    if pack["status"] != LIFECYCLE_VERIFIED:
        raise ExtractionError("E_INPUT", "frozen pack must be verified-in-declared-scope after extraction")
    if pack["novelty"]["status"] != NOVELTY_KNOWN_ADAPTATION:
        raise ExtractionError("E_INPUT", "frozen pack novelty label is not the honest extraction label")
    if pack["provenance"]["extractionTaskId"] != EXTRACTION_TASK_ID:
        raise ExtractionError("E_INPUT", "frozen pack provenance is not T1")
    if pack["verification"]["formalKernelChecked"] is not False:
        raise ExtractionError("E_INPUT", "frozen pack incorrectly marks formal_kernel_checked")
    if not evidence["inScopeVerification"]["allPassed"]:
        raise ExtractionError("E_RUNTIME", "in-scope verification failed")
    if not evidence["domainAndNegatives"]["allRejected"]:
        raise ExtractionError("E_RUNTIME", "negative domain cases did not all reject")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
