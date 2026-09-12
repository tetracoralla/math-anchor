"""Score pre-registered parameterized cost-smoke cells. Not a benefit percentage."""

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
    ARM_P_PACK,
    IN_FAMILY_TASKS,
    LIFECYCLE_VERIFIED,
    TASK_NEGATIVE,
    TASK_P0,
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
            "gosperCalled": None,
            "reconstructionDisabled": details.get("reconstructionDisabled"),
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
        "gosperCalled": result.get("gosperCalled"),
        "reconstructionDisabled": result.get("reconstructionDisabled"),
    }


def _exact_from_rational_payload(payload: object) -> str | None:
    if not isinstance(payload, dict) or not payload:
        return None
    try:
        return fraction_payload(rational_from_payload(payload))["exact"]
    except CalculatorError:
        return None


def score_cell(
    *,
    arm_id: str,
    task: dict[str, Any],
    summary: dict[str, Any],
    construction: dict[str, int] | None,
) -> dict[str, Any]:
    task_id = str(task["id"])
    expected = task.get("expectedExact")
    value_exact = summary.get("valueExact")
    status = summary.get("status")
    code = summary.get("errorCode")

    counted_as_solved = False
    wrong_acceptance = False
    applicability_misjudgment = False
    matched = False

    if task_id == TASK_NEGATIVE:
        counted_as_solved = False
        if arm_id == ARM_B0:
            matched = status == "ok" and value_exact is not None
            wrong_acceptance = False
        else:
            fail_closed = status in {"error", "inapplicable", "unsupported"} and code in {
                "E_UNSUPPORTED",
                "E_DOMAIN",
            }
            if status == "ok":
                wrong_acceptance = True
                applicability_misjudgment = True
            if status == "falsified":
                applicability_misjudgment = True
            matched = fail_closed and not wrong_acceptance
    else:
        matched = status == "ok" and value_exact == expected
        counted_as_solved = matched
        if status == "ok" and value_exact != expected:
            wrong_acceptance = True
        if status != "ok":
            applicability_misjudgment = True

    lifecycle = None
    call_alone = None
    if isinstance(summary.get("adoption"), dict):
        lifecycle = summary["adoption"].get("lifecycleEvidence")
        call_alone = summary["adoption"].get("callAloneIsNotAdoption")

    gosper_calls = (construction or {}).get("gosper_sum")
    construct_calls = (construction or {}).get("construct_antidifference")
    reconstructed = False
    if arm_id == ARM_P_PACK and task_id in IN_FAMILY_TASKS:
        reconstructed = bool(gosper_calls) or bool(construct_calls)

    return {
        "matchedPreRegisteredExpectation": matched,
        "countedAsSolved": counted_as_solved,
        "wrongAcceptance": wrong_acceptance,
        "applicabilityMisjudgment": applicability_misjudgment,
        "coversOriginalTaskClaim": False,
        "formalKernelChecked": summary.get("formalKernelChecked") is True,
        "lifecycleEvidence": lifecycle,
        "callAloneIsNotAdoption": call_alone,
        "semanticAdoption": False,
        "baselineEmbedded": bool(summary.get("baselineEmbedded")),
        "gosperCalledJsonFlag": summary.get("gosperCalled"),
        "reconstructionDisabled": summary.get("reconstructionDisabled"),
        "constructionTrace": {
            "gosper_sum": gosper_calls,
            "construct_antidifference": construct_calls,
        },
        "reconstructedOnPackArm": reconstructed,
        "semanticAdoptionFromLifecycleEvidenceAlone": False,
    }


