"""Extract the shifted-square parametric pack from one (c,a,b) instance.

Extraction may compare against B1 (Gosper allowed) as a fair baseline.
The frozen pack's apply path does not reconstruct G.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from math_anchor import __version__
from math_anchor.errors import CalculatorError

from research.polynomial_finite_sum_proposal.runner import run_polynomial_finite_sum
from research.polynomial_finite_sum_proposal.telescoping import (
    TELESCOPING_RULE_ID,
    TELESCOPING_RULE_ORIGIN,
)

from .format import (
    DEFAULT_PARAM_PACK_DIR,
    LIFECYCLE_CANDIDATE,
    LIFECYCLE_VERIFIED,
    NOVELTY_KNOWN_ADAPTATION,
    PARAM_EXTRACTION_TASK_ID,
    PARAM_HELD_OUT_TASK_ID,
    PARAM_PACK_ID,
    PARAM_PACK_VERSION,
    SCHEMA_VERSION,
)
from .loader import load_pack
from .shifted_square import (
    CANONICAL_G_SOURCE,
    canonical_g_terms,
    fraction_source,
    general_identity_sources,
    instantiate_univariate,
    monomial_antidifference,
)
from .shifted_square_apply import apply_shifted_square_pack


EXTRACTION_TASK = {
    "taskId": PARAM_EXTRACTION_TASK_ID,
    "summand": "(k+1)^2",
    "variable": "k",
    "parameterC": "1",
    "lower": 0,
    "upper": 4,
    "expected": "55",
}

IN_SCOPE_CASES = (
    EXTRACTION_TASK,
    {
        "id": "P0-empty",
        "summand": "(k+1)^2",
        "variable": "k",
        "parameterC": "1",
        "lower": 5,
        "upper": 4,
        "expected": "0",
    },
)

NEGATIVE_CASES = (
    {
        "id": "wrong-template-k-cubed",
        "summand": "k^3",
        "variable": "k",
        "lower": 1,
        "upper": 5,
        "expectCode": "E_UNSUPPORTED",
    },
    {
        "id": "wrong-template-not-perfect-square",
        "summand": "k^2 + 6*k + 8",
        "variable": "k",
        "lower": 1,
        "upper": 3,
        "expectCode": "E_UNSUPPORTED",
    },
    {
        "id": "harmonic",
        "summand": "1/k",
        "variable": "k",
        "lower": 1,
        "upper": 3,
        "expectCode": "E_UNSUPPORTED",
    },
    {
        "id": "reversed-bounds",
        "summand": "(k+1)^2",
        "variable": "k",
        "parameterC": "1",
        "lower": 5,
        "upper": 1,
        "expectCode": "E_DOMAIN",
    },
)


class ExtractionError(CalculatorError):
    """Shifted-square extraction or in-scope verification failed."""


def extract_shifted_square(*, output_dir: Path | None = None) -> dict[str, Any]:
    if any(
        case.get("taskId") == PARAM_HELD_OUT_TASK_ID or "k+3" in str(case.get("summand", ""))
        for case in IN_SCOPE_CASES
    ):
        raise ExtractionError("E_RUNTIME", "held-out shifted-square task leaked into extraction cases")

    derived = _derive_record()
    pack = load_pack(DEFAULT_PARAM_PACK_DIR / "pack.json")
    extraction_apply = apply_shifted_square_pack(
        {
            "taskId": EXTRACTION_TASK["taskId"],
            "summand": EXTRACTION_TASK["summand"],
            "variable": EXTRACTION_TASK["variable"],
            "parameterC": EXTRACTION_TASK["parameterC"],
            "lower": EXTRACTION_TASK["lower"],
            "upper": EXTRACTION_TASK["upper"],
        },
        pack=pack,
        compare_baseline=True,
    )
    if extraction_apply.get("status") != "ok" or extraction_apply["value"]["exact"] != EXTRACTION_TASK["expected"]:
        raise ExtractionError("E_RUNTIME", "extraction instance did not replay from the saved G")
    if extraction_apply.get("gosperCalled") is not False or extraction_apply.get("reconstructionDisabled") is not True:
        raise ExtractionError("E_RUNTIME", "extraction apply path reconstructed G")

    fair_b1 = run_polynomial_finite_sum(
        summand=EXTRACTION_TASK["summand"],
        variable=EXTRACTION_TASK["variable"],
        lower=EXTRACTION_TASK["lower"],
        upper=EXTRACTION_TASK["upper"],
        compare_baseline=False,
    )
    if fair_b1.get("status") != "ok" or fair_b1["value"]["exact"] != EXTRACTION_TASK["expected"]:
        raise ExtractionError("E_RUNTIME", "fair B1 baseline failed on the extraction instance")

    in_scope = _run_in_scope(pack)
    negatives = _run_negatives(pack)
    lifecycle = {
        "states": [LIFECYCLE_CANDIDATE, LIFECYCLE_VERIFIED, "cross-task-use-evidence"],
        "candidate": {
            "status": LIFECYCLE_CANDIDATE,
            "from": PARAM_EXTRACTION_TASK_ID,
            "proposed": derived["proposedRule"],
        },
        "verifiedInDeclaredScope": {
            "status": LIFECYCLE_VERIFIED if in_scope["allPassed"] and negatives["allRejected"] else LIFECYCLE_CANDIDATE,
            "inScopeCases": [EXTRACTION_TASK["taskId"], "P0-empty"],
            "heldOutSecondTaskId": PARAM_HELD_OUT_TASK_ID,
            "heldOutNotRun": True,
        },
        "crossTaskUseEvidence": {
            "status": "not_recorded_by_extraction",
            "note": "apply the frozen pack to a held-out (c,a,b); do not carry P0's numeric answer",
        },
    }
    if lifecycle["verifiedInDeclaredScope"]["status"] != LIFECYCLE_VERIFIED:
        raise ExtractionError("E_RUNTIME", "in-scope verification or negatives failed; pack stays candidate")

    evidence = {
        "schemaVersion": SCHEMA_VERSION,
        "packId": PARAM_PACK_ID,
        "packVersion": PARAM_PACK_VERSION,
        "extractionTask": {
            "taskId": PARAM_EXTRACTION_TASK_ID,
            "summand": EXTRACTION_TASK["summand"],
            "parameterC": EXTRACTION_TASK["parameterC"],
            "lower": EXTRACTION_TASK["lower"],
            "upper": EXTRACTION_TASK["upper"],
            "value": extraction_apply["value"],
            "constructor": extraction_apply["constructor"],
            "reconstructionDisabled": True,
            "gosperCalled": False,
            "generalIdentity": extraction_apply["generalIdentity"],
            "instanceIdentity": {
                "status": extraction_apply["identity"]["status"],
                "certificateDigest": extraction_apply["identity"].get("certificateDigest"),
            },
        },
        "candidate": derived,
        "fairB1Baseline": {
            "note": (
                "B1 may still construct via Gosper. This is a fair value comparison, "
                "not the pack apply path."
            ),
            "constructor": fair_b1["constructor"],
            "value": fair_b1["value"],
            "agreesWithPackApply": fair_b1["value"] == extraction_apply["value"],
        },
        "domainAndNegatives": negatives,
        "inScopeVerification": in_scope,
        "lifecycle": lifecycle,
        "runtime": {"name": "math-anchor", "version": __version__},
        "whatThePackAddsVersusB1": (
            "这个方法包相对不带包的 B1 流程，额外保存了参数化反差分 "
            "G(k,c)=k(k-1)(2k-1)/6 + c k(k-1) + c^2 k，以及可检查的二元恒等式 "
            "G(k+1,c)-G(k,c)=(k+c)^2。未来对未见过的有理数 c 与整数边界，"
            "apply 代入该 G 并做望远镜组合，不必再运行 Gosper / 待定系数构造。"
        ),
    }

    target = Path(output_dir) if output_dir is not None else DEFAULT_PARAM_PACK_DIR / "evidence"
    target.mkdir(parents=True, exist_ok=True)
    _write_json(target / "candidate.json", derived)
    _write_json(target / "domain_and_negatives.json", negatives)
    _write_json(target / "in_scope_verification.json", in_scope)
    _write_json(target / "lifecycle.json", lifecycle)
    _write_json(target / "extraction_bundle.json", evidence)

    _assert_frozen_pack_matches_extraction(pack, evidence)
    evidence["frozenPackConsistent"] = True
    _write_json(target / "extraction_bundle.json", evidence)
    return evidence


def _derive_record() -> dict[str, Any]:
    monomials = {
        "1": {str(power): fraction_source(coeff) for power, coeff in monomial_antidifference(0).items()},
        "k": {str(power): fraction_source(coeff) for power, coeff in monomial_antidifference(1).items()},
        "k^2": {str(power): fraction_source(coeff) for power, coeff in monomial_antidifference(2).items()},
    }
    terms = canonical_g_terms()
    sources = general_identity_sources(terms)
    instantiated = instantiate_univariate(terms, Fraction(1))
    return {
        "id": PARAM_PACK_ID,
        "extractionTaskId": PARAM_EXTRACTION_TASK_ID,
        "proposedRule": (
            "For p(k,c)=(k+c)^2, save the parametric antidifference G(k,c) obtained by "
            "undetermined coefficients on 1, k, k^2 and linearity. Later tasks instantiate "
            "that G at a rational c without reconstructing it."
        ),
        "derivation": {
            "method": "undetermined-coefficients-for-monomials-then-linearity",
            "notFromGosper": True,
            "monomialAntidifferences": monomials,
            "combination": "G(k,c) = G_{k^2}(k) + 2 c G_k(k) + c^2 G_1(k)",
            "canonicalSource": CANONICAL_G_SOURCE,
            "canonicalMatchesDerivation": True,
        },
        "generalIdentity": {
            "left": sources["left"],
            "right": sources["right"],
            "variables": ["k", "c"],
            "checkedOnApply": True,
            "note": (
                "The general bivariate identity is checked from the pack payload. "
                "A checked instance is not a kernel theorem and is not a proof for "
                "other templates."
            ),
        },
        "instantiationAtExtractionC": {
            "c": "1",
            "G": {str(power): fraction_source(coeff) for power, coeff in instantiated.items()},
        },
        "notExtracted": {
            "id": TELESCOPING_RULE_ID,
            "origin": TELESCOPING_RULE_ORIGIN,
            "agentExtracted": False,
            "reason": "hand-provided combination rule is A1 infrastructure, not pack novelty",
        },
        "novelty": {
            "status": NOVELTY_KNOWN_ADAPTATION,
            "autoClaimed": False,
            "note": (
                "Faulhaber's formula for sum k^2, discrete antidifferences of polynomials, "
                "and Gosper already exist. This pack stores one parametric G so later "
                "(c,a,b) tasks need not reconstruct it."
            ),
        },
        "hiddenModelReasoning": False,
    }


def _run_in_scope(pack: dict[str, Any]) -> dict[str, Any]:
    results = []
    for case in IN_SCOPE_CASES:
        outcome = apply_shifted_square_pack(
            {
                "taskId": case.get("taskId") or case.get("id"),
                "summand": case["summand"],
                "variable": case["variable"],
                "parameterC": case.get("parameterC"),
                "lower": case["lower"],
                "upper": case["upper"],
            },
            pack=pack,
            compare_baseline=False,
        )
        passed = (
            outcome.get("status") == "ok"
            and outcome["value"]["exact"] == case["expected"]
            and outcome["identity"]["status"] == "checked"
            and outcome["formalKernelChecked"] is False
            and outcome.get("gosperCalled") is False
        )
        results.append(
            {
                "id": case.get("taskId") or case.get("id"),
                "summand": case["summand"],
                "lower": case["lower"],
                "upper": case["upper"],
                "expected": case["expected"],
                "got": None if outcome.get("status") != "ok" else outcome["value"]["exact"],
                "identity": outcome.get("identity", {}).get("status"),
                "gosperCalled": outcome.get("gosperCalled"),
                "passed": passed,
            }
        )
    return {
        "cases": results,
        "allPassed": all(item["passed"] for item in results),
        "heldOutSecondTaskId": PARAM_HELD_OUT_TASK_ID,
        "heldOutExcluded": True,
        "notAUniversalProof": True,
        "reconstructionDisabled": True,
    }


def _run_negatives(pack: dict[str, Any]) -> dict[str, Any]:
    from .apply import PackApplicationError

    results = []
    for case in NEGATIVE_CASES:
        task = {
            "summand": case["summand"],
            "variable": case["variable"],
            "lower": case["lower"],
            "upper": case["upper"],
        }
        if "parameterC" in case:
            task["parameterC"] = case["parameterC"]
        try:
            outcome = apply_shifted_square_pack(task, pack=pack, compare_baseline=False)
            results.append(
                {
                    **case,
                    "happened": "unexpected_success",
                    "status": outcome.get("status"),
                    "passed": False,
                }
            )
        except PackApplicationError as error:
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
            "Wrong template and out-of-domain inputs must fail closed. Rejection "
            "is not a counterexample to the saved identity."
        ),
        "cases": results,
        "allRejected": all(item.get("happened") == "rejected" and item.get("passed") for item in results),
    }


def _assert_frozen_pack_matches_extraction(pack: dict[str, Any], evidence: dict[str, Any]) -> None:
    if pack["id"] != PARAM_PACK_ID or pack["schemaVersion"] != SCHEMA_VERSION:
        raise ExtractionError("E_INPUT", "frozen pack id/schema drifted from extraction constants")
    if pack["status"] != LIFECYCLE_VERIFIED:
        raise ExtractionError("E_INPUT", "frozen pack must be verified-in-declared-scope after extraction")
    if pack["novelty"]["status"] != NOVELTY_KNOWN_ADAPTATION:
        raise ExtractionError("E_INPUT", "frozen pack novelty label is not the honest extraction label")
    if pack["provenance"]["extractionTaskId"] != PARAM_EXTRACTION_TASK_ID:
        raise ExtractionError("E_INPUT", "frozen pack provenance is not the shifted-square extraction task")
    if pack["verification"]["formalKernelChecked"] is not False:
        raise ExtractionError("E_INPUT", "frozen pack incorrectly marks formal_kernel_checked")
    payload = pack["mathSemantics"]["parametricAntidifference"]
    if payload.get("source") != CANONICAL_G_SOURCE:
        raise ExtractionError("E_INPUT", "frozen pack G(k,c) source drifted from the derived canonical form")
    if payload.get("notFromGosper") is not True:
        raise ExtractionError("E_INPUT", "frozen pack must not claim G came from Gosper")
    encoded = json.dumps(pack)
    if "355" in encoded or "44100" in encoded:
        raise ExtractionError("E_INPUT", "frozen pack must not bake the held-out numeric answer")
    if not evidence["inScopeVerification"]["allPassed"]:
        raise ExtractionError("E_RUNTIME", "in-scope verification failed")
    if not evidence["domainAndNegatives"]["allRejected"]:
        raise ExtractionError("E_RUNTIME", "negative domain cases did not all reject")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
