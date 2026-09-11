"""Run the pre-registered A4 equal-budget smoke and build a machine-readable report."""

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

from research.method_packs.format import PACK_ID, PACK_VERSION
from research.method_packs.loader import load_pack
from research.polynomial_finite_sum_proposal.coverage import (
    coverage_from_failure,
    record_coverage,
)

from .arms import is_arm_exception, run_arm
from .protocol import (
    ARM_B0,
    ARM_B1,
    ARM_B2,
    ARM_B2_MINUS,
    PRIMARY_ARMS,
    REPORT_KIND,
    TASK_CUBES,
    load_protocol,
    protocol_digest,
    task_by_id,
    tasks,
)
from .score import (
    coverage_honesty,
    decide,
    result_summary,
    score_cell,
    should_run_b2_minus,
    t1_replay_lifecycle_ok,
)


ROOT = Path(__file__).resolve().parents[2]


def run_smoke(*, protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    document = protocol if protocol is not None else load_protocol()
    registered_tasks = tasks(document)
    cells: list[dict[str, Any]] = []
    pack = load_pack()

    for arm_id in PRIMARY_ARMS:
        for task in registered_tasks:
            cells.append(_run_cell(arm_id, task, pack=pack))

    b2_cubes = _cell(cells, ARM_B2, TASK_CUBES)
    run_minus, minus_reason = should_run_b2_minus(b2_cubes.get("scoring") if b2_cubes else None)
    b2_minus_record: dict[str, Any]
    if run_minus:
        cubes = task_by_id(TASK_CUBES, document)
        minus_cell = _run_cell(ARM_B2_MINUS, cubes, pack=None)
        cells.append(minus_cell)
        b2_value = (b2_cubes or {}).get("summary", {}).get("valueExact")
        minus_value = minus_cell.get("summary", {}).get("valueExact")
        b2_minus_record = {
            "ran": True,
            "skipReason": None,
            "task": TASK_CUBES,
            "arm": ARM_B2_MINUS,
            "packLoaded": False,
            "valueExact": minus_value,
            "b2ValueExact": b2_value,
            "valueUnchanged": minus_value == b2_value and minus_value == cubes.get("expectedExact"),
            "semanticAdoption": False,
            "impact": (
                "Removing the pack does not change the finite-sum value on the held-out cubes task. "
                "The A1 runner already produces the pre-registered 44100. Pack apply records a "
                "retrieve/instantiate/check/bind chain; lifecycleEvidence is not semantic adoption."
            ),
        }
    else:
        b2_minus_record = {
            "ran": False,
            "skipReason": minus_reason,
            "task": TASK_CUBES,
            "arm": ARM_B2_MINUS,
            "packLoaded": False,
            "valueExact": None,
            "b2ValueExact": (b2_cubes or {}).get("summary", {}).get("valueExact"),
            "valueUnchanged": None,
            "semanticAdoption": False,
            "impact": minus_reason,
        }

    decision = decide(cells, b2_minus_record)
    if not all(t1_replay_lifecycle_ok(cell) for cell in cells):
        decision["problems"] = list(decision.get("problems") or []) + [
            "B2×T1 replay minted cross-task lifecycle evidence"
        ]
        decision["verdict"] = "targeted_fix"
        decision["targetedFix"] = True
        decision["promote"] = False

    table = [_table_row(cell) for cell in cells]
    return {
        "kind": REPORT_KIND,
        "stage": "A4",
        "protocolKind": document["kind"],
        "protocolDigest": protocol_digest(),
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
            "id": PACK_ID,
            "version": PACK_VERSION,
            "publicPromotion": False,
            "loadedForB2": True,
            "loadedForB2Minus": False,
        },
        "cells": cells,
        "table": table,
        "b2Minus": b2_minus_record,
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
            "semanticAdoptionFromLifecycleEvidenceAlone": {
                "emitted": False,
                "reason": "call-alone is not adoption; B2-minus is the drop-library contrast",
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
            "greenHarnessTestsAreNotA4Completion": True,
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
        },
        "outOfScope": document["outOfScope"],
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    if path.exists():
        raise CalculatorError("E_INPUT", "result output already exists; refusing to overwrite it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run_cell(arm_id: str, task: dict[str, Any], *, pack: dict[str, Any] | None) -> dict[str, Any]:
    timings: list[float] = []
    result: dict[str, Any] | None = None
    error: BaseException | None = None
    for _trial in range(2):
        started = time.perf_counter()
        try:
            result = run_arm(arm_id, task)
            error = None
        except Exception as caught:
            if not is_arm_exception(caught):
                raise
            result = None
            error = caught
        timings.append((time.perf_counter() - started) * 1000.0)

    coverage = _coverage_record(arm_id, task, result, error, pack=pack)
    summary = result_summary(result, error)
    honesty = coverage_honesty(coverage)
    scoring = score_cell(arm_id=arm_id, task=task, summary=summary, honesty=honesty)
    return {
        "arm": arm_id,
        "task": task["id"],
        "taskId": task.get("taskId"),
        "summand": task["summand"],
        "lower": task["lower"],
        "upper": task["upper"],
        "expectedExact": task.get("expectedExact"),
        "role": task.get("role"),
        "latencyMs": {"cold": round(timings[0], 3), "hot": round(timings[1], 3)},
        "summary": summary,
        "coverage": honesty,
        "scoring": scoring,
    }


def _coverage_record(
    arm_id: str,
    task: dict[str, Any],
    result: dict[str, Any] | None,
    error: BaseException | None,
    *,
    pack: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = {
        "summand": task["summand"],
        "variable": task.get("variable") or "k",
        "lower": task["lower"],
        "upper": task["upper"],
        "taskId": task.get("taskId"),
    }
    source = {
        ARM_B0: "sympy-summation-baseline",
        ARM_B1: "polynomial-finite-sum-runner",
        ARM_B2: "method-pack-apply",
        ARM_B2_MINUS: "polynomial-finite-sum-runner",
    }.get(arm_id)
    pack_arg = pack if arm_id == ARM_B2 else None
    if error is not None:
        return coverage_from_failure(payload, error, pack=pack_arg, source=source)
    assert result is not None
    return record_coverage(payload, result, pack=pack_arg, source=source)


def _cell(cells: list[dict[str, Any]], arm_id: str, task_id: str) -> dict[str, Any] | None:
    for cell in cells:
        if cell.get("arm") == arm_id and cell.get("task") == task_id:
            return cell
    return None


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
        "reuseSignal": (scoring.get("reuseSignal") or {}).get("present"),
        "semanticAdoption": False,
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
