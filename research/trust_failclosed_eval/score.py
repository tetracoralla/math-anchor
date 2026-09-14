"""Score trust/fail-closed cells. Three judgments stay separate.

Trustworthiness is per-cell holds / fail-closed / silent-wrong.
Behavior is whether the pack instantiates saved content.
Utility is not the primary claim of this smoke.
"""

from __future__ import annotations

from typing import Any

from research.reuse_benefit_eval.protocol import CONSTRUCTION_TRACE_KEYS
from research.reuse_benefit_eval.score import result_summary as reuse_result_summary

from .protocol import (
    ADVERSARIAL_SAVED_G_TASKS,
    ARM_B_TEMPLATE,
    ARM_P_PACK,
    BOTH_FAIL_CLOSED_TASKS,
    CONTROL_TASKS,
    DIFFERENTIATION_TASKS,
    OUT_OF_DOMAIN_TASKS,
    TASK_CONTROL,
    TASK_CUBES,
    TASK_HARMONIC,
    TASK_OVER_LIMIT,
    TASK_PARAMETER,
    TASK_REVERSED,
    TASK_SWAPPED_G,
    TASK_WRONG_G,
    TRUST_FAIL_CLOSED,
    TRUST_HOLDS,
    TRUST_SILENT_WRONG,
    expected_by_arm,
    expected_exact_if_computed,
)


CONSTRUCTION_PROBE = "wrap"
FAIL_CLOSED_STATUSES = {"error", "inapplicable", "unsupported", "falsified"}
FAIL_CLOSED_CODES = {"E_UNSUPPORTED", "E_DOMAIN", "E_LIMIT", "E_INPUT", "E_AST_BLOCK"}


def result_summary(result: dict[str, Any] | None, error: BaseException | None) -> dict[str, Any]:
    summary = reuse_result_summary(result, error)
    if error is None and isinstance(result, dict):
        summary["savedG"] = result.get("savedG")
        summary["packIdentityChecks"] = bool(result.get("packIdentityChecks"))
        summary["packDomainChecks"] = bool(result.get("packDomainChecks"))
        if result.get("status") == "falsified":
            summary["status"] = "falsified"
            summary["emittedValue"] = False
    else:
        summary["savedG"] = None
        summary["packIdentityChecks"] = False
        summary["packDomainChecks"] = False
        summary["emittedValue"] = False
    if summary.get("valueExact"):
        summary["emittedValue"] = True
    elif "emittedValue" not in summary:
        summary["emittedValue"] = False
    return summary


def construction_trace(construction: dict[str, int] | None) -> dict[str, int]:
    construction = construction or {}
    return {key: int(construction.get(key) or 0) for key in CONSTRUCTION_TRACE_KEYS}


def _trace_reconstructed(trace: dict[str, Any] | None) -> bool:
    trace = trace or {}
    return any(trace.get(key) for key in CONSTRUCTION_TRACE_KEYS)


def _is_fail_closed(summary: dict[str, Any]) -> bool:
    status = summary.get("status")
    if status == "falsified":
        return not summary.get("valueExact")
    if status in FAIL_CLOSED_STATUSES:
        code = summary.get("errorCode")
        return code in FAIL_CLOSED_CODES or status in {"inapplicable", "unsupported", "error"}
    return False


