"""Run the pre-registered shadow-verifier scaffold and build a machine-readable report."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from math_anchor import __version__ as MATH_ANCHOR_VERSION
from math_anchor.errors import CalculatorError

from .arms import is_arm_exception, run_arm
from .model_interface import reject_include_model_arms
from .probes import run_structural_probes
from .protocol import (
    DEFERRED_ARMS,
    MODEL_ARMS_DEFERRED,
    PRIMARY_ARMS,
    REPORT_KIND,
    load_protocol,
    protocol_digest,
    tasks,
    validate_protocol,
)
from .score import decide, score_cell, score_gates


ROOT = Path(__file__).resolve().parents[2]


def run_smoke(
    *,
    protocol: dict[str, Any] | None = None,
    receipt_dir: Path | None = None,
    include_model_arms: bool = False,
) -> dict[str, Any]:
    document = validate_protocol(protocol) if protocol is not None else load_protocol()
    if include_model_arms:
        reject_include_model_arms(protocol=document)

    registered_tasks = tasks(document)
    own_temp = False
    if receipt_dir is None:
        receipt_dir = Path(tempfile.mkdtemp(prefix="shadow-verifier-receipts-"))
        own_temp = True
    else:
        receipt_dir.mkdir(parents=True, exist_ok=True)

    cells: list[dict[str, Any]] = []
    for arm_id in PRIMARY_ARMS:
        for task in registered_tasks:
            cells.append(
                _run_cell(arm_id, task, protocol=document, receipt_dir=receipt_dir)
            )

    probes = run_structural_probes(receipt_dir / "cli-probes")
    gates = score_gates(cells, probes=probes, protocol=document)
    decision = decide(cells, probes=probes, gates=gates)

    planned = [(arm_id, task["id"]) for arm_id in PRIMARY_ARMS for task in registered_tasks]
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
    return {
        "kind": REPORT_KIND,
        "stage": "shadow-verifier",
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
        },
        "model": document["model"],
        "budget": document["budget"],
        "workload": document["workload"],
        "independence": document["independence"],
        "progressiveAssurance": document["progressiveAssurance"],
        "executionPlan": {
            "arms": list(PRIMARY_ARMS),
            "runnableThisSmoke": ["B2", "B3"],
            "deferredThisSmoke": list(DEFERRED_ARMS),
            "tasks": [task["id"] for task in registered_tasks],
            "modelArms": MODEL_ARMS_DEFERRED,
        },
        "liveModelCommands": document["liveModelCommands"],
        "cells": cells,
        "table": table,
        "structuralProbes": probes,
        "gates": gates,
        "decision": decision,
        "receiptDir": str(receipt_dir),
        "receiptDirIsTemporary": own_temp,
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
                "reason": "do not invent a savings percentage",
            },
            "liveModelQualityDelta": {
                "emitted": False,
                "reason": "model_arms=deferred; live B0/B1 numbers are not invented",
            },
            "epoch2Complete": {
                "emitted": False,
                "valueForced": False,
                "reason": "Epoch 2 is not done until live four-arm model evidence exists",
            },
            "coversOriginalTaskClaim": {
                "emitted": False,
                "valueForced": False,
                "reason": "obligation success is not coverage of the original task claim",
            },
            "publicPromotion": {
                "emitted": False,
                "reason": "promotion is forbidden in this smoke",
            },
            "methodPackPromotion": {
                "emitted": False,
                "reason": "method packs remain research samples; dated H1 freeze",
            },
        },
        "honesty": {
            **document["honesty"],
            "smokeIsNotOverallBenefitPercent": True,
            "greenHarnessTestsAreNotCompletion": True,
            "packNotPromoted": True,
            "modelArmsDeferred": True,
            "noLiveModelNumbersInvented": True,
            "epoch2NotCompleteUntilLiveFourArmEvidence": True,
        },
        "outOfScopeThisSmoke": document["outOfScopeThisSmoke"],
        "corruptionKinds": document["corruptionKinds"],
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    if path.exists():
        raise CalculatorError("E_INPUT", "result output already exists; refusing to overwrite it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run_cell(
    arm_id: str,
    task: dict[str, Any],
    *,
    protocol: dict[str, Any],
    receipt_dir: Path,
) -> dict[str, Any]:
    try:
        result = run_arm(arm_id, task, protocol=protocol, receipt_dir=receipt_dir)
    except Exception as caught:
        if not is_arm_exception(caught):
            raise
        result = {
            "arm": arm_id,
            "task": task["id"],
            "status": "error",
            "errorCode": getattr(caught, "code", None),
            "message": getattr(caught, "message", str(caught)),
            "detected": False,
            "coversOriginalTaskClaim": False,
            "formalKernelChecked": False,
        }
    scoring = score_cell(arm_id, task, result)
    cell = dict(result)
    cell["scoring"] = scoring
    return cell


def _table_row(cell: dict[str, Any]) -> dict[str, Any]:
    scoring = cell.get("scoring") or {}
    return {
        "arm": cell.get("arm"),
        "task": cell.get("task"),
        "status": cell.get("status"),
        "primaryStatus": cell.get("primaryStatus"),
        "detected": scoring.get("detected"),
        "quietSuccess": cell.get("quietSuccess"),
        "modelContextBytes": cell.get("modelContextBytes"),
        "modelArms": cell.get("modelArms"),
        "matched": scoring.get("matchedPreRegisteredExpectation"),
    }


def _git_head() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None
