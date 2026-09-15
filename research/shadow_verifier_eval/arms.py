"""Arm runners for the shadow-verifier scaffold.

B0/B1 are deferred live-model interfaces.
B2/B3 reuse math_anchor.obligations.check_obligation_set (not a second stack).
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from math_anchor.errors import CalculatorError
from math_anchor.obligations import check_obligation_set

from .model_interface import deferred_cell
from .protocol import ARM_B0, ARM_B1, ARM_B2, ARM_B3, expected_by_arm


class ArmExecutionError(CalculatorError):
    """Smoke arm failed before producing a result object."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    if path.exists():
        raise ArmExecutionError("E_INPUT", "receipt output already exists; refusing to overwrite it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _entry_by_id(entries: list[dict[str, Any]], obligation_id: str) -> dict[str, Any] | None:
    for entry in entries:
        if entry.get("id") == obligation_id:
            return entry
    return None


def _obligation_summaries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for entry in entries:
        detail = entry.get("detail") if isinstance(entry.get("detail"), dict) else {}
        summaries.append(
            {
                "id": entry.get("id"),
                "status": entry.get("status"),
                "assuranceLevel": entry.get("assuranceLevel"),
                "scope": entry.get("scope"),
                "reason": detail.get("reason"),
                "blockedBy": entry.get("blockedBy"),
            }
        )
    return summaries


def _request_for_arm(task: dict[str, Any], *, response_mode: str) -> dict[str, Any]:
    request = deepcopy(task.get("obligationRequest"))
    if not isinstance(request, dict):
        raise ArmExecutionError("E_INPUT", f"task {task.get('id')!r} is missing obligationRequest")
    request["responseMode"] = response_mode
    return request


def run_arm(
    arm_id: str,
    task: dict[str, Any],
    *,
    protocol: dict[str, Any] | None = None,
    receipt_dir: Path | None = None,
) -> dict[str, Any]:
    if arm_id in (ARM_B0, ARM_B1):
        return deferred_cell(arm_id, task, protocol=protocol)
    if arm_id == ARM_B2:
        return run_b2(task, protocol=protocol, receipt_dir=receipt_dir)
    if arm_id == ARM_B3:
        return run_b3(task, protocol=protocol, receipt_dir=receipt_dir)
    raise ArmExecutionError("E_INPUT", f"unknown shadow-verifier arm: {arm_id}")


def run_b2(
    task: dict[str, Any],
    *,
    protocol: dict[str, Any] | None = None,
    receipt_dir: Path | None = None,
) -> dict[str, Any]:
    request = _request_for_arm(task, response_mode="full")
    feedback, receipt = check_obligation_set(request)
    return _obligation_result(
        ARM_B2,
        task,
        feedback=feedback,
        receipt=receipt,
        response_mode="full",
        quiet_success=False,
        receipt_dir=receipt_dir,
        apply_repair=False,
    )


def run_b3(
    task: dict[str, Any],
    *,
    protocol: dict[str, Any] | None = None,
    receipt_dir: Path | None = None,
) -> dict[str, Any]:
    request = _request_for_arm(task, response_mode="failures_only")
    feedback, receipt = check_obligation_set(request)
    result = _obligation_result(
        ARM_B3,
        task,
        feedback=feedback,
        receipt=receipt,
        response_mode="failures_only",
        quiet_success=True,
        receipt_dir=receipt_dir,
        apply_repair=True,
    )
    result["repairLoopHook"] = True
    result["repairHookIsNotLiveModelRepair"] = True
    return result


def _obligation_result(
    arm_id: str,
    task: dict[str, Any],
    *,
    feedback: dict[str, Any],
    receipt: dict[str, Any],
    response_mode: str,
    quiet_success: bool,
    receipt_dir: Path | None,
    apply_repair: bool,
) -> dict[str, Any]:
    primary_id = str(task.get("primaryObligationId") or "")
    entries = list(receipt.get("obligations") or [])
    primary = _entry_by_id(entries, primary_id) or {}
    primary_status = primary.get("status")
    feedback_ids = [
        entry.get("id")
        for entry in feedback.get("obligations") or []
        if isinstance(entry, dict)
    ]
    all_checked = feedback.get("status") == "checked"
    quiet = bool(quiet_success and all_checked)
    if quiet:
        returned_feedback = None
        model_context_bytes = 0
    else:
        returned_feedback = {
            "status": feedback.get("status"),
            "responseMode": feedback.get("responseMode"),
            "summary": feedback.get("summary"),
            "obligationIds": feedback_ids,
        }
        model_context_bytes = len(_canonical_bytes(feedback))
    receipt_bytes = len(_canonical_bytes(receipt))
    receipt_path = None
    if receipt_dir is not None:
        receipt_path = receipt_dir / f"{arm_id}-{task['id']}.receipt.json"
        _write_receipt(receipt_path, receipt)

    detected = primary_status not in {None, "checked"}
    repair_block: dict[str, Any] | None = None
    if apply_repair and isinstance(task.get("repair"), dict):
        repair_block = _run_seeded_repair(
            task["repair"],
            receipt_dir=receipt_dir,
            task_id=str(task["id"]),
        )

    expected = expected_by_arm(task, arm_id)
    return {
        "arm": arm_id,
        "task": task["id"],
        "status": "ok",
        "modelArms": None,
        "runnableThisSmoke": True,
        "corruptionKind": task.get("corruptionKind"),
        "role": task.get("role"),
        "g1SupportedSeededError": bool(task.get("g1SupportedSeededError")),
        "g3Control": bool(task.get("g3Control")),
        "primaryObligationId": primary_id,
        "primaryStatus": primary_status,
        "assuranceLevel": primary.get("assuranceLevel"),
        "scope": primary.get("scope"),
        "reason": (primary.get("detail") or {}).get("reason")
        if isinstance(primary.get("detail"), dict)
        else None,
        "feedbackStatus": feedback.get("status"),
        "responseMode": response_mode,
        "feedbackObligationIds": feedback_ids,
        "feedbackIncludesPrimary": primary_id in feedback_ids,
        "quietSuccess": quiet,
        "receiptOutsideModelContext": receipt_path is not None,
        "receiptPath": str(receipt_path) if receipt_path is not None else None,
        "modelContextBytes": model_context_bytes,
        "receiptBytes": receipt_bytes,
        "detected": detected,
        "coversOriginalTaskClaim": False,
        "formalKernelChecked": False,
        "obligationSummaries": _obligation_summaries(entries),
        "receiptDigest": receipt.get("receiptDigest"),
        "requestDigest": receipt.get("requestDigest"),
        "summary": receipt.get("summary"),
        "returnedFeedback": returned_feedback,
        "repair": repair_block,
        "expectedPrimaryStatus": expected.get("primaryStatus") or task.get("expectedPrimaryStatus"),
        "engine": "math-anchor.obligation-set.v0.1",
        "notASecondStack": True,
    }


def _run_seeded_repair(
    repair: dict[str, Any],
    *,
    receipt_dir: Path | None,
    task_id: str,
) -> dict[str, Any]:
    request = deepcopy(repair.get("obligationRequest"))
    if not isinstance(request, dict):
        raise ArmExecutionError("E_INPUT", f"repair for {task_id} is missing obligationRequest")
    request["responseMode"] = "failures_only"
    feedback, receipt = check_obligation_set(request)
    entries = list(receipt.get("obligations") or [])
    primary_id = None
    if entries:
        primary_id = entries[0].get("id")
    primary = entries[0] if entries else {}
    all_checked = feedback.get("status") == "checked"
    receipt_path = None
    if receipt_dir is not None:
        receipt_path = receipt_dir / f"B3-{task_id}.repair.receipt.json"
        _write_receipt(receipt_path, receipt)
    return {
        "kind": repair.get("kind"),
        "notALiveModelRepair": True,
        "primaryObligationId": primary_id,
        "primaryStatus": primary.get("status"),
        "feedbackStatus": feedback.get("status"),
        "quietSuccess": all_checked,
        "modelContextBytes": 0 if all_checked else len(_canonical_bytes(feedback)),
        "receiptOutsideModelContext": receipt_path is not None,
        "receiptPath": str(receipt_path) if receipt_path is not None else None,
        "receiptDigest": receipt.get("receiptDigest"),
        "expectedPrimaryStatus": repair.get("expectedPrimaryStatus"),
    }


def is_arm_exception(error: BaseException) -> bool:
    from .model_interface import ModelArmDeferredError

    return isinstance(error, (ArmExecutionError, ModelArmDeferredError, CalculatorError))