def classify_trust(task: dict[str, Any], arm_id: str, summary: dict[str, Any]) -> dict[str, Any]:
    """Per-cell trustworthiness. Never a collapsed success flag."""

    trusted_outcome = task.get("proposalTrustedOutcome")
    value_exact = summary.get("valueExact")
    emitted = bool(value_exact)
    expected_trust = expected_by_arm(task, arm_id).get("trust")
    expected_value = expected_exact_if_computed(task, arm_id)

    if trusted_outcome == "exact":
        matched = summary.get("status") == "ok" and value_exact == task.get("expectedExact")
        if matched:
            observed = TRUST_HOLDS
            reason = "emitted_trusted_exact"
        elif emitted and value_exact != task.get("expectedExact"):
            observed = TRUST_SILENT_WRONG
            reason = "emitted_wrong_exact"
        else:
            observed = TRUST_FAIL_CLOSED if _is_fail_closed(summary) else TRUST_SILENT_WRONG
            reason = "did_not_emit_trusted_exact"
    else:
        if emitted:
            observed = TRUST_SILENT_WRONG
            if expected_value and value_exact == expected_value:
                reason = (
                    "silent_accept_out_of_declared_pack_domain"
                    if task.get("id") == TASK_OVER_LIMIT
                    else "emitted_value_when_trusted_outcome_is_no_value"
                )
            else:
                reason = "emitted_value_when_trusted_outcome_is_no_value"
        elif _is_fail_closed(summary):
            observed = TRUST_FAIL_CLOSED
            reason = "refused_or_falsified_without_value"
        else:
            observed = TRUST_FAIL_CLOSED if not emitted else TRUST_SILENT_WRONG
            reason = "no_value_without_clear_fail_closed_status"

    return {
        "observed": observed,
        "expected": expected_trust,
        "matchedProtocol": observed == expected_trust,
        "reason": reason,
        "emittedValue": emitted,
        "valueExact": value_exact,
        "scale": [TRUST_HOLDS, TRUST_FAIL_CLOSED, TRUST_SILENT_WRONG],
    }


def score_cell(
    *,
    arm_id: str,
    task: dict[str, Any],
    summary: dict[str, Any],
    construction: dict[str, int] | None,
) -> dict[str, Any]:
    task_id = str(task["id"])
    trust = classify_trust(task, arm_id, summary)
    expected = expected_by_arm(task, arm_id)
    expected_code = expected.get("code")
    code = summary.get("errorCode")

    counted_as_solved = trust["observed"] == TRUST_HOLDS
    wrong_acceptance = trust["observed"] == TRUST_SILENT_WRONG
    fail_closed = trust["observed"] == TRUST_FAIL_CLOSED

    code_ok = True
    if expected.get("failClosed") is True and expected_code:
        code_ok = fail_closed and code == expected_code
    elif fail_closed and expected_code:
        code_ok = code == expected_code

    lifecycle = None
    call_alone = None
    if isinstance(summary.get("adoption"), dict):
        lifecycle = summary["adoption"].get("lifecycleEvidence")
        call_alone = summary["adoption"].get("callAloneIsNotAdoption")

    trace = construction_trace(construction)
    reconstructed = False
    if arm_id == ARM_P_PACK:
        reconstructed = _trace_reconstructed(trace)

    return {
        "trustworthiness": trust["observed"],
        "trustReason": trust["reason"],
        "expectedTrust": trust["expected"],
        "matchedPreRegisteredExpectation": trust["matchedProtocol"] and code_ok,
        "countedAsSolved": counted_as_solved,
        "wrongAcceptance": wrong_acceptance,
        "failClosed": fail_closed,
        "emittedValue": trust["emittedValue"],
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
        "constructionTrace": trace,
        "reconstructedOnPackArm": reconstructed,
        "semanticAdoptionFromLifecycleEvidenceAlone": False,
        "taskId": task_id,
        "savedG": task.get("savedG"),
    }


