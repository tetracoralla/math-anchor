"""Score pre-registered reuse-benefit cells. Three judgments stay separate."""

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
    ARM_B_CODEGEN,
    ARM_B_TEMPLATE,
    ARM_P_PACK,
    B0_HARMONIC_EXACT,
    HELD_OUT_TASKS,
    IN_FAMILY_TASKS,
    KARR_ARMS,
    KARR_REVERSED_EXACT,
    LIFECYCLE_VERIFIED,
    NEVER_SOLVED_TASKS,
    PRIMARY_ARMS,
    TASK_NEGATIVE,
    TASK_P0,
    TASK_REVERSED,
    expected_exact_if_computed,
)

CONSTRUCTION_PROBE = "wrap"


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
            "stepsExecuted": [],
            "valueEnteredLaterStepsExact": None,
            "methodPackId": details.get("methodPackId"),
            "baselineEmbedded": False,
            "gosperCalled": None,
            "reconstructionDisabled": details.get("reconstructionDisabled"),
            "usedSavedContent": False,
            "independentChecker": False,
            "floatingApproximation": False,
            "karrReversedBoundsAccepted": False,
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
    executed = result.get("stepsExecuted")
    if isinstance(executed, list) and executed:
        steps = [str(item) for item in executed if isinstance(item, str)]
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
        "stepsExecuted": steps,
        "valueEnteredLaterStepsExact": entered,
        "methodPackId": pack.get("id"),
        "baselineEmbedded": "baseline" in result,
        "gosperCalled": result.get("gosperCalled"),
        "reconstructionDisabled": result.get("reconstructionDisabled"),
        "usedSavedContent": bool(result.get("usedSavedContent")),
        "independentChecker": bool(result.get("independentChecker")),
        "floatingApproximation": bool(result.get("floatingApproximation")),
        "karrReversedBoundsAccepted": bool(result.get("karrReversedBoundsAccepted")),
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
            expected_harmonic = expected_exact_if_computed(task, arm_id) or B0_HARMONIC_EXACT
            matched = status == "ok" and value_exact == expected_harmonic
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
    elif task_id == TASK_REVERSED:
        counted_as_solved = False
        if arm_id in KARR_ARMS:
            expected_karr = expected_exact_if_computed(task, arm_id) or KARR_REVERSED_EXACT
            matched = status == "ok" and value_exact == expected_karr
            wrong_acceptance = False
        else:
            fail_closed = status in {"error", "inapplicable", "unsupported"} and code in {
                "E_UNSUPPORTED",
                "E_DOMAIN",
            }
            if status == "ok":
                wrong_acceptance = True
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
        "usedSavedContent": bool(summary.get("usedSavedContent")),
        "independentChecker": bool(summary.get("independentChecker")),
        "floatingApproximation": bool(summary.get("floatingApproximation")),
        "stepsExecuted": list(summary.get("stepsExecuted") or []),
        "constructionProbe": CONSTRUCTION_PROBE,
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
    wrong_g: dict[str, Any],
    fair_baselines: dict[str, Any],
    codegen_skip: dict[str, Any],
) -> dict[str, Any]:
    problems: list[str] = []
    for cell in cells:
        scoring = cell.get("scoring") or {}
        label = f"{cell.get('arm')}×{cell.get('task')}"
        if scoring.get("wrongAcceptance"):
            problems.append(f"{label}: wrong acceptance")
        if scoring.get("applicabilityMisjudgment"):
            problems.append(f"{label}: applicability misjudgment")
        if cell.get("task") in NEVER_SOLVED_TASKS and scoring.get("countedAsSolved"):
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
        if scoring.get("floatingApproximation"):
            problems.append(f"{label}: floating approximation labelled as a result")
        if cell.get("arm") == ARM_P_PACK and cell.get("task") in IN_FAMILY_TASKS:
            if scoring.get("gosperCalledJsonFlag") is not False:
                problems.append(f"{label}: gosperCalled JSON flag was not false")
            if scoring.get("reconstructionDisabled") is not True:
                problems.append(f"{label}: reconstructionDisabled was not true")
            if not scoring.get("usedSavedContent"):
                problems.append(f"{label}: P-pack in-family cell did not use saved content")
        if cell.get("arm") in {ARM_B_TEMPLATE, ARM_B_CODEGEN} and cell.get("task") in IN_FAMILY_TASKS:
            trace = scoring.get("constructionTrace") or {}
            if trace.get("gosper_sum") or trace.get("construct_antidifference"):
                problems.append(f"{label}: cache/codegen baseline reconstructed via Gosper")
            if not scoring.get("usedSavedContent"):
                problems.append(f"{label}: cache/codegen baseline did not use saved G")
        if cell.get("arm") == ARM_B1 and cell.get("task") in IN_FAMILY_TASKS:
            trace = scoring.get("constructionTrace") or {}
            if not trace.get("construct_antidifference") and not trace.get("gosper_sum"):
                problems.append(f"{label}: B1 did not construct (trace is the probe)")
        if not p0_replay_lifecycle_ok(cell):
            problems.append(f"{label}: P0 replay minted cross-task lifecycle evidence")

    if stripped.get("refused") is not True:
        problems.append("stripped parametricAntidifference payload did not refuse")
    if wrong_g.get("failClosed") is not True:
        problems.append("wrong saved G did not fail closed")
    if wrong_g.get("emittedValue") is True:
        problems.append("wrong saved G emitted a finite-sum value")
    if fair_baselines.get("b0ValueExact") != "44100" or fair_baselines.get("b1ValueExact") != "44100":
        problems.append("fair B0/B1 were crippled on out-of-family k^3")
    if fair_baselines.get("pPackRefused") is not True:
        problems.append("P-pack did not refuse out-of-family k^3")
    if fair_baselines.get("templateRefused") is not True:
        problems.append("B_template did not refuse out-of-family k^3")
    if fair_baselines.get("codegenRefused") is not True:
        problems.append("B_codegen did not refuse out-of-family k^3")
    c_probe = (codegen_skip.get("sympy.utilities.codegen.C") or {}).get("probe") or {}
    if c_probe.get("available") is True and c_probe.get("emitsFloatingType") is not True:
        problems.append("C codegen probe did not observe a floating type; refusing to treat it as exact")
    if (codegen_skip.get("sympy.utilities.codegen.C") or {}).get("used") is True:
        problems.append("floating C codegen was used")

    observations = _utility_observations(cells)
    judgments = three_judgments(
        cells,
        stripped=stripped,
        wrong_g=wrong_g,
        fair_baselines=fair_baselines,
        observations=observations,
        problems=problems,
    )

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
            "fasterThanColdGosperIsNotUniqueness": True,
            "problems": problems,
            "reasons": [
                "This smoke found a harness or vertical honesty/correctness problem.",
                "Do not promote the pack. Do not start H1 from this result.",
            ],
            "next": "targeted fix on this vertical; keep experimental; no Host work",
            "judgments": judgments,
            **observations,
        }

    reasons = [
        "Pre-registered (c,a,b) cells on one family are an integration smoke, not an overall benefit percentage.",
        "No model calls, no token accounting, and no dollar prices. Do not invent a savings percentage.",
        "equalBudget here is zero model calls on every arm; it does not claim equal wall-clock, memory, or dollar cost.",
        "Promotion is forbidden in this smoke even when cells are green. Do not start H1.",
        "lifecycleEvidence=cross-task-use-evidence is not semantic adoption.",
        "Faster than cold Gosper (B1) is not Math Anchor uniqueness: B_template and B_codegen also skip construction.",
        "Trustworthiness, behavior, and utility are recorded separately and are not one success flag.",
    ]
    if observations.get("b0AlreadyMatchesInFamily"):
        reasons.insert(
            1,
            "B0 (SymPy summation) already matches every in-family exact value and is the simpler path when only a number is required.",
        )
    if observations.get("bTemplateAlreadyMatchesP"):
        reasons.insert(
            2,
            "B_template already matches P-pack on every in-family exact value while skipping construction. The pack's extra work is identity checking, not a unique closed form.",
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
        "fasterThanColdGosperIsNotUniqueness": True,
        "problems": [],
        "reasons": reasons,
        "next": (
            "Keep experimental. Do not start H1. Do not promote. Strong baselines already "
            "reuse the same G; the pack does not show a net utility win on this family."
        ),
        "judgments": judgments,
        **observations,
    }


