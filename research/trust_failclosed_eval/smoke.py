"""Run the pre-registered trust/fail-closed smoke and build a machine-readable report."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from math_anchor import __version__ as MATH_ANCHOR_VERSION
from math_anchor.errors import CalculatorError

from research.method_packs.format import PARAM_PACK_ID, PARAM_PACK_VERSION

from .arms import (
    empty_construction_trace,
    is_arm_exception,
    run_arm,
    trace_construction_calls,
)
from .probes import binding_mismatch_probe, stripped_payload_probe
from .protocol import (
    ARM_B_TEMPLATE,
    ARM_P_PACK,
    REPORT_KIND,
    TASK_CONTROL,
    load_protocol,
    protocol_digest,
    reconcile_mandatory_claim_answer_zh,
    task_by_id,
    tasks,
    validate_protocol,
)
from .score import construction_trace, decide, result_summary, score_cell


ROOT = Path(__file__).resolve().parents[2]


def run_smoke(*, protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    document = validate_protocol(protocol) if protocol is not None else load_protocol()
    registered_tasks = tasks(document)
    trial_count = int(document["latency"]["trials"])
    labels = list(document["latency"]["labels"])
    arm_plan = [str(arm["id"]) for arm in document["arms"]]

    cells: list[dict[str, Any]] = []
    for arm_id in arm_plan:
        for task in registered_tasks:
            cells.append(
                _run_cell(arm_id, task, trial_count=trial_count, labels=labels, protocol=document)
            )

    control = task_by_id(TASK_CONTROL, document)
    stripped = stripped_payload_probe(control)
    pack_control_result, pack_control_error = _run_once(ARM_P_PACK, control, document)
    template_control_result, _template_control_error = _run_once(ARM_B_TEMPLATE, control, document)
    binding = binding_mismatch_probe(
        pack_result=pack_control_result,
        pack_error=pack_control_error,
        template_result=template_control_result,
        task=control,
    )

    decision = decide(cells, stripped=stripped, binding=binding)

    planned = [(arm_id, task["id"]) for arm_id in arm_plan for task in registered_tasks]
    actual = [(cell.get("arm"), cell.get("task")) for cell in cells]
    complete = actual == planned
    if not complete:
        decision["problems"] = list(decision.get("problems") or []) + [
            "report is missing or extra relative to planned protocol cells"
        ]
        decision["verdict"] = "targeted_fix"
        decision["experimentVerdict"] = "targeted_fix"
        decision["targetedFix"] = True
        decision["promote"] = False
    decision["complete"] = complete

    table = [_table_row(cell) for cell in cells]
    judgments = decision.get("judgments") or {}
    reconciled_claim = reconcile_mandatory_claim_answer_zh(
        document["mandatoryClaimAnswerZh"],
        saved_g_differentiated=decision.get("observedWrongGDifferentiation"),
        domain_differentiated=decision.get("observedDomainDifferentiation"),
    )
    return {
        "kind": REPORT_KIND,
        "stage": "trust-failclosed",
        "protocolKind": document["kind"],
        "protocolDigest": protocol_digest(document),
        "complete": complete,
        "preRegistered": True,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "mathAnchorVersion": MATH_ANCHOR_VERSION,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "gitHead": _git_head(),
            "sympy": _sympy_version(),
        },
        "model": document["model"],
        "budget": document["budget"],
        "workload": document["workload"],
        "trustworthinessScale": document["trustworthinessScale"],
        "mandatoryClaimZh": document["mandatoryClaimZh"],
        "mandatoryClaimAnswerZh": reconciled_claim["answerZh"],
        "mandatoryClaimAnswerZhPinned": document["mandatoryClaimAnswerZh"],
        "mandatoryClaimDifferentiationClauseZh": reconciled_claim["differentiationClauseZh"],
        "mandatoryClaimAnswerZhOverwrittenBecauseDifferentiationFlagsDisagreed": reconciled_claim[
            "overwrittenBecauseDifferentiationFlagsDisagreed"
        ],
        "executionPlan": {
            "arms": arm_plan,
            "tasks": [task["id"] for task in registered_tasks],
            "trials": trial_count,
            "labels": labels,
        },
        "pack": {
            "id": PARAM_PACK_ID,
            "version": PARAM_PACK_VERSION,
            "publicPromotion": False,
            "loadedForPPack": True,
            "loadedForBTemplate": False,
        },
        "cells": cells,
        "table": table,
        "structuralProbes": {
            "strippedPayload": stripped,
            "bindingMismatch": binding,
        },
        "judgments": judgments,
        "decision": decision,
        "refusedClaims": {
            "overallBenefitPercent": {
                "emitted": False,
                "reason": "this smoke is not a benefit percentage",
            },
            "dollarCosts": {
                "emitted": False,
                "reason": document["budget"]["dollarCostsOmittedBecause"],
            },
            "savingsPercent": {
                "emitted": False,
                "reason": "do not invent a savings percentage from in-process timings",
            },
            "latencyBakeOff": {
                "emitted": False,
                "reason": "reuse-benefit already reported no net utility vs B_template; not re-asked here",
            },
            "semanticAdoptionFromLifecycleEvidenceAlone": {
                "emitted": False,
                "reason": "call-alone is not adoption",
            },
            "coversOriginalTaskClaim": {
                "emitted": False,
                "valueForced": False,
                "reason": "obligation success is not coverage of the original task claim",
            },
            "collapsedSuccessFlag": {
                "emitted": False,
                "reason": "trustworthiness, behavior, and utility stay separate",
            },
            "publicPromotion": {
                "emitted": False,
                "reason": "promotion is forbidden in this smoke",
            },
        },
        "honesty": {
            **document["honesty"],
            "smokeIsNotOverallBenefitPercent": True,
            "greenHarnessTestsAreNotCompletion": True,
            "packNotPromoted": True,
            "noHostUiMcpThisPr": True,
            "latencyLabelsAreInformational": True,
            "gosperCalledJsonFlagIsNotTheProbe": True,
            "usedSavedContentComesFromApply": True,
            "constructionWrapIsTheBindingProbe": True,
            "mandatoryClaimAnswerZhPinned": True,
            "mandatoryClaimDifferentiationClauseGeneratedFromFlags": True,
            "mandatoryClaimAnswerZhConsistentWithDifferentiationFlags": reconciled_claim[
                "consistentWithDifferentiationFlags"
            ],
            "judgmentsAreNotOneSuccessFlag": judgments.get("notCollapsedIntoOneSuccess") is True,
            "familyMatchingIsNotPackUnique": True,
            "researchStatus": document.get("researchStatus"),
        },
        "outOfScopeThisSmoke": document["outOfScopeThisSmoke"],
        "latencyNote": document["latency"]["note"],
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    if path.exists():
        raise CalculatorError("E_INPUT", "result output already exists; refusing to overwrite it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run_once(
    arm_id: str,
    task: dict[str, Any],
    protocol: dict[str, Any],
) -> tuple[dict[str, Any] | None, BaseException | None]:
    try:
        return run_arm(arm_id, task, protocol=protocol), None
    except Exception as caught:
        if not is_arm_exception(caught):
            raise
        return None, caught


def _run_cell(
    arm_id: str,
    task: dict[str, Any],
    *,
    trial_count: int,
    labels: list[str],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    trials: list[dict[str, Any]] = []
    result: dict[str, Any] | None = None
    error: BaseException | None = None
    last_counts = empty_construction_trace()
    for index in range(trial_count):
        started = time.perf_counter()
        trial_result: dict[str, Any] | None = None
        trial_error: BaseException | None = None
        with trace_construction_calls() as counts:
            try:
                trial_result = run_arm(arm_id, task, protocol=protocol)
                trial_error = None
            except Exception as caught:
                if not is_arm_exception(caught):
                    raise
                trial_result = None
                trial_error = caught
            last_counts = construction_trace(counts)
        latency_ms = (time.perf_counter() - started) * 1000.0
        trial_summary = result_summary(trial_result, trial_error)
        label = labels[index] if index < len(labels) else f"trial-{index}"
        trials.append(
            {
                "index": index,
                "label": label,
                "latencyMs": round(latency_ms, 3),
                "status": trial_summary.get("status"),
                "errorCode": trial_summary.get("errorCode"),
                "valueExact": trial_summary.get("valueExact"),
                "trustworthiness": None,
                "constructionTrace": last_counts,
                "stepsExecuted": trial_summary.get("stepsExecuted"),
            }
        )
        result = trial_result
        error = trial_error

    summary = result_summary(result, error)
    scoring = score_cell(
        arm_id=arm_id,
        task=task,
        summary=summary,
        construction=last_counts,
    )
    for trial in trials:
        trial["trustworthiness"] = scoring.get("trustworthiness")
    first, last = trials[0], trials[-1]
    disagree = (first.get("status"), first.get("errorCode"), first.get("valueExact")) != (
        last.get("status"),
        last.get("errorCode"),
        last.get("valueExact"),
    )
    latency = {trial["label"]: trial["latencyMs"] for trial in trials}
    return {
        "arm": arm_id,
        "task": task["id"],
        "taskId": task.get("taskId"),
        "role": task.get("role"),
        "summand": task["summand"],
        "parameterC": task.get("parameterC"),
        "lower": task["lower"],
        "upper": task["upper"],
        "savedG": task.get("savedG"),
        "proposalTrustedOutcome": task.get("proposalTrustedOutcome"),
        "trueExact": task.get("trueExact") or task.get("expectedExact"),
        "latencyMs": latency,
        "trials": trials,
        "trialsDisagree": disagree,
        "summary": summary,
        "scoring": scoring,
    }


def _table_row(cell: dict[str, Any]) -> dict[str, Any]:
    scoring = cell.get("scoring") or {}
    summary = cell.get("summary") or {}
    return {
        "arm": cell.get("arm"),
        "task": cell.get("task"),
        "trustworthiness": scoring.get("trustworthiness"),
        "trustReason": scoring.get("trustReason"),
        "status": summary.get("status"),
        "valueExact": summary.get("valueExact"),
        "errorCode": summary.get("errorCode"),
        "countedAsSolved": scoring.get("countedAsSolved"),
        "failClosed": scoring.get("failClosed"),
        "wrongAcceptance": scoring.get("wrongAcceptance"),
        "silentAcceptance": scoring.get("silentAcceptance"),
        "usedSavedContent": scoring.get("usedSavedContent"),
        "savedG": cell.get("savedG"),
        "coversOriginalTaskClaim": scoring.get("coversOriginalTaskClaim"),
        "constructionTrace": scoring.get("constructionTrace"),
        "latencyMs": cell.get("latencyMs"),
    }


def _git_head() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _sympy_version() -> str | None:
    try:
        import sympy as sp
    except ImportError:
        return None
    return str(sp.__version__)