def decide(
    cells: list[dict[str, Any]],
    *,
    stripped: dict[str, Any],
    binding: dict[str, Any],
) -> dict[str, Any]:
    problems: list[str] = []
    for cell in cells:
        scoring = cell.get("scoring") or {}
        label = f"{cell.get('arm')}×{cell.get('task')}"
        if not scoring.get("matchedPreRegisteredExpectation"):
            problems.append(f"{label}: did not match the pre-registered trust expectation")
        if scoring.get("coversOriginalTaskClaim") is True:
            problems.append(f"{label}: coversOriginalTaskClaim was true")
        if scoring.get("formalKernelChecked"):
            problems.append(f"{label}: formal_kernel_checked was true")
        if scoring.get("baselineEmbedded") and cell.get("arm") == ARM_P_PACK:
            problems.append(f"{label}: B0 was embedded (compare_baseline leaked into the arm)")
        if scoring.get("reconstructedOnPackArm"):
            problems.append(
                f"{label}: P-pack reconstructed via gosper_sum, construct_antidifference, summation, or Sum.doit"
            )
        if scoring.get("floatingApproximation"):
            problems.append(f"{label}: floating approximation labelled as a result")
        if cell.get("arm") == ARM_P_PACK and cell.get("task") in CONTROL_TASKS:
            if scoring.get("gosperCalledJsonFlag") is not False:
                problems.append(f"{label}: gosperCalled JSON flag was not false")
            if scoring.get("reconstructionDisabled") is not True:
                problems.append(f"{label}: reconstructionDisabled was not true")
            if not scoring.get("usedSavedContent"):
                problems.append(f"{label}: P-pack control did not use saved content")
        if cell.get("arm") == ARM_P_PACK and cell.get("task") in ADVERSARIAL_SAVED_G_TASKS:
            if scoring.get("emittedValue"):
                problems.append(f"{label}: P-pack emitted a finite-sum value on mutated saved G")
            if scoring.get("trustworthiness") != TRUST_FAIL_CLOSED:
                problems.append(f"{label}: P-pack did not fail closed on mutated saved G")
        if cell.get("trialsDisagree"):
            problems.append(f"{label}: trials disagree")

    if stripped.get("refused") is not True:
        problems.append("stripped parametricAntidifference payload did not refuse")
    if binding.get("packTamperedIdentityFailClosed") is not True:
        problems.append("tampered identity.right did not fail closed on verify_typed_binding")
    if binding.get("packGoodResultBindingHolds") is not True:
        problems.append("verify_typed_binding rejected a good P-pack control result")
    if binding.get("templateHasObligationBindingHook") is True:
        problems.append("B_template unexpectedly exposed an obligation binding hook")

    contrast = _contrast(cells)
    judgments = three_judgments(cells, stripped=stripped, binding=binding, contrast=contrast)

    targeted = bool(problems)
    experiment_verdict = (
        "targeted_fix"
        if targeted
        else (
            "differentiation_observed"
            if contrast["anyDifferentiation"]
            else "no_differentiation"
        )
    )
    reasons = [
        "This smoke answers fail-closed vs silent-wrong against a fair template, not a latency bake-off.",
        "Promotion is forbidden in this smoke even when cells match. Do not start H1.",
        "Out-of-family k^3 and 1/k refusal is not pack-unique versus a family-matched template.",
        "Trustworthiness, behavior, and utility stay separate and are not one success flag.",
        "No model calls, no token accounting, and no dollar prices. Do not invent a savings percentage.",
    ]
    if contrast["anyDifferentiation"]:
        reasons.insert(
            0,
            "P-pack fail-closed on mutated saved G and/or declared-domain probes while B_template emitted a value.",
        )
    if targeted:
        reasons = [
            "This smoke found a harness or vertical honesty/correctness problem.",
            "Do not promote the pack. Do not start H1 from this result.",
        ]

    return {
        "verdict": "targeted_fix" if targeted else "evidence_insufficient",
        "experimentVerdict": experiment_verdict,
        "promote": False,
        "targetedFix": targeted,
        "keepExperimental": True,
        "publicPromotion": False,
        "basedOnThisSmokeOnly": True,
        "notAStatisticalSaving": True,
        "notALatencyBakeOff": True,
        "doNotStartH1": True,
        "problems": problems,
        "reasons": reasons,
        "next": (
            "targeted fix on this vertical; keep experimental"
            if targeted
            else (
                "Keep experimental. Do not start H1. Do not promote. "
                "Fail-closed vs silent-wrong on this family is not product readiness."
            )
        ),
        "judgments": judgments,
        "contrast": contrast,
        "utilityNotPrimary": True,
        "observedWrongGDifferentiation": contrast["savedG"],
        "observedDomainDifferentiation": contrast["domain"],
        "observedOutOfFamilyBothFailClosed": contrast["outOfFamilyBothFailClosed"],
        "observedParameterMismatchBothFailClosed": contrast["parameterMismatchBothFailClosed"],
    }


