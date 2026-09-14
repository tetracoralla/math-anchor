"""Arm runners for the trust/fail-closed smoke.

B_template is a fair cached instantiation without pack identity/domain checks.
P-pack reuses the existing shifted-square apply / certificate / obligation path.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from math_anchor.errors import CalculatorError

from research.reuse_benefit_eval.arms import (
    empty_construction_trace,
    is_arm_exception as _reuse_is_arm_exception,
    trace_construction_calls,
)
from research.reuse_benefit_eval.template import (
    CACHED_G,
    TemplateBaselineError,
    _K,
    evaluate_template,
)

from .protocol import (
    ARM_B_TEMPLATE,
    ARM_P_PACK,
    SAVED_G_CANONICAL,
    SAVED_G_CUBES,
    SAVED_G_LINEAR,
    saved_g_source,
)


class ArmExecutionError(CalculatorError):
    """Smoke arm failed before producing a result object."""


# Built from symbols (no string sympify / parse_expr). Same polynomials as the
# pre-registered savedG sources in protocol.json.
_SAVED_G_EXPR = {
    SAVED_G_CANONICAL: CACHED_G,
    SAVED_G_LINEAR: _K,
    SAVED_G_CUBES: (_K ** 2) * ((_K - 1) ** 2) / 4,
}


def run_arm(arm_id: str, task: dict[str, Any], *, protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    if arm_id == ARM_B_TEMPLATE:
        return run_b_template(task, protocol=protocol)
    if arm_id == ARM_P_PACK:
        return run_p_pack(task, protocol=protocol)
    raise ArmExecutionError("E_INPUT", f"unknown trust/fail-closed arm: {arm_id}")


def run_b_template(task: dict[str, Any], *, protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fair template: family matching on, pack identity/domain checks off."""

    saved_id = str(task.get("savedG") or SAVED_G_CANONICAL)
    cached_g = _SAVED_G_EXPR.get(saved_id)
    if cached_g is None:
        raise ArmExecutionError("E_INPUT", f"unknown savedG id for B_template: {saved_id}")
    source = saved_g_source(saved_id, protocol)
    result = evaluate_template(
        task,
        cached_g=cached_g,
        cached_formula=source,
        enforce_bound_magnitude_limit=False,
    )
    result["savedG"] = saved_id
    result["packIdentityChecks"] = False
    result["packDomainChecks"] = False
    return result


def run_p_pack(task: dict[str, Any], *, protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    """Frozen shifted-square apply with optional saved-G mutation. No reconstruction."""

    from research.method_packs.apply import apply_method_pack
    from research.method_packs.format import DEFAULT_PARAM_PACK_PATH, PARAM_PACK_ID
    from research.method_packs.loader import load_pack

    pack = deepcopy(load_pack(DEFAULT_PARAM_PACK_PATH))
    if pack.get("id") != PARAM_PACK_ID:
        raise ArmExecutionError(
            "E_INPUT",
            "P-pack arm loaded a pack that is not the shifted-square pack",
            {"loadedId": pack.get("id"), "expectedId": PARAM_PACK_ID},
        )
    saved_id = str(task.get("savedG") or SAVED_G_CANONICAL)
    if saved_id != SAVED_G_CANONICAL:
        semantics = pack.get("mathSemantics")
        if not isinstance(semantics, dict) or not isinstance(semantics.get("parametricAntidifference"), dict):
            raise ArmExecutionError("E_INPUT", "shifted-square pack is missing parametricAntidifference")
        semantics["parametricAntidifference"]["source"] = saved_g_source(saved_id, protocol)
    payload: dict[str, Any] = {
        "summand": str(task["summand"]),
        "variable": str(task.get("variable") or "k"),
        "lower": task["lower"],
        "upper": task["upper"],
    }
    task_id = task.get("taskId")
    if isinstance(task_id, str) and task_id:
        payload["taskId"] = task_id
    parameter_c = task.get("parameterC")
    if parameter_c is not None:
        payload["parameterC"] = parameter_c
    result = apply_method_pack(payload, pack=pack, compare_baseline=False)
    wrapped = dict(result)
    chain = result.get("chain") if isinstance(result.get("chain"), list) else []
    steps = [item.get("step") for item in chain if isinstance(item, dict) and isinstance(item.get("step"), str)]
    wrapped["stepsExecuted"] = steps
    if "usedSavedContent" not in wrapped:
        wrapped["usedSavedContent"] = (
            wrapped.get("constructor") == "instantiated-saved-parametric-antidifference"
        )
    wrapped["independentChecker"] = True
    wrapped["floatingApproximation"] = False
    wrapped["savedG"] = saved_id
    wrapped["packIdentityChecks"] = True
    wrapped["packDomainChecks"] = True
    return wrapped


def is_arm_exception(error: BaseException) -> bool:
    return _reuse_is_arm_exception(error) or isinstance(error, (ArmExecutionError, TemplateBaselineError))


__all__ = [
    "ArmExecutionError",
    "empty_construction_trace",
    "is_arm_exception",
    "run_arm",
    "run_b_template",
    "run_p_pack",
    "trace_construction_calls",
]
