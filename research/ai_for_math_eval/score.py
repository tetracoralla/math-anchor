"""Score pre-registered A4 cells. Smoke is not an overall benefit percentage."""

from __future__ import annotations

from typing import Any

from math_anchor.errors import CalculatorError

from research.polynomial_finite_sum_proposal.polynomials import (
    fraction_payload,
    rational_from_payload,
)

from .protocol import (
    ARM_B0,
    ARM_B1,
    ARM_B2,
    LIFECYCLE_CROSS_TASK,
    LIFECYCLE_VERIFIED,
    TASK_CUBES,
    TASK_NEGATIVE,
    TASK_T1,
)


REUSE_CHAIN_STEPS = (
    "retrieve",
    "instantiate",
    "verify_difference_identity",
    "combine_with_infrastructure_telescoping",
)


def result_summary(result: dict[str, Any] | None, error: BaseException | None) -> dict[str, Any]:
    if error is not None:
        details = getattr(error, "details", None)
        details = details if isinstance(details, dict) else {}
        return {
            "status": "inapplicable" if details.get("applicability") == "rejected" else "error",
            "kind": None,
            "valueExact": None,
            "errorCode": getattr(error, "code", None),
            "errorMessage": getattr(error, "message", str(error)),
            "applicability": details.get("applicability"),
            "applicabilityReason": details.get("reason"),
            "formalKernelChecked": False,
            "constructor": None,
            "identityStatus": None,
            "adoption": None,
            "chainSteps": [],
            "valueEnteredLaterStepsExact": None,
            "methodPackId": details.get("methodPackId"),
            "baselineEmbedded": False,
        }
    assert result is not None
    identity = result.get("identity") if isinstance(result.get("identity"), dict) else {}
    verification = result.get("verification") if isinstance(result.get("verification"), dict) else {}
    adoption = result.get("adoption") if isinstance(result.get("adoption"), dict) else None
    value = result.get("value") if isinstance(result.get("value"), dict) else {}
    chain = result.get("chain") if isinstance(result.get("chain"), list) else []
    entered = None
    steps: list[str] = []
    for item in chain:
        if not isinstance(item, dict):
            continue
        step = item.get("step")
        if isinstance(step, str):
            steps.append(step)
        if step == "combine_with_infrastructure_telescoping":
            payload = item.get("valueEnteredLaterSteps")
            if isinstance(payload, dict):
                entered = _exact_from_rational_payload(payload)
    pack = result.get("methodPack") if isinstance(result.get("methodPack"), dict) else {}
    return {
        "status": result.get("status"),
        "kind": result.get("kind"),
        "valueExact": _exact_from_rational_payload(value),
        "errorCode": None,
        "errorMessage": None,
        "applicability": None,
        "applicabilityReason": None,
        "formalKernelChecked": bool(result.get("formalKernelChecked")),
        "constructor": result.get("constructor"),
        "identityStatus": identity.get("status") or verification.get("status"),
        "adoption": (
            {
                "used": adoption.get("used"),
                "lifecycleEvidence": adoption.get("lifecycleEvidence"),
                "callAloneIsNotAdoption": adoption.get("callAloneIsNotAdoption"),
                "extractionTaskIdNotReusedAsAnswer": adoption.get("extractionTaskIdNotReusedAsAnswer"),
                "taskId": adoption.get("taskId"),
                "methodId": adoption.get("methodId"),
            }
            if adoption is not None
            else None
        ),
        "chainSteps": steps,
        "valueEnteredLaterStepsExact": entered,
        "methodPackId": pack.get("id"),
        "baselineEmbedded": "baseline" in result,
    }


def _exact_from_rational_payload(payload: object) -> str | None:
    if not isinstance(payload, dict) or not payload:
        return None
    try:
        return fraction_payload(rational_from_payload(payload))["exact"]
    except CalculatorError:
        return None


