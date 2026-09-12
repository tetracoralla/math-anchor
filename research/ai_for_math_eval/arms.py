"""Equal-budget arm runners. B0 does not load the method pack."""

from __future__ import annotations

from typing import Any

from math_anchor.errors import CalculatorError

from research.polynomial_finite_sum_proposal.baseline import sympy_finite_sum
from research.polynomial_finite_sum_proposal.polynomials import DomainError
from research.polynomial_finite_sum_proposal.runner import run_polynomial_finite_sum

from .protocol import ARM_B0, ARM_B1, ARM_B2, ARM_B2_MINUS


class ArmExecutionError(CalculatorError):
    """Smoke arm failed before producing a result object."""


def run_arm(arm_id: str, task: dict[str, Any]) -> dict[str, Any]:
    if arm_id == ARM_B0:
        return run_b0(task)
    if arm_id == ARM_B1:
        return run_b1(task)
    if arm_id == ARM_B2:
        return run_b2(task)
    if arm_id == ARM_B2_MINUS:
        return run_b2_minus(task)
    raise ArmExecutionError("E_INPUT", f"unknown A4 arm: {arm_id}")


def run_b0(task: dict[str, Any]) -> dict[str, Any]:
    """SymPy summation baseline. Does not import or apply the method pack."""

    return sympy_finite_sum(
        summand=str(task["summand"]),
        variable=str(task.get("variable") or "k"),
        lower=task["lower"],
        upper=task["upper"],
    )


def run_b1(task: dict[str, Any]) -> dict[str, Any]:
    """A1 runner with no extracted pack and no embedded B0 comparison."""

    return run_polynomial_finite_sum(
        summand=str(task["summand"]),
        variable=str(task.get("variable") or "k"),
        lower=task["lower"],
        upper=task["upper"],
        compare_baseline=False,
    )


def run_b2(task: dict[str, Any]) -> dict[str, Any]:
    """Frozen A2 pack apply. Imported here so B0/B1 need not load the pack module."""

    from research.method_packs.apply import apply_method_pack

    payload: dict[str, Any] = {
        "summand": str(task["summand"]),
        "variable": str(task.get("variable") or "k"),
        "lower": task["lower"],
        "upper": task["upper"],
    }
    task_id = task.get("taskId")
    if isinstance(task_id, str) and task_id:
        payload["taskId"] = task_id
    return apply_method_pack(payload, compare_baseline=False)


def run_b2_minus(task: dict[str, Any]) -> dict[str, Any]:
    """Drop-library contrast: same cubes task through B1, pack not loaded."""

    return run_b1(task)


def is_arm_exception(error: BaseException) -> bool:
    from research.method_packs.apply import PackApplicationError

    return isinstance(error, (DomainError, PackApplicationError, ArmExecutionError, CalculatorError))