def decide(
    cells: list[dict[str, Any]],
    *,
    stripped: dict[str, Any],
    fair_baselines: dict[str, Any],
) -> dict[str, Any]:
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
        if scoring.get("baselineEmbedded") and cell.get("arm") in {ARM_B1, ARM_P_PACK}:
            problems.append(f"{label}: B0 was embedded (compare_baseline leaked into the arm)")
        if not scoring.get("matchedPreRegisteredExpectation"):
            problems.append(f"{label}: did not match the pre-registered expectation")
        if cell.get("trialsDisagree"):
            problems.append(f"{label}: first and repeat trials disagree")
        if scoring.get("reconstructedOnPackArm"):
            problems.append(f"{label}: P-pack called gosper_sum or construct_antidifference")
        if cell.get("arm") == ARM_P_PACK and cell.get("task") in IN_FAMILY_TASKS:
            if scoring.get("gosperCalledJsonFlag") is not False:
                problems.append(f"{label}: gosperCalled JSON flag was not false")
            if scoring.get("reconstructionDisabled") is not True:
                problems.append(f"{label}: reconstructionDisabled was not true")
        if cell.get("arm") == ARM_B1 and cell.get("task") in IN_FAMILY_TASKS:
            trace = scoring.get("constructionTrace") or {}
            if not trace.get("construct_antidifference") and not trace.get("gosper_sum"):
                problems.append(f"{label}: B1 did not construct (trace is the probe)")
        if not p0_replay_lifecycle_ok(cell):
            problems.append(f"{label}: P0 replay minted cross-task lifecycle evidence")

    if stripped.get("refused") is not True:
        problems.append("stripped parametricAntidifference payload did not refuse")
    if fair_baselines.get("b0ValueExact") != "44100" or fair_baselines.get("b1ValueExact") != "44100":
        problems.append("fair B0/B1 were crippled on out-of-family k^3")
    if fair_baselines.get("pPackRefused") is not True:
        problems.append("P-pack did not refuse out-of-family k^3")

    observed, observed_note = _slower_checked_path_observation(cells)
    pack_vs_b1, pack_vs_b1_note = _pack_vs_b1_observation(cells)
    b0_matches = _b0_already_matches(cells)

    if problems:
        return {
            "verdict": "targeted_fix",
            "promote": False,
            "targetedFix": True,
            "keepExperimental": True,
            "publicPromotion": False,
            "basedOnThisSmokeOnly": True,
            "notAStatisticalSaving": True,
            "doNotStartH1": True,
            "problems": problems,
            "reasons": [
                "This smoke found a harness or vertical honesty/correctness problem.",
                "Do not promote the pack. Do not start H1 from this result.",
            ],
            "next": "targeted fix on this vertical; keep experimental; no Host work",
            "observedSlowerCheckedPath": observed,
            "observedSlowerCheckedPathNote": observed_note,
            "observedPackRepeatFasterThanB1": pack_vs_b1,
            "observedPackRepeatFasterThanB1Note": pack_vs_b1_note,
            "b0AlreadyMatchesInFamily": b0_matches,
        }

    reasons = [
        "Pre-registered (c,a,b) cells on one family are an integration smoke, not an overall benefit percentage.",
        "No model calls, no token accounting, and no dollar prices. Do not invent a savings percentage.",
        "equalBudget here is zero model calls on every arm; it does not claim equal wall-clock, memory, or dollar cost.",
        "Promotion is forbidden in this smoke even when cells are green. Do not start H1.",
        "lifecycleEvidence=cross-task-use-evidence is not semantic adoption.",
        "P-pack avoids reconstructing this G; identity checks still run. Construction is what was saved, not the proof obligation.",
        "B1 on the same (c,a,b) already produces the number by constructing, so the pack is not a unique closed form.",
    ]
    if b0_matches:
        reasons.insert(
            1,
            "B0 (SymPy summation) already matches every in-family exact value and is the simpler path when only a number is required.",
        )

    return {
        "verdict": "evidence_insufficient",
        "promote": False,
        "targetedFix": False,
        "keepExperimental": True,
        "publicPromotion": False,
        "basedOnThisSmokeOnly": True,
        "notAStatisticalSaving": True,
        "doNotStartH1": True,
        "problems": [],
        "reasons": reasons,
        "next": (
            "Keep experimental. Do not start H1. Do not promote. A later experiment "
            "is only justified if it targets work B0 cannot already do on this family."
        ),
        "observedSlowerCheckedPath": observed,
        "observedSlowerCheckedPathNote": observed_note,
        "observedPackRepeatFasterThanB1": pack_vs_b1,
        "observedPackRepeatFasterThanB1Note": pack_vs_b1_note,
        "b0AlreadyMatchesInFamily": b0_matches,
    }


def p0_replay_lifecycle_ok(cell: dict[str, Any]) -> bool:
    if cell.get("arm") != ARM_P_PACK or cell.get("task") != TASK_P0:
        return True
    scoring = cell.get("scoring") or {}
    return scoring.get("lifecycleEvidence") == LIFECYCLE_VERIFIED


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
        for arm in (ARM_B1, ARM_P_PACK):
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
            "Repeat-trial in-process latency for B1/P-pack was higher than B0 on every "
            "in-family task in this report. Not an isolated cold start and not a dollar cost."
        )
    elif observed is False:
        note = (
            "Measured in-process latencies do not support claiming the checked path is slower than B0."
        )
    else:
        note = "No measured latencies; slower-checked-path is not an observation."
    return observed, note


def _pack_vs_b1_observation(cells: list[dict[str, Any]]) -> tuple[bool | None, str]:
    by_task: dict[str, dict[str, float]] = {}
    for cell in cells:
        arm = cell.get("arm")
        task = cell.get("task")
        if task not in IN_FAMILY_TASKS or not isinstance(arm, str):
            continue
        samples = _cell_latency_samples(cell)
        if not samples:
            continue
        by_task.setdefault(str(task), {})[arm] = samples[-1]
    comparisons: list[bool] = []
    for arms in by_task.values():
        b1 = arms.get(ARM_B1)
        pack = arms.get(ARM_P_PACK)
        if b1 is None or pack is None:
            continue
        comparisons.append(pack < b1)
    if not comparisons:
        return None, "No measured latencies; pack-vs-B1 is not an observation."
    if all(comparisons):
        return True, (
            "P-pack repeat in-process latency was lower than B1 on every in-family task. "
            "This is not a dollar saving and not a promotion case."
        )
    return False, (
        "Measured in-process latencies do not support claiming P-pack is faster than B1."
    )


def _b0_already_matches(cells: list[dict[str, Any]]) -> bool:
    expected_ok = 0
    matched = 0
    for cell in cells:
        if cell.get("arm") != ARM_B0 or cell.get("task") not in IN_FAMILY_TASKS:
            continue
        expected_ok += 1
        scoring = cell.get("scoring") or {}
        if scoring.get("matchedPreRegisteredExpectation") is True:
            matched += 1
    return expected_ok > 0 and matched == expected_ok