def coverage_honesty(coverage: dict[str, Any] | None) -> dict[str, Any]:
    if coverage is None:
        return {
            "recorded": False,
            "coversOriginalTaskClaim": False,
            "procedureEstablishedFiniteSumValue": False,
            "generatedObligationIds": [],
            "source": None,
            "formalKernelChecked": False,
            "propositionFalsified": False,
            "unsupportedTreatedAsCounterexample": False,
        }
    claim = coverage.get("claimCoverage") if isinstance(coverage.get("claimCoverage"), dict) else {}
    outcome = coverage.get("outcome") if isinstance(coverage.get("outcome"), dict) else {}
    honesty = coverage.get("honesty") if isinstance(coverage.get("honesty"), dict) else {}
    generated = coverage.get("generatedObligations") if isinstance(coverage.get("generatedObligations"), list) else []
    return {
        "recorded": True,
        "coversOriginalTaskClaim": claim.get("coversOriginalTaskClaim"),
        "procedureEstablishedFiniteSumValue": claim.get("procedureEstablishedFiniteSumValue"),
        "generatedObligationIds": [item.get("id") for item in generated if isinstance(item, dict)],
        "source": coverage.get("source"),
        "formalKernelChecked": honesty.get("formalKernelChecked"),
        "propositionFalsified": outcome.get("propositionFalsified"),
        "unsupportedTreatedAsCounterexample": outcome.get("unsupportedTreatedAsCounterexample"),
        "allSubmittedObligationsChecked": claim.get("allSubmittedObligationsChecked"),
    }


def score_cell(
    *,
    arm_id: str,
    task: dict[str, Any],
    summary: dict[str, Any],
    honesty: dict[str, Any],
) -> dict[str, Any]:
    task_id = str(task["id"])
    expected = task.get("expectedExact")
    value_exact = summary.get("valueExact")
    status = summary.get("status")
    code = summary.get("errorCode")
    proposition_false = honesty.get("propositionFalsified") is True
    treated_as_counterexample = honesty.get("unsupportedTreatedAsCounterexample") is True
    covers_claim = honesty.get("coversOriginalTaskClaim") is True
    formal_kernel = summary.get("formalKernelChecked") is True or honesty.get("formalKernelChecked") is True

    counted_as_solved = False
    wrong_acceptance = False
    applicability_misjudgment = False
    matched = False

    if task_id == TASK_NEGATIVE:
        counted_as_solved = False
        if arm_id == ARM_B0:
            matched = not proposition_false and not treated_as_counterexample and not covers_claim
            if status == "ok" and value_exact is not None:
                wrong_acceptance = False
        else:
            fail_closed = status in {"error", "inapplicable", "unsupported"} and code in {
                "E_UNSUPPORTED",
                "E_DOMAIN",
            }
            if status == "ok":
                wrong_acceptance = True
                applicability_misjudgment = True
            if proposition_false or treated_as_counterexample or status == "falsified":
                applicability_misjudgment = True
            matched = fail_closed and not proposition_false and not treated_as_counterexample and not wrong_acceptance
    else:
        matched = status == "ok" and value_exact == expected
        counted_as_solved = matched
        if status == "ok" and value_exact != expected:
            wrong_acceptance = True
        if status != "ok":
            applicability_misjudgment = True

    reuse = detect_reuse_signal(arm_id=arm_id, task_id=task_id, expected_exact=expected, summary=summary)
    lifecycle = None
    call_alone = None
    if isinstance(summary.get("adoption"), dict):
        lifecycle = summary["adoption"].get("lifecycleEvidence")
        call_alone = summary["adoption"].get("callAloneIsNotAdoption")

    return {
        "matchedPreRegisteredExpectation": matched,
        "countedAsSolved": counted_as_solved,
        "wrongAcceptance": wrong_acceptance,
        "applicabilityMisjudgment": applicability_misjudgment,
        "coversOriginalTaskClaim": honesty.get("coversOriginalTaskClaim"),
        "formalKernelChecked": formal_kernel,
        "propositionFalsified": proposition_false,
        "unsupportedTreatedAsCounterexample": treated_as_counterexample,
        "reuseSignal": reuse,
        "lifecycleEvidence": lifecycle,
        "callAloneIsNotAdoption": call_alone,
        "semanticAdoption": False,
        "baselineEmbedded": bool(summary.get("baselineEmbedded")),
    }


