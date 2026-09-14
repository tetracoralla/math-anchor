"""Structural probes that reuse existing apply / typed-binding paths.

Strip and binding mismatch are not timed comparison cells. They exist to
disprove overclaim: the pack must refuse a missing payload and a tampered
identity, using hooks already present (A3 / PR13 R1–R3).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from math_anchor.errors import CalculatorError
from research.method_packs.loader import PackFormatError
from research.polynomial_finite_sum_proposal.coverage import (
    CoverageIntegrityError,
    verify_typed_binding,
)

from .protocol import TASK_CONTROL


def stripped_payload_probe(held_out: dict[str, Any]) -> dict[str, Any]:
    from pathlib import Path
    import json

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
            "task": held_out.get("id") or TASK_CONTROL,
            "note": (
                "Stripping parametricAntidifference must stop the P-pack path. "
                "B_template does not load pack JSON, so this probe is pack-only."
            ),
        }
    return {
        "refused": False,
        "errorCode": None,
        "errorType": None,
        "message": "stripped pack completed; this is a harness failure",
        "task": held_out.get("id") or TASK_CONTROL,
        "note": "Stripping parametricAntidifference must stop the P-pack path.",
    }


def binding_mismatch_probe(
    *,
    pack_result: dict[str, Any] | None,
    pack_error: BaseException | None,
    template_result: dict[str, Any] | None,
    task: dict[str, Any],
) -> dict[str, Any]:
    """Reuse verify_typed_binding (A3 / PR13 R1–R3). Do not invent a parallel stack."""

    binding_task = {
        "summand": task["summand"],
        "variable": task.get("variable") or "k",
        "lower": task["lower"],
        "upper": task["upper"],
        "taskId": task.get("taskId"),
    }
    pack_ok = _binding_on_good_result(pack_result, pack_error, binding_task)
    pack_tamper = _binding_on_tampered_identity(pack_result, pack_error, binding_task)
    template_hook = _template_binding_hook(template_result, binding_task)
    return {
        "hook": "research.polynomial_finite_sum_proposal.coverage.verify_typed_binding",
        "task": task.get("id") or TASK_CONTROL,
        "packGoodResultBindingHolds": pack_ok.get("holds"),
        "packGoodResult": pack_ok,
        "packTamperedIdentityFailClosed": pack_tamper.get("failClosed"),
        "packTamperedIdentity": pack_tamper,
        "templateHasObligationBindingHook": template_hook.get("hookPresent"),
        "templateBinding": template_hook,
        "note": (
            "Typed binding re-checks current G against the original task summand "
            "and refuse a swapped identity.right. The fair template has no "
            "identity/obligation record, so it cannot detect that mismatch."
        ),
    }


def _binding_on_good_result(
    result: dict[str, Any] | None,
    error: BaseException | None,
    task: dict[str, Any],
) -> dict[str, Any]:
    if error is not None or not isinstance(result, dict):
        return {
            "holds": False,
            "reason": "pack_control_did_not_return_a_result",
            "errorType": type(error).__name__ if error is not None else None,
        }
    try:
        check = verify_typed_binding(deepcopy(result), task=task)
    except (CoverageIntegrityError, CalculatorError) as caught:
        return {
            "holds": False,
            "reason": "verify_typed_binding_rejected_good_pack_result",
            "errorCode": getattr(caught, "code", None),
            "message": getattr(caught, "message", str(caught)),
        }
    return {
        "holds": check.get("ok") is True,
        "currentGBoundToCheckedIdentity": check.get("currentGBoundToCheckedIdentity"),
        "formula": check.get("formula"),
    }


def _binding_on_tampered_identity(
    result: dict[str, Any] | None,
    error: BaseException | None,
    task: dict[str, Any],
) -> dict[str, Any]:
    if error is not None or not isinstance(result, dict):
        return {
            "failClosed": False,
            "reason": "pack_control_did_not_return_a_result",
        }
    tampered = deepcopy(result)
    identity = tampered.get("identity")
    if not isinstance(identity, dict):
        return {
            "failClosed": False,
            "reason": "pack_result_has_no_identity_to_tamper",
        }
    identity["right"] = "k**3"
    try:
        verify_typed_binding(tampered, task=task)
    except (CoverageIntegrityError, CalculatorError) as caught:
        return {
            "failClosed": True,
            "emittedTrustedBinding": False,
            "errorCode": getattr(caught, "code", None),
            "errorType": type(caught).__name__,
            "message": getattr(caught, "message", str(caught)),
        }
    return {
        "failClosed": False,
        "emittedTrustedBinding": True,
        "reason": "tampered identity.right still bound; this is a harness failure",
    }


def _template_binding_hook(result: dict[str, Any] | None, task: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {
            "hookPresent": False,
            "reason": "template_control_did_not_return_a_result",
        }
    identity = result.get("identity")
    receipt = result.get("obligationReceipt")
    hook_present = isinstance(identity, dict) or isinstance(receipt, dict)
    try:
        verify_typed_binding(deepcopy(result), task=task)
        bound = True
        error_message = None
    except (CoverageIntegrityError, CalculatorError) as caught:
        bound = False
        error_message = getattr(caught, "message", str(caught))
    return {
        "hookPresent": hook_present,
        "verifyTypedBindingSucceeded": bound,
        "message": error_message,
        "note": (
            "Absence of an identity/obligation record is the observation: "
            "the fair template cannot fail closed on a binding mismatch it never recorded."
        ),
    }