def three_judgments(
    cells: list[dict[str, Any]],
    *,
    stripped: dict[str, Any],
    wrong_g: dict[str, Any],
    fair_baselines: dict[str, Any],
    observations: dict[str, Any],
    problems: list[str],
) -> dict[str, Any]:
    """Return three independent judgments. Never collapse them into one success flag."""

    trust = _trust_from_probes(
        cells,
        stripped=stripped,
        wrong_g=wrong_g,
        fair_baselines=fair_baselines,
    )
    p_held_out_uses_saved = _p_held_out_uses_saved_content(cells)
    behavior_ok = p_held_out_uses_saved is True

    if trust["fails"]:
        trust_verdict = "fails"
    elif trust["holds"]:
        trust_verdict = "holds_in_declared_domain"
    else:
        trust_verdict = "evidence_insufficient"

    if p_held_out_uses_saved is False:
        behavior_verdict = "re_solves"
    elif behavior_ok:
        behavior_verdict = "pack_uses_saved_content"
    else:
        behavior_verdict = "evidence_insufficient"

    if observations.get("bTemplateAlreadyMatchesP"):
        utility_verdict = "no_net_benefit_vs_strong_baselines"
    else:
        utility_verdict = "evidence_insufficient"
    _ = problems

    return {
        "notCollapsedIntoOneSuccess": True,
        "trustworthiness": {
            "verdict": trust_verdict,
            "notBehavior": True,
            "notUtility": True,
            "means": "the method and instances hold under the declared domain",
            "classifiedFromStructuredProbes": True,
            "probes": trust["probes"],
            "evidence": trust["evidence"],
        },
        "behavior": {
            "verdict": behavior_verdict,
            "notTrustworthiness": True,
            "notUtility": True,
            "means": "the next task uses saved content instead of reconstructing G",
            "constructionProbe": CONSTRUCTION_PROBE,
            "evidence": _behavior_evidence(cells, p_held_out_uses_saved),
            "packReuseIsNotUniqueVsTemplate": True,
        },
        "utility": {
            "verdict": utility_verdict,
            "notTrustworthiness": True,
            "notBehavior": True,
            "means": "net benefit versus strong baselines (CAS, cache/template, exact codegen)",
            "mayBeNegative": True,
            "fasterThanColdGosperIsNotUniqueness": True,
            "b0AlreadyMatchesInFamily": observations.get("b0AlreadyMatchesInFamily"),
            "bTemplateAlreadyMatchesP": observations.get("bTemplateAlreadyMatchesP"),
            "bCodegenAlreadyMatchesP": observations.get("bCodegenAlreadyMatchesP"),
            "observedPackRepeatFasterThanB1": observations.get("observedPackRepeatFasterThanB1"),
            "observedPackRepeatFasterThanTemplate": observations.get("observedPackRepeatFasterThanTemplate"),
            "observedSlowerCheckedPathThanB0": observations.get("observedSlowerCheckedPath"),
            "evidence": [
                "B0 already matches in-family exact values",
                "B_template already matches P-pack values while skipping construction",
                "B_codegen matches the same values with an exact QQ evaluator",
                "P-pack still runs applicability plus general and instance identity checks",
                "reversed-bound fail-closed is A1 convention (B1 already has it); not pack-unique versus B1",
                "no dollar costs; no savings percentage",
            ],
        },
    }