def detect_reuse_signal(
    *,
    arm_id: str,
    task_id: str,
    expected_exact: object,
    summary: dict[str, Any],
) -> dict[str, Any]:
    if arm_id != ARM_B2:
        return {"present": False, "reason": "reuse is scored only on B2"}
    if task_id != TASK_CUBES:
        reason = (
            "B2 on T1 is extraction-task replay, not held-out reuse"
            if task_id == TASK_T1
            else "reuse is scored only on the held-out cubes task"
        )
        return {"present": False, "reason": reason}

    adoption = summary.get("adoption") if isinstance(summary.get("adoption"), dict) else {}
    steps = summary.get("chainSteps") if isinstance(summary.get("chainSteps"), list) else []
    missing: list[str] = []
    if summary.get("status") != "ok":
        missing.append("ok_status")
    if summary.get("valueExact") != expected_exact:
        missing.append("held_out_value")
    for required in REUSE_CHAIN_STEPS:
        if required not in steps:
            missing.append(required)
    if summary.get("valueEnteredLaterStepsExact") != expected_exact:
        missing.append("value_entered_later_step")
    if adoption.get("lifecycleEvidence") != LIFECYCLE_CROSS_TASK:
        missing.append("lifecycleEvidence=cross-task-use-evidence")
    if adoption.get("extractionTaskIdNotReusedAsAnswer") is not True:
        missing.append("extractionTaskIdNotReusedAsAnswer")
    if adoption.get("callAloneIsNotAdoption") is not True:
        missing.append("callAloneIsNotAdoption")
    if adoption.get("used") is not True:
        missing.append("adoption.used")
    if summary.get("methodPackId") is None:
        missing.append("retrieve_named_pack")

    present = not missing
    return {
        "present": present,
        "reason": (
            "B2 retrieve/instantiate/check/bind on held-out cubes; lifecycleEvidence is not semantic adoption"
            if present
            else "missing: " + ", ".join(missing)
        ),
        "missing": missing,
        "lifecycleEvidence": adoption.get("lifecycleEvidence"),
        "callAloneIsNotAdoption": adoption.get("callAloneIsNotAdoption"),
        "semanticAdoption": False,
    }


def should_run_b2_minus(b2_cubes_score: dict[str, Any] | None) -> tuple[bool, str]:
    if not isinstance(b2_cubes_score, dict):
        return False, "B2 held-out cubes cell missing; B2-minus skipped"
    signal = b2_cubes_score.get("reuseSignal") if isinstance(b2_cubes_score.get("reuseSignal"), dict) else {}
    if signal.get("present") is True:
        return True, "B2 held-out cubes showed a reuse signal (apply chain); B2-minus drops the pack on that task"
    reason = signal.get("reason") or "B2 held-out cubes did not show a reuse signal"
    return False, f"B2-minus skipped: {reason}"


