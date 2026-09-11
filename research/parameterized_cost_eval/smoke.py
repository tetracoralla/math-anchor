"""Run the pre-registered parameterized cost smoke and build a machine-readable report."""

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

from .arms import is_arm_exception, run_arm, run_b0, run_b1, run_p_pack, trace_construction_calls
from .protocol import (
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


ROOT = Path(__file__).resolve().parents[2]


def run_smoke(*, protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    document = validate_protocol(protocol) if protocol is not None else load_protocol()
    registered_tasks = tasks(document)
    cells: list[dict[str, Any]] = []

    for arm_id in PRIMARY_ARMS:
        for task in registered_tasks:
            cells.append(_run_cell(arm_id, task))

    stripped = _stripped_payload_probe(task_by_id(TASK_P1, document))
    fair_baselines = _fair_baseline_cubes_probe()

    decision = decide(cells, stripped=stripped, fair_baselines=fair_baselines)

    planned = [(arm_id, task["id"]) for arm_id in PRIMARY_ARMS for task in registered_tasks]
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
    return {
        "kind": REPORT_KIND,
        "stage": "parameterized-cost-smoke",
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
        "pack": {
            "id": PARAM_PACK_ID,
            "version": PARAM_PACK_VERSION,
            "publicPromotion": False,
            "loadedForPPack": True,
            "loadedForB0": False,
            "loadedForB1": False,
        },
        "cells": cells,
        "table": table,
        "structuralProbes": {
            "strippedPayload": stripped,
            "fairBaselinesNotCrippledOnCubes": fair_baselines,
        },
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
                "reason": "call-alone is not adoption; B1 on the same tasks is the drop-library contrast",
            },
            "coversOriginalTaskClaim": {
                "emitted": False,
                "valueForced": False,
                "reason": "obligation success is not coverage of the original task claim",
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
                    cell.get("task") == "negative-harmonic"
                    and (cell.get("scoring") or {}).get("countedAsSolved")
                )
                for cell in cells
            ),
            "packNotPromoted": True,
            "noHostUiMcp": True,
            "latencyLabelsAreFirstRepeatNotColdHot": True,
            "gosperCalledJsonFlagIsNotTheProbe": True,
        },
        "outOfScope": document["outOfScope"],
        "latencyNote": document["latency"]["note"],
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    if path.exists():
        raise CalculatorError("E_INPUT", "result output already exists; refusing to overwrite it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run_cell(arm_id: str, task: dict[str, Any]) -> dict[str, Any]:
    trials: list[dict[str, Any]] = []
    result: dict[str, Any] | None = None
    error: BaseException | None = None
    last_counts = {"gosper_sum": 0, "construct_antidifference": 0}
    for index in range(2):
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
        trials.append(
            {
                "index": index,
                "label": "first" if index == 0 else "repeat",
                "latencyMs": round(latency_ms, 3),
                "status": trial_summary.get("status"),
                "errorCode": trial_summary.get("errorCode"),
                "valueExact": trial_summary.get("valueExact"),
                "constructionTrace": last_counts,
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
    first, repeat = trials[0], trials[1]
    disagree = (first.get("status"), first.get("errorCode"), first.get("valueExact")) != (
        repeat.get("status"),
        repeat.get("errorCode"),
        repeat.get("valueExact"),
    )
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
        "latencyMs": {"first": first["latencyMs"], "repeat": repeat["latencyMs"]},
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


def _fair_baseline_cubes_probe() -> dict[str, Any]:
    cubes = {"summand": "k^3", "variable": "k", "lower": 1, "upper": 20}
    b0_error = None
    b1_error = None
    p_error = None
    b0: dict[str, Any] | None = None
    b1: dict[str, Any] | None = None
    p_pack: dict[str, Any] | None = None
    try:
        b0 = run_b0(cubes)
    except Exception as caught:
        if not is_arm_exception(caught):
            raise
        b0_error = caught
    try:
        b1 = run_b1(cubes)
    except Exception as caught:
        if not is_arm_exception(caught):
            raise
        b1_error = caught
    try:
        p_pack = run_p_pack(cubes)
    except Exception as caught:
        if not is_arm_exception(caught):
            raise
        p_error = caught
    b0_summary = result_summary(b0, b0_error)
    b1_summary = result_summary(b1, b1_error)
    p_summary = result_summary(p_pack, p_error)
    p_refused = p_summary.get("status") in {"error", "inapplicable", "unsupported"} and p_summary.get(
        "errorCode"
    ) in {"E_UNSUPPORTED", "E_DOMAIN"}
    return {
        "summand": "k^3",
        "lower": 1,
        "upper": 20,
        "b0ValueExact": b0_summary.get("valueExact"),
        "b0Status": b0_summary.get("status"),
        "b1ValueExact": b1_summary.get("valueExact"),
        "b1Status": b1_summary.get("status"),
        "b1Constructor": b1_summary.get("constructor"),
        "pPackStatus": p_summary.get("status"),
        "pPackErrorCode": p_summary.get("errorCode"),
        "pPackRefused": p_refused,
        "note": (
            "Out of the shifted-square family. B0/B1 may still construct 44100. "
            "P-pack must refuse. This probe is not a timed comparison cell."
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