def _tri_state(value: object) -> bool | None:
    if value is True:
        return True
    if value is False:
        return False
    return None


def _p_pack_task_matched(cells: list[dict[str, Any]], task_id: str) -> bool | None:
    found = [cell for cell in cells if cell.get("arm") == ARM_P_PACK and cell.get("task") == task_id]
    if not found:
        return None
    return all((cell.get("scoring") or {}).get("matchedPreRegisteredExpectation") is True for cell in found)


def _p_pack_in_family_matched(cells: list[dict[str, Any]]) -> bool | None:
    flags = [_p_pack_task_matched(cells, task_id) for task_id in IN_FAMILY_TASKS]
    if any(flag is False for flag in flags):
        return False
    if any(flag is None for flag in flags):
        return None
    return True


def _p_pack_in_family_wrong_acceptance(cells: list[dict[str, Any]]) -> bool:
    for cell in cells:
        if cell.get("arm") != ARM_P_PACK or cell.get("task") not in IN_FAMILY_TASKS:
            continue
        if (cell.get("scoring") or {}).get("wrongAcceptance"):
            return True
    return False


def _formal_kernel_checked_stays_false(cells: list[dict[str, Any]]) -> bool:
    return all((cell.get("scoring") or {}).get("formalKernelChecked") is not True for cell in cells)