def three_judgments(
    cells: list[dict[str, Any]],
    *,
    stripped: dict[str, Any],
    binding: dict[str, Any],
    contrast: dict[str, Any],
) -> dict[str, Any]:
    pack_control = _cell_trust(cells, ARM_P_PACK, TASK_CONTROL)
    template_control = _cell_trust(cells, ARM_B_TEMPLATE, TASK_CONTROL)
    behavior = _behavior(cells)

    return {
        "notCollapsedIntoOneSuccess": True,
        "trustworthiness": {
            "verdict": "per_cell",
            "scale": [TRUST_HOLDS, TRUST_FAIL_CLOSED, TRUST_SILENT_WRONG],
            "appliedPerCell": True,
            "notBehavior": True,
            "notUtility": True,
            "means": (
                "holds = trusted exact; fail-closed = no value; "
                "silent-wrong = emitted a value when the protocol trusted outcome is no_value, "
                "or a wrong exact"
            ),
            "control": {
                "P-pack": pack_control,
                "B_template": template_control,
            },
            "observedContrast": contrast["byTask"],
            "strippedPayloadRefused": stripped.get("refused") is True,
            "bindingMismatchFailClosedOnPack": binding.get("packTamperedIdentityFailClosed") is True,
            "templateHasObligationBindingHook": binding.get("templateHasObligationBindingHook") is True,
            "evidence": _trust_evidence(cells, stripped, binding, contrast),
        },
        "behavior": {
            "verdict": behavior["verdict"],
            "notTrustworthiness": True,
            "notUtility": True,
            "means": "the pack instantiates saved G (including mutated G) instead of reconstructing",
            "constructionProbe": CONSTRUCTION_PROBE,
            "evidence": behavior["evidence"],
            "packReuseIsNotUniqueVsTemplate": True,
        },
        "utility": {
            "verdict": "not_the_primary_claim",
            "notTrustworthiness": True,
            "notBehavior": True,
            "means": "net benefit versus strong baselines is not scored here",
            "mayBeNegative": True,
            "latencyIsNotThePrimaryClaim": True,
            "reuseBenefitAlreadyReportedNoNetBenefitVsTemplate": True,
            "evidence": [
                "reuse-benefit smoke already recorded no_net_benefit_vs_strong_baselines",
                "this smoke does not re-ask the same-family latency question",
                "timings, if present, are informational in-process wall times",
                "no dollar costs; no savings percentage",
            ],
        },
    }


def _cell_trust(cells: list[dict[str, Any]], arm: str, task: str) -> str | None:
    for cell in cells:
        if cell.get("arm") == arm and cell.get("task") == task:
            return (cell.get("scoring") or {}).get("trustworthiness")
    return None


def _cell(cells: list[dict[str, Any]], arm: str, task: str) -> dict[str, Any] | None:
    for cell in cells:
        if cell.get("arm") == arm and cell.get("task") == task:
            return cell
    return None


def _pair_differentiates(cells: list[dict[str, Any]], task: str) -> bool | None:
    pack = _cell(cells, ARM_P_PACK, task)
    template = _cell(cells, ARM_B_TEMPLATE, task)
    if pack is None or template is None:
        return None
    pack_trust = (pack.get("scoring") or {}).get("trustworthiness")
    template_trust = (template.get("scoring") or {}).get("trustworthiness")
    return pack_trust == TRUST_FAIL_CLOSED and template_trust == TRUST_SILENT_WRONG


def _both_fail_closed(cells: list[dict[str, Any]], task: str) -> bool | None:
    pack = _cell(cells, ARM_P_PACK, task)
    template = _cell(cells, ARM_B_TEMPLATE, task)
    if pack is None or template is None:
        return None
    return (
        (pack.get("scoring") or {}).get("trustworthiness") == TRUST_FAIL_CLOSED
        and (template.get("scoring") or {}).get("trustworthiness") == TRUST_FAIL_CLOSED
    )


