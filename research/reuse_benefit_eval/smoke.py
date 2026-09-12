"""Run the pre-registered reuse-benefit smoke and build a machine-readable report."""

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
from research.method_packs.loader import PackFormatError

from .arms import (
    is_arm_exception,
    run_arm,
    run_b0,
    run_b1,
    run_b_codegen,
    run_b_template,
    run_p_pack,
    trace_construction_calls,
)
from .codegen import prepare_codegen, skip_reasons
from .protocol import (
    ARM_B0,
    ARM_B1,
    ARM_B_CODEGEN,
    ARM_B_TEMPLATE,
    ARM_P_PACK,
    PRIMARY_ARMS,
    REPORT_KIND,
    TASK_P1,
    load_protocol,
    protocol_digest,
    task_by_id,
    tasks,
    validate_protocol,
)
from .score import decide, result_summary, score_cell
from .template import prepare_template


ROOT = Path(__file__).resolve().parents[2]


def run_smoke(*, protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    document = validate_protocol(protocol) if protocol is not None else load_protocol()
    registered_tasks = tasks(document)
    trial_count = int(document["latency"]["trials"])
    labels = list(document["latency"]["labels"])
    arm_plan = [str(arm["id"]) for arm in document["arms"]]

    prep = _run_prep()

    cells: list[dict[str, Any]] = []
    for arm_id in arm_plan:
        for task in registered_tasks:
            cells.append(_run_cell(arm_id, task, trial_count=trial_count, labels=labels))

    stripped = _stripped_payload_probe(task_by_id(TASK_P1, document))
    wrong_g = _wrong_g_probe(task_by_id(TASK_P1, document))
    fair_baselines = _fair_baseline_cubes_probe()
    codegen_skip = skip_reasons()

    decision = decide(
        cells,
        stripped=stripped,
        wrong_g=wrong_g,
        fair_baselines=fair_baselines,
        codegen_skip=codegen_skip,
    )

    planned = [(arm_id, task["id"]) for arm_id in arm_plan for task in registered_tasks]
    actual = [(cell.get("arm"), cell.get("task")) for cell in cells]
    complete = actual == planned
    if not complete:
        decision["problems"] = list(decision.get("problems") or []) + [
            "report is missing or extra relative to planned protocol cells"
        ]
        decision["verdict"] = "targeted_fix"
        decision["targetedFix"] = True
        decision["promote"] = False
    decision["complete"] = complete

    table = [_table_row(cell) for cell in cells]
    judgments = decision.get("judgments") or {}
    return {
        "kind": REPORT_KIND,
        "stage": "reuse-benefit",
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
        "mandatoryClaimZh": document["mandatoryClaimZh"],
        "mandatoryClaimAnswerZh": document["mandatoryClaimAnswerZh"],
        "executionPlan": {
            "arms": arm_plan,
            "tasks": [task["id"] for task in registered_tasks],
            "trials": trial_count,
            "labels": labels,
        },
        "prep": prep,
        "pack": {
            "id": PARAM_PACK_ID,
            "version": PARAM_PACK_VERSION,
            "publicPromotion": False,
            "loadedForPPack": True,
            "loadedForB0": False,
            "loadedForB1": False,
            "loadedForBTemplate": False,
            "loadedForBCodegen": False,
        },
        "cells": cells,
        "table": table,
        "structuralProbes": {
            "strippedPayload": stripped,
            "wrongSavedG": wrong_g,
            "fairBaselinesNotCrippledOnCubes": fair_baselines,
            "codegenSkip": codegen_skip,
        },
        "judgments": judgments,
        "decision": decision,
        "refusedClaims": {
            "overallBenefitPercent": {
                "emitted": False,
                "reason": "smoke is an integration signal, not a benefit percentage",
            },
            "dollarCosts": {
                "emitted": False,
                "reason": document["budget"]["dollarCostsOmittedBecause"],
            },
            "savingsPercent": {
                "emitted": False,
                "reason": "do not invent a savings percentage from in-process timings",
            },
            "semanticAdoptionFromLifecycleEvidenceAlone": {
                "emitted": False,
                "reason": "call-alone is not adoption; B_template on the same tasks is the drop-library contrast",
            },
            "coversOriginalTaskClaim": {
                "emitted": False,
                "valueForced": False,
                "reason": "obligation success is not coverage of the original task claim",
            },
            "uniquenessFromFasterThanColdGosper": {
                "emitted": False,
                "reason": "B_template and B_codegen also skip construction",
            },
            "collapsedSuccessFlag": {
                "emitted": False,
                "reason": "trustworthiness, behavior, and utility stay separate",
            },
        },
        "honesty": {
            **document["honesty"],
            "smokeIsNotOverallBenefitPercent": True,
            "greenHarnessTestsAreNotCompletion": True,
            "lifecycleEvidenceIsNotSemanticAdoption": True,
            "callAloneIsNotAdoption": True,
            "coversOriginalTaskClaimStaysFalse": all(
                (cell.get("scoring") or {}).get("coversOriginalTaskClaim") is False for cell in cells
            ),
            "negativeNeverCountedAsSolved": all(
                not (
                    cell.get("task") in {"negative-harmonic", "negative-reversed"}
                    and (cell.get("scoring") or {}).get("countedAsSolved")
                )
                for cell in cells
            ),
            "packNotPromoted": True,
            "noHostUiMcp": True,
            "latencyLabelsAreFirstRepeatNotColdHot": True,
            "gosperCalledJsonFlagIsNotTheProbe": True,
            "judgmentsAreNotOneSuccessFlag": judgments.get("notCollapsedIntoOneSuccess") is True,
            "benefitComparisonDoesNotCrippleBaselines": True,
        },
        "outOfScope": document["outOfScope"],
        "latencyNote": document["latency"]["note"],
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    if path.exists():
        raise CalculatorError("E_INPUT", "result output already exists; refusing to overwrite it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run_prep() -> dict[str, Any]:
    started = time.perf_counter()
    template_prep = prepare_template()
    template_ms = round((time.perf_counter() - started) * 1000.0, 3)
    started = time.perf_counter()
    codegen_prep = prepare_codegen()
    codegen_ms = round((time.perf_counter() - started) * 1000.0, 3)
    return {
        "B0": {"once": False, "note": "no family prep; constructs a closed value per task"},
        "B1": {"once": False, "note": "no family prep; constructs G per task"},
        "B_template": {**template_prep, "latencyMs": template_ms},
        "B_codegen": {**codegen_prep, "latencyMs": codegen_ms},
        "P-pack": {
            "once": True,
            "note": "G(k,c) was extracted in a prior experiment and frozen in pack JSON; this smoke only loads it",
            "artifact": "research/method_packs/shifted_square_antidifference.v0/pack.json",
        },
        "note": (
            "Prep is one-time and reported separately. It is not amortized into a savings percentage."
        ),
    }


def _run_cell(
    arm_id: str,
    task: dict[str, Any],
    *,
    trial_count: int,
    labels: list[str],
) -> dict[str, Any]:
    trials: list[dict[str, Any]] = []
    result: dict[str, Any] | None = None
    error: BaseException | None = None
    last_counts = {"gosper_sum": 0, "construct_antidifference": 0}
    for index in range(trial_count):
        started = time.perf_counter()
        trial_result: dict[str, Any] | None = None
        trial_error: BaseException | None = None
        with trace_construction_calls() as counts:
            try:
                trial_result = run_arm(arm_id, task)
                trial_error = None
            except Exception as caught:
                if not is_arm_exception(caught):
                    raise
                trial_result = None
                trial_error = caught
            last_counts = {
                "gosper_sum": int(counts["gosper_sum"]),
                "construct_antidifference": int(counts["construct_antidifference"]),
            }
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
    first, repeat = trials[0], trials[-1]
    disagree = (first.get("status"), first.get("errorCode"), first.get("valueExact")) != (
        repeat.get("status"),
        repeat.get("errorCode"),
        repeat.get("valueExact"),
    )
    latency = {trial["label"]: trial["latencyMs"] for trial in trials}
    return {
        "arm": arm_id,
        "task": task["id"],
        "taskId": task.get("taskId"),
        "summand": task["summand"],
        "parameterC": task.get("parameterC"),
        "lower": task["lower"],
        "upper": task["upper"],
        "expectedExact": task.get("expectedExact"),
        "role": task.get("role"),
        "latencyMs": latency,
        "trials": trials,
        "trialsDisagree": disagree,
        "summary": summary,
        "scoring": scoring,
    }


def _stripped_payload_probe(held_out: dict[str, Any]) -> dict[str, Any]:
    from research.method_packs.apply import apply_method_pack
    from research.method_packs.format import DEFAULT_PARAM_PACK_PATH

    pack = json.loads(Path(DEFAULT_PARAM_PACK_PATH).read_text(encoding="utf-8"))
    semantics = pack.get("mathSemantics")
    if isinstance(semantics, dict):
        semantics.pop("parametricAntidifference", None)
    payload = {
        "summand": held_out["summand"],
        "variable": held_out.get("variable") or "k",
        "lower": held_out["lower"],
        "upper": held_out["upper"],
        "parameterC": held_out.get("parameterC"),
        "taskId": held_out.get("taskId"),
    }
    try:
        apply_method_pack(payload, pack=pack, compare_baseline=False)
    except (PackFormatError, CalculatorError) as error:
        return {
            "refused": True,
            "errorCode": getattr(error, "code", None),
            "errorType": type(error).__name__,
            "message": getattr(error, "message", str(error)),
            "task": TASK_P1,
            "note": "Stripping parametricAntidifference must stop the P-pack path even though B1 could still construct.",
        }
    return {
        "refused": False,
        "errorCode": None,
        "errorType": None,
        "message": "stripped pack completed; this is a harness failure",
        "task": TASK_P1,
        "note": "Stripping parametricAntidifference must stop the P-pack path.",
    }


def _wrong_g_probe(held_out: dict[str, Any]) -> dict[str, Any]:
    from research.method_packs.apply import apply_method_pack
    from research.method_packs.format import DEFAULT_PARAM_PACK_PATH

    pack = json.loads(Path(DEFAULT_PARAM_PACK_PATH).read_text(encoding="utf-8"))
    semantics = pack.get("mathSemantics")
    if isinstance(semantics, dict) and isinstance(semantics.get("parametricAntidifference"), dict):
        semantics["parametricAntidifference"]["source"] = "k"
    payload = {
        "summand": held_out["summand"],
        "variable": held_out.get("variable") or "k",
        "lower": held_out["lower"],
        "upper": held_out["upper"],
        "parameterC": held_out.get("parameterC"),
        "taskId": held_out.get("taskId"),
    }
    try:
        result = apply_method_pack(payload, pack=pack, compare_baseline=False)
    except CalculatorError as error:
        return {
            "failClosed": True,
            "emittedValue": False,
            "status": "error",
            "errorCode": getattr(error, "code", None),
            "task": TASK_P1,
            "note": "Wrong saved G must not produce a finite-sum value.",
        }
    emitted = isinstance(result.get("value"), dict) and result.get("status") == "ok"
    return {
        "failClosed": result.get("status") != "ok" and not emitted,
        "emittedValue": bool(emitted),
        "status": result.get("status"),
        "task": TASK_P1,
        "note": "Wrong saved G must not produce a finite-sum value.",
    }


def _fair_baseline_cubes_probe() -> dict[str, Any]:
    cubes = {"summand": "k^3", "variable": "k", "lower": 1, "upper": 20}
    summaries: dict[str, dict[str, Any]] = {}
    errors: dict[str, BaseException | None] = {}
    runners = {
        ARM_B0: run_b0,
        ARM_B1: run_b1,
        ARM_B_TEMPLATE: run_b_template,
        ARM_B_CODEGEN: run_b_codegen,
        ARM_P_PACK: run_p_pack,
    }
    for arm_id, runner in runners.items():
        caught: BaseException | None = None
        result: dict[str, Any] | None = None
        try:
            result = runner(cubes)
        except Exception as error:
            if not is_arm_exception(error):
                raise
            caught = error
        summaries[arm_id] = result_summary(result, caught)
        errors[arm_id] = caught

    def _refused(summary: dict[str, Any]) -> bool:
        return summary.get("status") in {"error", "inapplicable", "unsupported"} and summary.get(
            "errorCode"
        ) in {"E_UNSUPPORTED", "E_DOMAIN"}

    return {
        "summand": "k^3",
        "lower": 1,
        "upper": 20,
        "b0ValueExact": summaries[ARM_B0].get("valueExact"),
        "b0Status": summaries[ARM_B0].get("status"),
        "b1ValueExact": summaries[ARM_B1].get("valueExact"),
        "b1Status": summaries[ARM_B1].get("status"),
        "b1Constructor": summaries[ARM_B1].get("constructor"),
        "templateStatus": summaries[ARM_B_TEMPLATE].get("status"),
        "templateErrorCode": summaries[ARM_B_TEMPLATE].get("errorCode"),
        "templateRefused": _refused(summaries[ARM_B_TEMPLATE]),
        "codegenStatus": summaries[ARM_B_CODEGEN].get("status"),
        "codegenErrorCode": summaries[ARM_B_CODEGEN].get("errorCode"),
        "codegenRefused": _refused(summaries[ARM_B_CODEGEN]),
        "pPackStatus": summaries[ARM_P_PACK].get("status"),
        "pPackErrorCode": summaries[ARM_P_PACK].get("errorCode"),
        "pPackRefused": _refused(summaries[ARM_P_PACK]),
        "note": (
            "Out of the shifted-square family. B0/B1 may still construct 44100. "
            "Family template/codegen/P-pack must refuse. This probe is not a timed comparison cell."
        ),
    }


def _table_row(cell: dict[str, Any]) -> dict[str, Any]:
    scoring = cell.get("scoring") or {}
    summary = cell.get("summary") or {}
    return {
        "arm": cell.get("arm"),
        "task": cell.get("task"),
        "status": summary.get("status"),
        "valueExact": summary.get("valueExact"),
        "errorCode": summary.get("errorCode"),
        "countedAsSolved": scoring.get("countedAsSolved"),
        "wrongAcceptance": scoring.get("wrongAcceptance"),
        "applicabilityMisjudgment": scoring.get("applicabilityMisjudgment"),
        "coversOriginalTaskClaim": scoring.get("coversOriginalTaskClaim"),
        "lifecycleEvidence": scoring.get("lifecycleEvidence"),
        "semanticAdoption": False,
        "usedSavedContent": scoring.get("usedSavedContent"),
        "stepsExecuted": scoring.get("stepsExecuted"),
        "gosperCalledJsonFlag": scoring.get("gosperCalledJsonFlag"),
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