def _trust_from_probes(
    cells: list[dict[str, Any]],
    *,
    stripped: dict[str, Any],
    wrong_g: dict[str, Any],
    fair_baselines: dict[str, Any],
) -> dict[str, Any]:
    """Classify trust from structured probe fields, not problem-string substrings."""

    in_family = _p_pack_in_family_matched(cells)
    stripped_refused = _tri_state(stripped.get("refused"))
    wrong_fail_closed = _tri_state(wrong_g.get("failClosed"))
    wrong_emitted = _tri_state(wrong_g.get("emittedValue"))
    b0_cubes = fair_baselines.get("b0ValueExact")
    b1_cubes = fair_baselines.get("b1ValueExact")
    cubes_observed = b0_cubes is not None or b1_cubes is not None
    cubes_not_crippled: bool | None
    if cubes_observed:
        cubes_not_crippled = b0_cubes == "44100" and b1_cubes == "44100"
    else:
        cubes_not_crippled = None
    pack_refused_cubes = _tri_state(fair_baselines.get("pPackRefused"))
    pack_harmonic = _p_pack_task_matched(cells, TASK_NEGATIVE)
    pack_reversed = _p_pack_task_matched(cells, TASK_REVERSED)
    pack_wrong_value = _p_pack_in_family_wrong_acceptance(cells)
    formal_ok = _formal_kernel_checked_stays_false(cells)

    fails = (
        stripped_refused is False
        or wrong_fail_closed is False
        or wrong_emitted is True
        or in_family is False
        or pack_wrong_value
        or cubes_not_crippled is False
        or pack_refused_cubes is False
    )
    holds = (
        in_family is True
        and stripped_refused is True
        and wrong_fail_closed is True
        and wrong_emitted is not True
        and cubes_not_crippled is True
        and pack_refused_cubes is True
        and formal_ok
        and pack_harmonic is not False
        and pack_reversed is not False
        and not pack_wrong_value
    )
    probes = {
        "inFamilyPPackMatched": in_family,
        "strippedRefused": stripped_refused,
        "wrongGFailClosed": wrong_fail_closed,
        "wrongGEmittedValue": wrong_emitted,
        "cubesNotCrippled": cubes_not_crippled,
        "packRefusedCubes": pack_refused_cubes,
        "packRejectedHarmonic": pack_harmonic,
        "packRejectedReversed": pack_reversed,
        "formalKernelCheckedStaysFalse": formal_ok,
    }
    return {
        "fails": fails,
        "holds": holds and not fails,
        "probes": probes,
        "evidence": _trust_evidence(probes),
    }