def _contrast(cells: list[dict[str, Any]]) -> dict[str, Any]:
    by_task: dict[str, Any] = {}
    for task_id in (
        TASK_CONTROL,
        TASK_WRONG_G,
        TASK_SWAPPED_G,
        TASK_CUBES,
        TASK_HARMONIC,
        TASK_REVERSED,
        TASK_PARAMETER,
        TASK_OVER_LIMIT,
    ):
        pack = _cell_trust(cells, ARM_P_PACK, task_id)
        template = _cell_trust(cells, ARM_B_TEMPLATE, task_id)
        differentiates = _pair_differentiates(cells, task_id)
        by_task[task_id] = {
            "P-pack": pack,
            "B_template": template,
            "differentiates": differentiates,
        }
    saved_flags = [_pair_differentiates(cells, task_id) for task_id in ADVERSARIAL_SAVED_G_TASKS]
    domain_flags = [_pair_differentiates(cells, task_id) for task_id in OUT_OF_DOMAIN_TASKS]
    oof_flags = [_both_fail_closed(cells, task_id) for task_id in (TASK_CUBES, TASK_HARMONIC)]
    saved = True if saved_flags and all(flag is True for flag in saved_flags) else (
        False if any(flag is False for flag in saved_flags) else None
    )
    domain = True if domain_flags and all(flag is True for flag in domain_flags) else (
        False if any(flag is False for flag in domain_flags) else None
    )
    oof = True if oof_flags and all(flag is True for flag in oof_flags) else (
        False if any(flag is False for flag in oof_flags) else None
    )
    param = _both_fail_closed(cells, TASK_PARAMETER)
    any_diff = any(flag is True for flag in saved_flags + domain_flags)
    return {
        "byTask": by_task,
        "savedG": saved,
        "domain": domain,
        "outOfFamilyBothFailClosed": oof,
        "parameterMismatchBothFailClosed": param,
        "anyDifferentiation": any_diff,
        "differentiationTasks": list(DIFFERENTIATION_TASKS),
        "bothFailClosedTasks": list(BOTH_FAIL_CLOSED_TASKS),
    }


def _trust_evidence(
    cells: list[dict[str, Any]],
    stripped: dict[str, Any],
    binding: dict[str, Any],
    contrast: dict[str, Any],
) -> list[str]:
    lines: list[str] = []
    if _cell_trust(cells, ARM_P_PACK, TASK_CONTROL) == TRUST_HOLDS and _cell_trust(
        cells, ARM_B_TEMPLATE, TASK_CONTROL
    ) == TRUST_HOLDS:
        lines.append("in-family control: both arms hold at 355 (template is not crippled)")
    if contrast.get("savedG") is True:
        lines.append("wrong/swapped saved G: P-pack fail-closed, B_template silent-wrong")
    elif contrast.get("savedG") is False:
        lines.append("wrong/swapped saved G did not show fail-closed vs silent-wrong")
    if contrast.get("domain") is True:
        lines.append("reversed bounds and over-limit: P-pack fail-closed, B_template silent-wrong")
    elif contrast.get("domain") is False:
        lines.append("declared-domain probes did not show fail-closed vs silent-wrong")
    if contrast.get("outOfFamilyBothFailClosed") is True:
        lines.append("out-of-family k^3 and 1/k: both arms fail-closed (not pack-unique)")
    if contrast.get("parameterMismatchBothFailClosed") is True:
        lines.append("parameterC/summand mismatch: both arms fail-closed (not pack-unique)")
    if stripped.get("refused") is True:
        lines.append("stripped parametricAntidifference refuses on the pack path")
    if binding.get("packTamperedIdentityFailClosed") is True:
        lines.append("tampered identity.right fail-closes on verify_typed_binding")
    if binding.get("templateHasObligationBindingHook") is not True:
        lines.append("fair template has no obligation binding hook")
    lines.append("formal_kernel_checked stays false")
    return lines


def _behavior(cells: list[dict[str, Any]]) -> dict[str, Any]:
    observed = False
    uses_saved = True
    reconstructed = False
    for cell in cells:
        if cell.get("arm") != ARM_P_PACK:
            continue
        if cell.get("task") not in {TASK_CONTROL, *ADVERSARIAL_SAVED_G_TASKS}:
            continue
        observed = True
        scoring = cell.get("scoring") or {}
        if scoring.get("reconstructedOnPackArm") or _trace_reconstructed(scoring.get("constructionTrace")):
            reconstructed = True
            uses_saved = False
        if cell.get("task") == TASK_CONTROL and not scoring.get("usedSavedContent"):
            uses_saved = False
    if not observed:
        verdict = "evidence_insufficient"
    elif reconstructed or not uses_saved:
        verdict = "re_solves"
    else:
        verdict = "pack_uses_saved_content"
    evidence = []
    if verdict == "pack_uses_saved_content":
        evidence.append(
            "P-pack control and mutated-G cells instantiate saved G with 0 constructor calls (wrap is the probe)"
        )
    elif verdict == "re_solves":
        evidence.append("P-pack reconstructed or did not use saved content (wrap is the probe)")
    else:
        evidence.append("P-pack saved-content wrap was not observed")
    evidence.append("B_template also instantiates a cached G; reuse of the formula is not unique")
    return {"verdict": verdict, "evidence": evidence}
