"""Equal-budget arm runners for the parameterized cost smoke.

B0 does not load the method pack. B1 may construct. P-pack must not.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from math_anchor.errors import CalculatorError

from research.polynomial_finite_sum_proposal.baseline import sympy_finite_sum
from research.polynomial_finite_sum_proposal.polynomials import DomainError
from research.polynomial_finite_sum_proposal.runner import run_polynomial_finite_sum

from .protocol import ARM_B0, ARM_B1, ARM_P_PACK


class ArmExecutionError(CalculatorError):
    """Smoke arm failed before producing a result object."""


def run_arm(arm_id: str, task: dict[str, Any]) -> dict[str, Any]:
    if arm_id == ARM_B0:
        return run_b0(task)
    if arm_id == ARM_B1:
        return run_b1(task)
    if arm_id == ARM_P_PACK:
        return run_p_pack(task)
    raise ArmExecutionError("E_INPUT", f"unknown parameterized cost-smoke arm: {arm_id}")


def run_b0(task: dict[str, Any]) -> dict[str, Any]:
    """SymPy summation baseline. Does not import or apply the method pack."""

    return sympy_finite_sum(
        summand=str(task["summand"]),
        variable=str(task.get("variable") or "k"),
        lower=task["lower"],
        upper=task["upper"],
    )


def run_b1(task: dict[str, Any]) -> dict[str, Any]:
    """A1 runner with construction allowed and no embedded B0 comparison."""

    return run_polynomial_finite_sum(
        summand=str(task["summand"]),
        variable=str(task.get("variable") or "k"),
        lower=task["lower"],
        upper=task["upper"],
        compare_baseline=False,
    )


def run_p_pack(task: dict[str, Any]) -> dict[str, Any]:
    """Frozen shifted-square apply. Imported here so B0/B1 need not load the pack module."""

    from research.method_packs.apply import apply_method_pack
    from research.method_packs.format import DEFAULT_PARAM_PACK_PATH, PARAM_PACK_ID
    from research.method_packs.loader import load_pack

    pack = load_pack(DEFAULT_PARAM_PACK_PATH)
    if pack.get("id") != PARAM_PACK_ID:
        raise ArmExecutionError(
            "E_INPUT",
            "P-pack arm loaded a pack that is not the shifted-square pack",
            {"loadedId": pack.get("id"), "expectedId": PARAM_PACK_ID},
        )
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
    return apply_method_pack(payload, pack=pack, compare_baseline=False)


def is_arm_exception(error: BaseException) -> bool:
    from research.method_packs.apply import PackApplicationError
    from research.method_packs.loader import PackFormatError

    return isinstance(
        error,
        (DomainError, PackApplicationError, PackFormatError, ArmExecutionError, CalculatorError),
    )


@contextmanager
def trace_construction_calls() -> Iterator[dict[str, int]]:
    """Wrap Gosper/construct bindings used by B1. JSON gosperCalled is not this probe."""

    import sympy.concrete.gosper as gosper_mod

    from research.polynomial_finite_sum_proposal import polynomials
    from research.polynomial_finite_sum_proposal import runner as a1_runner

    counts = {"gosper_sum": 0, "construct_antidifference": 0}
    orig_runner_construct = a1_runner.construct_antidifference
    orig_poly_construct = polynomials.construct_antidifference
    orig_poly_gosper = polynomials.gosper_sum
    orig_sympy_gosper = gosper_mod.gosper_sum

    def wrap_construct(original):
        def wrapped(*args: object, **kwargs: object):
            counts["construct_antidifference"] += 1
            return original(*args, **kwargs)

        return wrapped

    def wrap_gosper(original):
        def wrapped(*args: object, **kwargs: object):
            counts["gosper_sum"] += 1
            return original(*args, **kwargs)

        return wrapped

    a1_runner.construct_antidifference = wrap_construct(orig_runner_construct)
    polynomials.construct_antidifference = wrap_construct(orig_poly_construct)
    polynomials.gosper_sum = wrap_gosper(orig_poly_gosper)
    gosper_mod.gosper_sum = wrap_gosper(orig_sympy_gosper)
    try:
        yield counts
    finally:
        a1_runner.construct_antidifference = orig_runner_construct
        polynomials.construct_antidifference = orig_poly_construct
        polynomials.gosper_sum = orig_poly_gosper
        gosper_mod.gosper_sum = orig_sympy_gosper