def _trust_evidence(probes: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    in_family = probes.get("inFamilyPPackMatched")
    if in_family is True:
        lines.append("in-family P-pack values match the pre-registered rationals")
    elif in_family is False:
        lines.append("in-family P-pack values did not match the pre-registered rationals")
    else:
        lines.append("in-family P-pack match was not fully observed")

    stripped_refused = probes.get("strippedRefused")
    if stripped_refused is True:
        lines.append("stripped parametricAntidifference refuses")
    elif stripped_refused is False:
        lines.append("stripped parametricAntidifference did not refuse")
    else:
        lines.append("strip probe was not observed")

    wrong_closed = probes.get("wrongGFailClosed")
    wrong_emitted = probes.get("wrongGEmittedValue")
    if wrong_closed is True and wrong_emitted is not True:
        lines.append("wrong saved G fail-closes without emitting a sum")
    elif wrong_emitted is True:
        lines.append("wrong saved G emitted a finite-sum value")
    elif wrong_closed is False:
        lines.append("wrong saved G did not fail closed")
    else:
        lines.append("wrong saved G probe was not observed")

    cubes_ok = probes.get("cubesNotCrippled")
    pack_cubes = probes.get("packRefusedCubes")
    pack_harmonic = probes.get("packRejectedHarmonic")
    if pack_cubes is True and pack_harmonic is True:
        lines.append("out-of-family k^3 and 1/k are rejected on the pack path")
    elif pack_cubes is False or pack_harmonic is False:
        lines.append("out-of-family k^3 or 1/k was not rejected on the pack path")
    elif cubes_ok is False:
        lines.append("fair B0/B1 were crippled on out-of-family k^3")
    elif pack_cubes is True:
        lines.append("out-of-family k^3 is rejected on the pack path")
    elif pack_harmonic is True:
        lines.append("out-of-family 1/k is rejected on the pack path")

    pack_reversed = probes.get("packRejectedReversed")
    if pack_reversed is True:
        lines.append("reversed bounds are rejected on the pack path")
    elif pack_reversed is False:
        lines.append("reversed bounds were not rejected on the pack path")

    if probes.get("formalKernelCheckedStaysFalse") is True:
        lines.append("formal_kernel_checked stays false")
    else:
        lines.append("formal_kernel_checked was true")
    return lines


def _p_held_out_uses_saved_content(cells: list[dict[str, Any]]) -> bool | None:
    """Held-out reuse: wrap/trace is binding; apply usedSavedContent corroborates."""

    observed = False
    for cell in cells:
        if cell.get("arm") != ARM_P_PACK or cell.get("task") not in HELD_OUT_TASKS:
            continue
        observed = True
        scoring = cell.get("scoring") or {}
        trace = scoring.get("constructionTrace") or {}
        if scoring.get("reconstructedOnPackArm"):
            return False
        if trace.get("gosper_sum") or trace.get("construct_antidifference"):
            return False
        if not scoring.get("usedSavedContent"):
            return False
    if not observed:
        return None
    return True


def _behavior_evidence(cells: list[dict[str, Any]], p_held_out_uses_saved: bool | None) -> list[str]:
    lines: list[str] = []
    if p_held_out_uses_saved is True:
        lines.append(
            "P-pack held-outs instantiate saved G with 0 gosper_sum / construct_antidifference calls (wrap is the probe)"
        )
    elif p_held_out_uses_saved is False:
        lines.append("P-pack held-outs reconstructed or did not use saved content (wrap is the probe)")
    else:
        lines.append("P-pack held-out construction wrap was not observed")

    b1_constructed = False
    b1_seen = False
    for cell in cells:
        if cell.get("arm") != ARM_B1 or cell.get("task") not in HELD_OUT_TASKS:
            continue
        b1_seen = True
        trace = (cell.get("scoring") or {}).get("constructionTrace") or {}
        if trace.get("construct_antidifference") or trace.get("gosper_sum"):
            b1_constructed = True
    if b1_constructed:
        lines.append("B1 held-outs still construct (baselines are not crippled)")
    elif b1_seen:
        lines.append("B1 held-outs did not construct")

    lines.append("B_template and B_codegen also reuse cached G; reuse is not unique to the pack")
    return lines


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


def _repeat_by_task_arm(cells: list[dict[str, Any]], *, in_family_only: bool = True) -> dict[str, dict[str, float]]:
    by_task: dict[str, dict[str, float]] = {}
    for cell in cells:
        arm = cell.get("arm")
        task = cell.get("task")
        if not isinstance(arm, str) or not isinstance(task, str):
            continue
        if in_family_only and task not in IN_FAMILY_TASKS:
            continue
        samples = _cell_latency_samples(cell)
        if not samples:
            continue
        by_task.setdefault(task, {})[arm] = samples[-1]
    return by_task


def observed_slower_checked_path(cells: list[dict[str, Any]]) -> bool | None:
    by_task = _repeat_by_task_arm(cells)
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


def _all_repeat_faster(cells: list[dict[str, Any]], left: str, right: str) -> bool | None:
    by_task = _repeat_by_task_arm(cells)
    comparisons: list[bool] = []
    for arms in by_task.values():
        a = arms.get(left)
        b = arms.get(right)
        if a is None or b is None:
            continue
        comparisons.append(a < b)
    if not comparisons:
        return None
    return all(comparisons)


def _values_match(cells: list[dict[str, Any]], left: str, right: str) -> bool:
    by_task: dict[str, dict[str, str | None]] = {}
    for cell in cells:
        if cell.get("task") not in IN_FAMILY_TASKS:
            continue
        arm = cell.get("arm")
        task = cell.get("task")
        if not isinstance(arm, str) or not isinstance(task, str):
            continue
        summary = cell.get("summary") or {}
        by_task.setdefault(task, {})[arm] = summary.get("valueExact")
    if not by_task:
        return False
    for arms in by_task.values():
        if left not in arms or right not in arms:
            return False
        if arms[left] is None or arms[left] != arms[right]:
            return False
    return True


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


def _utility_observations(cells: list[dict[str, Any]]) -> dict[str, Any]:
    slower = observed_slower_checked_path(cells)
    pack_vs_b1 = _all_repeat_faster(cells, ARM_P_PACK, ARM_B1)
    pack_vs_template = _all_repeat_faster(cells, ARM_P_PACK, ARM_B_TEMPLATE)
    pack_vs_codegen = _all_repeat_faster(cells, ARM_P_PACK, ARM_B_CODEGEN)
    template_vs_p = _values_match(cells, ARM_B_TEMPLATE, ARM_P_PACK)
    codegen_vs_p = _values_match(cells, ARM_B_CODEGEN, ARM_P_PACK)
    b0_matches = _b0_already_matches(cells)
    return {
        "observedSlowerCheckedPath": slower,
        "observedSlowerCheckedPathNote": (
            "Repeat-trial in-process latency for B1/P-pack was higher than B0 on every "
            "in-family task in this report. Not an isolated cold start and not a dollar cost."
            if slower is True
            else (
                "Measured in-process latencies do not support claiming the checked path is slower than B0."
                if slower is False
                else "No measured latencies; slower-checked-path is not an observation."
            )
        ),
        "observedPackRepeatFasterThanB1": pack_vs_b1,
        "observedPackRepeatFasterThanB1Note": (
            "P-pack repeat in-process latency was lower than B1 on every in-family task. "
            "This is not a dollar saving, not uniqueness, and not a promotion case."
            if pack_vs_b1 is True
            else (
                "Measured in-process latencies do not support claiming P-pack is faster than B1."
                if pack_vs_b1 is False
                else "No measured latencies; pack-vs-B1 is not an observation."
            )
        ),
        "observedPackRepeatFasterThanTemplate": pack_vs_template,
        "observedPackRepeatFasterThanCodegen": pack_vs_codegen,
        "b0AlreadyMatchesInFamily": b0_matches,
        "bTemplateAlreadyMatchesP": template_vs_p,
        "bCodegenAlreadyMatchesP": codegen_vs_p,
        "armsCompared": list(PRIMARY_ARMS),
    }
