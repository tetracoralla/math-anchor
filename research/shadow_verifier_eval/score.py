"""Score shadow-verifier cells. G1–G6 stay targets; this smoke does not complete Epoch 2."""

from __future__ import annotations

from typing import Any

from .protocol import (
    ARM_B0,
    ARM_B1,
    ARM_B2,
    ARM_B3,
    CONTROL_TASKS,
    DEFERRED_ARMS,
    GATE_IDS,
    MODEL_ARMS_DEFERRED,
    RUNNABLE_ARMS,
    SAME_CLAIM_REPAIR_TASKS,
    SUPPORTED_ERROR_TASKS,
    UNRELATED_RESUBMIT_TASKS,
    expected_by_arm,
)


def _score_live_model_cell(arm_id: str, task: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    invented = (
        result.get("liveQualityDelta") is not None
        or result.get("dollarCost") is not None
        or result.get("finalAccuracy") is not None
    )
    matched = (
        result.get("coversOriginalTaskClaim") is not True
        and result.get("formalKernelChecked") is not True
        and not invented
        and result.get("status") in {"ok", "error"}
        and result.get("modelArms") == "ran"
    )
    g1 = bool(task.get("g1SupportedSeededError"))
    g3 = bool(task.get("g3Control"))
    return {
        "matchedPreRegisteredExpectation": matched,
        "deferred": False,
        "liveRan": True,
        "modelArms": "ran",
        "detected": result.get("detected") if g1 else None,
        "acceptedSeededError": result.get("acceptedSeededError") if g1 else None,
        "falseReject": result.get("falseReject") if g3 else None,
        "verdict": result.get("verdict"),
        "unparseable": result.get("unparseable"),
        "targetCalls": result.get("targetCalls"),
        "httpCalls": result.get("httpCalls"),
        "quietSuccess": None,
        "coversOriginalTaskClaim": False,
        "formalKernelChecked": False,
        "g1SupportedSeededError": g1,
        "g3Control": g3,
        "liveQualityDeltaInvented": False,
        "inventedDollarCost": False,
        "inventedFinalAccuracy": False,
    }


def score_cell(arm_id: str, task: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    expected = expected_by_arm(task, arm_id)
    if arm_id in DEFERRED_ARMS:
        if result.get("liveRan") is True or result.get("modelArms") == "ran":
            return _score_live_model_cell(arm_id, task, result)
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
            context_ok = (
                result.get("modelContextBytes") == 0
                and int(result.get("runtimeFeedbackBytes") or 0) > 0
                and result.get("modelContextBytesIsWrapperProjection") is True
            )
        elif expected.get("modelContextBytesZero") is False:
            context_ok = int(result.get("modelContextBytes") or 0) > 0
    if "receiptOutsideModelContext" in expected:
        receipt_ok = result.get("receiptOutsideModelContext") is bool(
            expected.get("receiptOutsideModelContext")
        )
    elif arm_id == ARM_B3:
        receipt_ok = result.get("receiptOutsideModelContext") is True
    repair_ok = True
    repair_matched = None
    unrelated_resubmit_matched = None
    repair = result.get("repair") if isinstance(result.get("repair"), dict) else None
    if arm_id == ARM_B3 and expected.get("repairAfterPrimaryStatus"):
        repair_ok = (
            repair is not None
            and repair.get("sameClaimCorrection") is True
            and repair.get("kind") == "same_claim_correction"
            and repair.get("primaryStatus") == expected.get("repairAfterPrimaryStatus")
            and bool(repair.get("quietSuccess")) is bool(expected.get("repairAfterQuietSuccess"))
            and repair.get("notALiveModelRepair") is True
        )
        repair_matched = repair_ok
    elif arm_id == ARM_B3 and expected.get("unrelatedValidResubmitAfterPrimaryStatus"):
        unrelated_resubmit_matched = (
            repair is not None
            and repair.get("sameClaimCorrection") is not True
            and repair.get("kind") == "unrelated_valid_resubmit"
            and repair.get("primaryStatus")
            == expected.get("unrelatedValidResubmitAfterPrimaryStatus")
            and bool(repair.get("quietSuccess"))
            is bool(expected.get("unrelatedValidResubmitAfterQuietSuccess"))
            and repair.get("notALiveModelRepair") is True
        )
        repair_ok = unrelated_resubmit_matched
        repair_matched = None
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
        "runtimeFeedbackBytes": result.get("runtimeFeedbackBytes"),
        "modelContextBytesIsWrapperProjection": result.get(
            "modelContextBytesIsWrapperProjection"
        ),
        "receiptOutsideModelContext": result.get("receiptOutsideModelContext"),
        "repairMatched": repair_matched,
        "unrelatedValidResubmitMatched": unrelated_resubmit_matched,
        "sameClaimCorrection": (
            None if repair is None else repair.get("sameClaimCorrection") is True
        ),
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


def _live_ran(cell: dict[str, Any] | None) -> bool:
    if cell is None:
        return False
    return cell.get("liveRan") is True or cell.get("modelArms") == "ran"


def _live_g1_stats(cells: list[dict[str, Any]], arm_id: str) -> dict[str, Any]:
    detected = 0
    accepted = 0
    unparseable = 0
    ran = 0
    for task_id in SUPPORTED_ERROR_TASKS:
        cell = _cell(cells, arm_id, task_id)
        if not _live_ran(cell):
            continue
        ran += 1
        scoring = (cell or {}).get("scoring") or {}
        if scoring.get("detected") is True:
            detected += 1
        if scoring.get("acceptedSeededError") is True:
            accepted += 1
        if scoring.get("unparseable") is True or (cell or {}).get("verdict") == "unparseable":
            unparseable += 1
    return {
        "detected": detected,
        "acceptedSeededErrors": accepted,
        "unparseable": unparseable,
        "ran": ran,
        "total": len(SUPPORTED_ERROR_TASKS),
        "allG1TasksRan": ran == len(SUPPORTED_ERROR_TASKS),
    }


def _live_g3_stats(cells: list[dict[str, Any]], arm_id: str) -> dict[str, Any]:
    false_rejects = 0
    ran = 0
    unparseable = 0
    for task_id in CONTROL_TASKS:
        cell = _cell(cells, arm_id, task_id)
        if not _live_ran(cell):
            continue
        ran += 1
        scoring = (cell or {}).get("scoring") or {}
        if scoring.get("falseReject") is True:
            false_rejects += 1
        if scoring.get("unparseable") is True or (cell or {}).get("verdict") == "unparseable":
            unparseable += 1
    return {
        "falseRejects": false_rejects,
        "ran": ran,
        "unparseable": unparseable,
        "total": len(CONTROL_TASKS),
        "allControlsRan": ran == len(CONTROL_TASKS),
    }


def _mean_total_tokens(cells: list[dict[str, Any]], arm_id: str) -> float | None:
    values: list[int] = []
    for cell in cells:
        if cell.get("arm") != arm_id or not _live_ran(cell):
            continue
        usage = cell.get("usage") if isinstance(cell.get("usage"), dict) else {}
        total = usage.get("totalTokens")
        if isinstance(total, int):
            values.append(total)
    if not values:
        return None
    return sum(values) / len(values)


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
    g5_unrelated: dict[str, bool] = {}
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
            unrelated = []
            for task_id in CONTROL_TASKS:
                cell = _cell(cells, arm_id, task_id)
                zeros.append(
                    cell is not None
                    and cell.get("modelContextBytes") == 0
                    and cell.get("quietSuccess") is True
                    and int(cell.get("runtimeFeedbackBytes") or 0) > 0
                    and cell.get("modelContextBytesIsWrapperProjection") is True
                )
            g4_zero[arm_id] = all(zeros) and bool(zeros)
            for task_id in SAME_CLAIM_REPAIR_TASKS:
                cell = _cell(cells, arm_id, task_id)
                scoring = (cell or {}).get("scoring") or {}
                repairs.append(scoring.get("repairMatched") is True)
            g5_repair[arm_id] = all(repairs) and bool(repairs)
            for task_id in UNRELATED_RESUBMIT_TASKS:
                cell = _cell(cells, arm_id, task_id)
                scoring = (cell or {}).get("scoring") or {}
                unrelated.append(scoring.get("unrelatedValidResubmitMatched") is True)
            g5_unrelated[arm_id] = all(unrelated) and bool(unrelated)

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
    live_g1_b0 = _live_g1_stats(cells, ARM_B0)
    live_g1_b1 = _live_g1_stats(cells, ARM_B1)
    live_g3_b0 = _live_g3_stats(cells, ARM_B0)
    live_g3_b1 = _live_g3_stats(cells, ARM_B1)
    live_present = bool(live_g1_b0["ran"] or live_g1_b1["ran"] or live_g3_b0["ran"] or live_g3_b1["ran"])
    g1_this_machine: dict[str, Any] = {
        "B2": {"detected": g1_b2["detected"], "total": g1_b2["total"], "rate": g1_rate_b2},
        "B3": {"detected": g1_b3["detected"], "total": g1_b3["total"], "rate": g1_rate_b3},
        "bindingProbes": {
            "detected": binding_detected,
            "total": binding_total,
            "rate": g1_binding_rate,
        },
    }
    if live_present:
        g1_this_machine["B0"] = live_g1_b0
        g1_this_machine["B1"] = live_g1_b1
    g1_four_arm_ready = (
        live_g1_b0["allG1TasksRan"]
        and live_g1_b1["allG1TasksRan"]
        and live_g1_b0["unparseable"] == 0
        and live_g1_b1["unparseable"] == 0
        and g1_b2["detected"] == g1_b2["total"]
        and g1_b3["detected"] == g1_b3["total"]
        and g1_b2["total"] > 0
    )
    g1_epoch2 = bool(g1_four_arm_ready and g1_rate_b2 >= 0.8 and g1_rate_b3 >= 0.8)
    g2_this: dict[str, Any] | None = None
    g2_epoch2 = False
    if live_g1_b0["allG1TasksRan"]:
        b0_accepted = live_g1_b0["acceptedSeededErrors"]
        b1_accepted = live_g1_b1["acceptedSeededErrors"] if live_g1_b1["allG1TasksRan"] else None
        verifier_accepted = 0  # B2/B3 matched seeded errors are detected, not accepted
        g2_this = {
            "B0AcceptedSeededErrors": b0_accepted,
            "B1AcceptedSeededErrors": b1_accepted,
            "B2B3AcceptedSeededErrors": verifier_accepted,
            "B0Unparseable": live_g1_b0["unparseable"],
            "B1Unparseable": live_g1_b1["unparseable"],
            "note": (
                "Counts only. No savings percentage. Vacuous if B0 accepted zero "
                "graded seeded errors. Unparseable is not treated as acceptance."
            ),
        }
        g2_epoch2 = (
            live_g1_b0["unparseable"] == 0
            and b0_accepted >= 1
            and verifier_accepted < b0_accepted
        )
    mean_b0 = _mean_total_tokens(cells, ARM_B0)
    mean_b1 = _mean_total_tokens(cells, ARM_B1)
    ten_percent: float | None = None
    if mean_b0 and mean_b0 > 0 and mean_b1 is not None:
        ten_percent = (mean_b1 - mean_b0) / mean_b0
    g3_this: dict[str, Any] = {
        "B2FalseRejects": g3_false[ARM_B2],
        "B3FalseRejects": g3_false[ARM_B3],
    }
    if live_present:
        g3_this["B0"] = live_g3_b0
        g3_this["B1"] = live_g3_b1
    g3_epoch2 = (
        g3_false[ARM_B2] == 0
        and g3_false[ARM_B3] == 0
        and live_g3_b0["allControlsRan"]
        and live_g3_b1["allControlsRan"]
    )

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
            thisMachine=g1_this_machine,
            thisMachineDoesNotMeetEpoch2Gate=not g1_epoch2,
            epoch2GateMet=g1_epoch2,
        ),
        "G2": _gate(
            "G2",
            thisMachine=g2_this,
            deferredBecause=(
                None
                if g2_this is not None
                else "requires matched live B0 vs B2/B3 accepted-error counts"
            ),
            thisMachineDoesNotMeetEpoch2Gate=not g2_epoch2,
            epoch2GateMet=g2_epoch2,
        ),
        "G3": _gate(
            "G3",
            thisMachine=g3_this,
            thisMachineDoesNotMeetEpoch2Gate=not g3_epoch2,
            epoch2GateMet=g3_epoch2,
        ),
        "G4": _gate(
            "G4",
            thisMachine={
                "B3QuietSuccessZeroReturnedContent": g4_zero.get(ARM_B3),
                "B3LibraryZeroBytesIsWrapperProjection": g4_zero.get(ARM_B3) is True,
                "productEvidenceCliQuietSuccessStdoutEmpty": (
                    probes.get("cliQuietSuccess", {}).get("stdoutEmpty") is True
                ),
                "tenPercentVsB0": ten_percent,
                "meanTotalTokensB0": mean_b0,
                "meanTotalTokensB1": mean_b1,
            },
            deferredBecause=(
                None
                if ten_percent is not None
                else "≤10% main-context growth vs B0 requires live model tokens"
            ),
            thisMachineDoesNotMeetEpoch2Gate=True,
            epoch2GateMet=False,
        ),
        "G5": _gate(
            "G5",
            thisMachine={
                "B3SameClaimSeededCorrectionMatched": g5_repair.get(ARM_B3),
                "B3SeededRepairHookMatched": g5_repair.get(ARM_B3),
                "B3UnrelatedValidResubmitReachedChecked": g5_unrelated.get(ARM_B3),
                "dimensionMismatchResubmitIsNotOriginalClaimRepair": True,
                "notALiveModelRepair": True,
            },
            thisMachineDoesNotMeetEpoch2Gate=True,
        ),
        "G6": _gate(
            "G6",
            thisMachine=None,
            deferredBecause="requires a stronger and a weaker live model under the same protocol",
            thisMachineDoesNotMeetEpoch2Gate=True,
            epoch2GateMet=False,
        ),
        "ids": list(GATE_IDS),
        "allRemainTargets": not any(
            [g1_epoch2, g2_epoch2, g3_epoch2]
        ),
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
    if probes.get("roundingSneak", {}).get("ok") is not True:
        problems.append("rounding-sneak adversarial probe did not falsify")
    if probes.get("unitScaleMismatch", {}).get("ok") is not True:
        problems.append("unit-scale-mismatch adversarial probe did not falsify")
    if probes.get("assumptionSwap", {}).get("ok") is not True:
        problems.append("assumption-swap adversarial probe did not falsify")
    if probes.get("stepNLegalWrong", {}).get("ok") is not True:
        problems.append("step-N legal-wrong adversarial probe did not falsify")

    targeted = bool(problems)
    live_ran = any(
        cell.get("liveRan") is True or cell.get("modelArms") == "ran" for cell in cells
    )
    epoch2_complete = all(
        gates.get(gate_id, {}).get("epoch2GateMet") is True for gate_id in GATE_IDS
    )
    if targeted:
        experiment_verdict = "targeted_fix"
        reasons = [
            "This smoke found a harness or obligation-runtime honesty/correctness problem.",
            "Do not promote method packs. Do not start H1. Epoch 2 is not complete.",
        ]
    elif live_ran:
        experiment_verdict = "live_b0_b1_ran"
        reasons = [
            "Live B0/B1 cells ran under a written call cap against a registered backend.",
            "B2/B3 still use the existing obligation runtime. No quality delta, dollar, or savings percentage was invented.",
            "G1–G6 are scored from this four-arm evidence; unmet gates stay targets.",
            "Do not promote method packs. Do not start H1.",
        ]
    else:
        experiment_verdict = "deterministic_b2_b3_scaffold_ran"
        reasons = [
            "Deterministic B2/B3 seeded corpus ran against the existing obligation runtime.",
            "B0/B1 remain model_arms=deferred. Live four-arm evidence is not invented.",
            "G1–G6 stay targets. This-machine B2/B3 detection is not Epoch 2 completion.",
            "Do not promote method packs. Do not start H1 from this scaffold.",
        ]
    return {
        "verdict": "targeted_fix" if targeted else "evidence_insufficient",
        "experimentVerdict": experiment_verdict,
        "promote": False,
        "targetedFix": targeted,
        "keepExperimental": True,
        "publicPromotion": False,
        "doNotStartH1": True,
        "packNotPromoted": True,
        "epoch2Complete": bool(epoch2_complete and not targeted),
        "modelArms": "ran" if live_ran else MODEL_ARMS_DEFERRED,
        "basedOnThisSmokeOnly": True,
        "notAStatisticalSaving": True,
        "problems": problems,
        "reasons": reasons,
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
