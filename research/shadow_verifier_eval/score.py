"""Score shadow-verifier cells. G1–G6 stay targets; this smoke does not complete Epoch 2."""

from __future__ import annotations

from typing import Any

from .protocol import (
    ARM_B2,
    ARM_B3,
    CONTROL_TASKS,
    DEFERRED_ARMS,
    GATE_IDS,
    MODEL_ARMS_DEFERRED,
    REPAIRABLE_TASKS,
    RUNNABLE_ARMS,
    SUPPORTED_ERROR_TASKS,
    expected_by_arm,
)


def score_cell(arm_id: str, task: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    expected = expected_by_arm(task, arm_id)
    if arm_id in DEFERRED_ARMS:
        matched = (
            result.get("status") == MODEL_ARMS_DEFERRED
            and result.get("modelArms") == MODEL_ARMS_DEFERRED
            and result.get("liveQualityDelta") is None
            and result.get("finalAccuracy") is None
        )
        return {
            "matchedPreRegisteredExpectation": matched,
            "deferred": True,
            "modelArms": MODEL_ARMS_DEFERRED,
            "detected": None,
            "falseReject": None,
            "quietSuccess": None,
            "coversOriginalTaskClaim": False,
            "liveQualityDeltaInvented": False,
        }

    primary_ok = result.get("primaryStatus") == expected.get("primaryStatus")
    feedback_ok = result.get("feedbackStatus") == expected.get("feedbackStatus")
    mode_ok = result.get("responseMode") == expected.get("responseMode")
    detected_ok = bool(result.get("detected")) is bool(expected.get("detected"))
    includes_ok = bool(result.get("feedbackIncludesPrimary")) is bool(
        expected.get("feedbackIncludesPrimary")
    )
    quiet_ok = True
    context_ok = True
    receipt_ok = True
    if arm_id == ARM_B3:
        quiet_ok = bool(result.get("quietSuccess")) is bool(expected.get("quietSuccess"))
        if expected.get("modelContextBytesZero") is True:
            context_ok = result.get("modelContextBytes") == 0
        elif expected.get("modelContextBytesZero") is False:
            context_ok = int(result.get("modelContextBytes") or 0) > 0
        receipt_ok = result.get("receiptOutsideModelContext") is True
    repair_ok = True
    repair = result.get("repair") if isinstance(result.get("repair"), dict) else None
    if arm_id == ARM_B3 and expected.get("repairAfterPrimaryStatus"):
        repair_ok = (
            repair is not None
            and repair.get("primaryStatus") == expected.get("repairAfterPrimaryStatus")
            and bool(repair.get("quietSuccess")) is bool(expected.get("repairAfterQuietSuccess"))
            and repair.get("notALiveModelRepair") is True
        )
    elif repair is not None and arm_id != ARM_B3:
        repair_ok = False

    false_reject = bool(task.get("g3Control")) and result.get("primaryStatus") != "checked"
    matched = (
        primary_ok
        and feedback_ok
        and mode_ok
        and detected_ok
        and includes_ok
        and quiet_ok
        and context_ok
        and receipt_ok
        and repair_ok
        and result.get("coversOriginalTaskClaim") is not True
        and result.get("formalKernelChecked") is not True
    )
    return {
        "matchedPreRegisteredExpectation": matched,
        "deferred": False,
        "primaryStatus": result.get("primaryStatus"),
        "expectedPrimaryStatus": expected.get("primaryStatus"),
        "detected": bool(result.get("detected")),
        "falseReject": false_reject,
        "quietSuccess": result.get("quietSuccess"),
        "modelContextBytes": result.get("modelContextBytes"),
        "receiptOutsideModelContext": result.get("receiptOutsideModelContext"),
        "repairMatched": repair_ok if expected.get("repairAfterPrimaryStatus") else None,
        "coversOriginalTaskClaim": False,
        "formalKernelChecked": False,
        "g1SupportedSeededError": bool(task.get("g1SupportedSeededError")),
        "g3Control": bool(task.get("g3Control")),
    }


def _cell(cells: list[dict[str, Any]], arm_id: str, task_id: str) -> dict[str, Any] | None:
    for cell in cells:
        if cell.get("arm") == arm_id and cell.get("task") == task_id:
            return cell
    return None


def score_gates(
    cells: list[dict[str, Any]],
    *,
    probes: dict[str, Any],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    declared = protocol.get("gates") if isinstance(protocol.get("gates"), dict) else {}
    g1_counts: dict[str, dict[str, int]] = {}
    g3_false: dict[str, int] = {}
    g4_zero: dict[str, bool] = {}
    g5_repair: dict[str, bool] = {}
    for arm_id in RUNNABLE_ARMS:
        detected = 0
        total = 0
        false_rejects = 0
        for task_id in SUPPORTED_ERROR_TASKS:
            cell = _cell(cells, arm_id, task_id)
            total += 1
            scoring = (cell or {}).get("scoring") or {}
            if scoring.get("detected") is True and scoring.get("matchedPreRegisteredExpectation"):
                detected += 1
        g1_counts[arm_id] = {"detected": detected, "total": total}
        for task_id in CONTROL_TASKS:
            cell = _cell(cells, arm_id, task_id)
            scoring = (cell or {}).get("scoring") or {}
            if scoring.get("falseReject"):
                false_rejects += 1
        g3_false[arm_id] = false_rejects
        if arm_id == ARM_B3:
            zeros = []
            repairs = []
            for task_id in CONTROL_TASKS:
                cell = _cell(cells, arm_id, task_id)
                zeros.append(
                    cell is not None
                    and cell.get("modelContextBytes") == 0
                    and cell.get("quietSuccess") is True
                )
            g4_zero[arm_id] = all(zeros) and bool(zeros)
            for task_id in REPAIRABLE_TASKS:
                cell = _cell(cells, arm_id, task_id)
                scoring = (cell or {}).get("scoring") or {}
                repairs.append(scoring.get("repairMatched") is True)
            g5_repair[arm_id] = all(repairs) and bool(repairs)

    binding_detected = 0
    binding_total = 2
    if probes.get("wrongWitness", {}).get("failClosed"):
        binding_detected += 1
    if probes.get("staleSwappedResult", {}).get("failClosed"):
        binding_detected += 1

    g1_b2 = g1_counts[ARM_B2]
    g1_b3 = g1_counts[ARM_B3]
    g1_rate_b2 = g1_b2["detected"] / g1_b2["total"] if g1_b2["total"] else 0.0
    g1_rate_b3 = g1_b3["detected"] / g1_b3["total"] if g1_b3["total"] else 0.0
    g1_binding_rate = binding_detected / binding_total if binding_total else 0.0

    def _gate(gate_id: str, **fields: Any) -> dict[str, Any]:
        spec = declared.get(gate_id) if isinstance(declared.get(gate_id), dict) else {}
        payload = {
            "id": gate_id,
            "name": spec.get("name"),
            "target": spec.get("target"),
            "status": spec.get("status"),
            "liveModelRequired": spec.get("liveModelRequired"),
            "thisSmokeMeasures": spec.get("thisSmokeMeasures"),
            "note": spec.get("note"),
            "epoch2GateMet": False,
        }
        payload.update(fields)
        return payload

    return {
        "G1": _gate(
            "G1",
            thisMachine={
                "B2": {"detected": g1_b2["detected"], "total": g1_b2["total"], "rate": g1_rate_b2},
                "B3": {"detected": g1_b3["detected"], "total": g1_b3["total"], "rate": g1_rate_b3},
                "bindingProbes": {
                    "detected": binding_detected,
                    "total": binding_total,
                    "rate": g1_binding_rate,
                },
            },
            thisMachineDoesNotMeetEpoch2Gate=True,
        ),
        "G2": _gate(
            "G2",
            thisMachine=None,
            deferredBecause="requires matched live B0 vs B2/B3 accepted-error counts",
        ),
        "G3": _gate(
            "G3",
            thisMachine={"B2FalseRejects": g3_false[ARM_B2], "B3FalseRejects": g3_false[ARM_B3]},
            thisMachineDoesNotMeetEpoch2Gate=True,
        ),
        "G4": _gate(
            "G4",
            thisMachine={
                "B3QuietSuccessZeroReturnedContent": g4_zero.get(ARM_B3),
                "tenPercentVsB0": None,
            },
            deferredBecause="≤10% main-context growth vs B0 requires live model tokens",
            thisMachineDoesNotMeetEpoch2Gate=True,
        ),
        "G5": _gate(
            "G5",
            thisMachine={
                "B3SeededRepairHookMatched": g5_repair.get(ARM_B3),
                "notALiveModelRepair": True,
            },
            thisMachineDoesNotMeetEpoch2Gate=True,
        ),
        "G6": _gate(
            "G6",
            thisMachine=None,
            deferredBecause="requires a stronger and a weaker live model under the same protocol",
        ),
        "ids": list(GATE_IDS),
        "allRemainTargets": True,
    }


def decide(
    cells: list[dict[str, Any]],
    *,
    probes: dict[str, Any],
    gates: dict[str, Any],
) -> dict[str, Any]:
    problems: list[str] = []
    for cell in cells:
        scoring = cell.get("scoring") or {}
        label = f"{cell.get('arm')}×{cell.get('task')}"
        if not scoring.get("matchedPreRegisteredExpectation"):
            problems.append(f"{label}: did not match the pre-registered expectation")
        if scoring.get("coversOriginalTaskClaim") is True:
            problems.append(f"{label}: coversOriginalTaskClaim was true")
        if cell.get("arm") in DEFERRED_ARMS:
            if cell.get("finalAccuracy") is not None or cell.get("liveQualityDelta") is not None:
                problems.append(f"{label}: invented a live-model quality number")
    if probes.get("ok") is not True:
        problems.append("structural probes did not all pass")
    if probes.get("coreConformance", {}).get("ok") is not True:
        problems.append("evals/obligations/core.v0.1.json conformance failed")
    if probes.get("wrongWitness", {}).get("failClosed") is not True:
        problems.append("wrong-witness binding probe did not fail closed")
    if probes.get("staleSwappedResult", {}).get("failClosed") is not True:
        problems.append("stale-swapped certificate probe did not fail closed")
    if probes.get("cliQuietSuccess", {}).get("stdoutEmpty") is not True:
        problems.append("CLI --quiet-success did not emit empty stdout")
    if probes.get("cliFailuresOnlyOnFail", {}).get("ok") is not True:
        problems.append("CLI failure path did not return failures_only attention")

    targeted = bool(problems)
    return {
        "verdict": "targeted_fix" if targeted else "evidence_insufficient",
        "experimentVerdict": (
            "targeted_fix" if targeted else "deterministic_b2_b3_scaffold_ran"
        ),
        "promote": False,
        "targetedFix": targeted,
        "keepExperimental": True,
        "publicPromotion": False,
        "doNotStartH1": True,
        "packNotPromoted": True,
        "epoch2Complete": False,
        "modelArms": MODEL_ARMS_DEFERRED,
        "basedOnThisSmokeOnly": True,
        "notAStatisticalSaving": True,
        "problems": problems,
        "reasons": (
            [
                "This smoke found a harness or obligation-runtime honesty/correctness problem.",
                "Do not promote method packs. Do not start H1. Epoch 2 is not complete.",
            ]
            if targeted
            else [
                "Deterministic B2/B3 seeded corpus ran against the existing obligation runtime.",
                "B0/B1 remain model_arms=deferred. Live four-arm evidence is not invented.",
                "G1–G6 stay targets. This-machine B2/B3 detection is not Epoch 2 completion.",
                "Do not promote method packs. Do not start H1 from this scaffold.",
            ]
        ),
        "next": (
            "targeted fix on this scaffold; keep experimental"
            if targeted
            else (
                "Keep experimental. Run live B0/B1/B2/B3 only with a written model "
                "budget and --confirm-model-runs. Do not start H1. Do not promote packs."
            )
        ),
        "gatesRemainTargets": gates.get("allRemainTargets") is True,
    }