def decide(cells: list[dict[str, Any]], b2_minus: dict[str, Any]) -> dict[str, Any]:
    problems: list[str] = []
    for cell in cells:
        scoring = cell.get("scoring") or {}
        label = f"{cell.get('arm')}×{cell.get('task')}"
        if scoring.get("wrongAcceptance"):
            problems.append(f"{label}: wrong acceptance")
        if scoring.get("applicabilityMisjudgment"):
            problems.append(f"{label}: applicability misjudgment")
        if cell.get("task") == TASK_NEGATIVE and scoring.get("countedAsSolved"):
            problems.append(f"{label}: negative counted as solved")
        if scoring.get("coversOriginalTaskClaim") is True:
            problems.append(f"{label}: coversOriginalTaskClaim was true")
        if scoring.get("formalKernelChecked"):
            problems.append(f"{label}: formal_kernel_checked was true")
        if scoring.get("baselineEmbedded") and cell.get("arm") in {ARM_B1, ARM_B2}:
            problems.append(f"{label}: B0 was embedded (compare_baseline leaked into the arm)")
        if not scoring.get("matchedPreRegisteredExpectation"):
            problems.append(f"{label}: did not match the pre-registered expectation")
        if cell.get("trialsDisagree"):
            problems.append(f"{label}: first and repeat trials disagree")

    observed, observed_note = _slower_checked_path_observation(cells)
    promote = False
    if problems:
        return {
            "verdict": "targeted_fix",
            "promote": promote,
            "targetedFix": True,
            "keepExperimental": True,
            "publicPromotion": False,
            "basedOnThisSmokeOnly": True,
            "notAStatisticalSaving": True,
            "problems": problems,
            "reasons": [
                "This smoke found a harness or vertical honesty/correctness problem.",
                "Do not promote the pack. Do not start H1 from this result.",
            ],
            "next": "targeted fix on this vertical; keep experimental; no Host work",
            "observedSlowerCheckedPath": observed,
            "observedSlowerCheckedPathNote": observed_note,
        }

    b2_minus_same = b2_minus.get("ran") is True and b2_minus.get("valueUnchanged") is True
    reasons = [
        "n=3 pre-registered tasks on one family is an integration smoke, not an overall benefit percentage.",
        "In-domain T1 and cubes are already computed by B0 (SymPy summation).",
        "B1/B2 add independent checking and fail-closed domain; they are not a reliability lift on T1/cubes values.",
        "lifecycleEvidence=cross-task-use-evidence is not semantic adoption.",
        "No model calls, no token accounting, and no dollar prices.",
        "equalBudget here is zero model calls on every arm; it does not claim equal wall-clock, memory, or dollar cost.",
        "Promotion is forbidden in this smoke even when cells are green.",
    ]
    if b2_minus_same:
        reasons.insert(
            3,
            "B2-minus still produced 44100 without the pack, so pack apply is not a unique closed form on cubes.",
        )
    elif b2_minus.get("ran") is not True:
        reasons.insert(3, f"B2-minus did not run: {b2_minus.get('skipReason')}")

    return {
        "verdict": "evidence_insufficient",
        "promote": False,
        "targetedFix": False,
        "keepExperimental": True,
        "publicPromotion": False,
        "basedOnThisSmokeOnly": True,
        "notAStatisticalSaving": True,
        "problems": [],
        "reasons": reasons,
        "next": (
            "Keep experimental. Do not start H1. Expand the neighborhood only if a later "
            "authorized experiment shows work B0 cannot already do on this family."
        ),
        "observedSlowerCheckedPath": observed,
        "observedSlowerCheckedPathNote": observed_note,
    }


def _cell_latency_samples(cell: dict[str, Any]) -> list[float]:
    latency = cell.get("latencyMs")
    if not isinstance(latency, dict):
        return []
    samples: list[float] = []
    for key in ("first", "repeat"):
        value = latency.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        samples.append(float(value))
    return samples


def observed_slower_checked_path(cells: list[dict[str, Any]]) -> bool | None:
    """True/False from measured latencies; None when there is nothing to observe."""

    by_task: dict[str, dict[str, float]] = {}
    for cell in cells:
        arm = cell.get("arm")
        task = cell.get("task")
        if not isinstance(arm, str) or not isinstance(task, str):
            continue
        if task == TASK_NEGATIVE:
            continue
        samples = _cell_latency_samples(cell)
        if not samples:
            continue
        by_task.setdefault(task, {})[arm] = samples[-1]
    comparisons: list[bool] = []
    for arms in by_task.values():
        baseline = arms.get(ARM_B0)
        if baseline is None:
            continue
        for arm in (ARM_B1, ARM_B2):
            checked = arms.get(arm)
            if checked is None:
                continue
            comparisons.append(checked > baseline)
    if not comparisons:
        return None
    return all(comparisons)


def _slower_checked_path_observation(cells: list[dict[str, Any]]) -> tuple[bool | None, str]:
    observed = observed_slower_checked_path(cells)
    if observed is True:
        note = (
            "Repeat-trial in-process latency for B1/B2 was higher than B0 on every "
            "comparable task in this report. Not an isolated cold start and not a dollar cost."
        )
    elif observed is False:
        note = (
            "Measured in-process latencies do not support claiming the checked path is slower."
        )
    else:
        note = "No measured latencies; slower-checked-path is not an observation."
    return observed, note


def t1_replay_lifecycle_ok(cell: dict[str, Any]) -> bool:
    if cell.get("arm") != ARM_B2 or cell.get("task") != TASK_T1:
        return True
    scoring = cell.get("scoring") or {}
    return scoring.get("lifecycleEvidence") == LIFECYCLE_VERIFIED and scoring.get("reuseSignal", {}).get("present") is not True
