"""Equal-budget arm runners for the reuse-benefit smoke.

B0/B1 may construct. B_template/B_codegen may cache. P-pack must not reconstruct.
Benefit comparison does not cripple the baselines.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from math_anchor.errors import CalculatorError

from research.polynomial_finite_sum_proposal.baseline import sympy_finite_sum
from research.polynomial_finite_sum_proposal.polynomials import DomainError
from research.polynomial_finite_sum_proposal.runner import run_polynomial_finite_sum

from .codegen import CodegenBaselineError, evaluate_codegen
from .protocol import (
    ARM_B0,
    ARM_B1,
    ARM_B_CODEGEN,
    ARM_B_TEMPLATE,
    ARM_P_PACK,
    CONSTRUCTION_TRACE_KEYS,
)
from .template import TemplateBaselineError, evaluate_template


class ArmExecutionError(CalculatorError):
    """Smoke arm failed before producing a result object."""


def run_arm(arm_id: str, task: dict[str, Any]) -> dict[str, Any]:
    if arm_id == ARM_B0:
        return run_b0(task)
    if arm_id == ARM_B1:
        return run_b1(task)
    if arm_id == ARM_B_TEMPLATE:
        return run_b_template(task)
    if arm_id == ARM_B_CODEGEN:
        return run_b_codegen(task)
    if arm_id == ARM_P_PACK:
        return run_p_pack(task)
    raise ArmExecutionError("E_INPUT", f"unknown reuse-benefit arm: {arm_id}")


def run_b0(task: dict[str, Any]) -> dict[str, Any]:
    """SymPy summation baseline. Does not import or apply the method pack."""

    result = sympy_finite_sum(
        summand=str(task["summand"]),
        variable=str(task.get("variable") or "k"),
        lower=task["lower"],
        upper=task["upper"],
    )
    wrapped = dict(result)
    wrapped["stepsExecuted"] = ["cas_summation"]
    wrapped["usedSavedContent"] = False
    wrapped["gosperCalled"] = False
    wrapped["independentChecker"] = False
    wrapped["floatingApproximation"] = False
    return wrapped


def run_b1(task: dict[str, Any]) -> dict[str, Any]:
    """A1 runner with construction allowed and no embedded B0 comparison."""

    result = run_polynomial_finite_sum(
        summand=str(task["summand"]),
        variable=str(task.get("variable") or "k"),
        lower=task["lower"],
        upper=task["upper"],
        compare_baseline=False,
    )
    wrapped = dict(result)
    wrapped["stepsExecuted"] = [
        "construct_antidifference",
        "check_instance_identity",
        "evaluate_telescoping",
    ]
    wrapped["usedSavedContent"] = False
    wrapped["independentChecker"] = True
    wrapped["floatingApproximation"] = False
    return wrapped


def run_b_template(task: dict[str, Any]) -> dict[str, Any]:
    """Cached parametric G on the SymPy side. Fair template; not crippled."""

    return evaluate_template(task)


def run_b_codegen(task: dict[str, Any]) -> dict[str, Any]:
    """Exact QQ coefficient-table evaluator. Fair; not crippled."""

    return evaluate_codegen(task)


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
    result = apply_method_pack(payload, pack=pack, compare_baseline=False)
    wrapped = dict(result)
    chain = result.get("chain") if isinstance(result.get("chain"), list) else []
    steps = [item.get("step") for item in chain if isinstance(item, dict) and isinstance(item.get("step"), str)]
    wrapped["stepsExecuted"] = steps
    # Pass through apply's usedSavedContent. Do not overwrite True on every
    # non-raising return. Constructor is corroboration if apply omitted the field.
    # JSON gosperCalled is a path invariant; construction wrap/trace is the probe.
    if "usedSavedContent" not in wrapped:
        wrapped["usedSavedContent"] = (
            wrapped.get("constructor") == "instantiated-saved-parametric-antidifference"
        )
    wrapped["independentChecker"] = True
    wrapped["floatingApproximation"] = False
    return wrapped


def is_arm_exception(error: BaseException) -> bool:
    from research.method_packs.apply import PackApplicationError
    from research.method_packs.loader import PackFormatError

    return isinstance(
        error,
        (
            DomainError,
            PackApplicationError,
            PackFormatError,
            TemplateBaselineError,
            CodegenBaselineError,
            ArmExecutionError,
            CalculatorError,
        ),
    )


def empty_construction_trace() -> dict[str, int]:
    return {key: 0 for key in CONSTRUCTION_TRACE_KEYS}


@contextmanager
def trace_construction_calls() -> Iterator[dict[str, int]]:
    """Wrap reconstruction call sites. JSON gosperCalled is not this probe.

    Counts `gosper_sum`, `construct_antidifference`, `sympy.summation`, and
    `Sum.doit`. A future pack that reconstructed via CAS summation is visible
    on the P-pack arm. The wrap still calls the originals, so B0/B1 may use
    summation; scoring must not treat B0 summation as pack reconstruction.
    """

    import sympy as sp
    import sympy.concrete.gosper as gosper_mod
    import sympy.concrete.summations as summations_mod

    from research.polynomial_finite_sum_proposal import polynomials
    from research.polynomial_finite_sum_proposal import runner as a1_runner

    counts = empty_construction_trace()
    orig_runner_construct = a1_runner.construct_antidifference
    orig_poly_construct = polynomials.construct_antidifference
    orig_poly_gosper = polynomials.gosper_sum
    orig_sympy_gosper = gosper_mod.gosper_sum
    orig_summation = sp.summation
    orig_summations_summation = summations_mod.summation
    orig_sum_doit = sp.Sum.doit

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

    def wrap_summation(original):
        def wrapped(*args: object, **kwargs: object):
            counts["summation"] += 1
            return original(*args, **kwargs)

        return wrapped

    def wrap_doit(original):
        def wrapped(self, *args: object, **kwargs: object):
            counts["Sum.doit"] += 1
            return original(self, *args, **kwargs)

        return wrapped

    wrapped_summation = wrap_summation(orig_summation)
    a1_runner.construct_antidifference = wrap_construct(orig_runner_construct)
    polynomials.construct_antidifference = wrap_construct(orig_poly_construct)
    polynomials.gosper_sum = wrap_gosper(orig_poly_gosper)
    gosper_mod.gosper_sum = wrap_gosper(orig_sympy_gosper)
    sp.summation = wrapped_summation
    summations_mod.summation = (
        wrapped_summation
        if orig_summations_summation is orig_summation
        else wrap_summation(orig_summations_summation)
    )
    sp.Sum.doit = wrap_doit(orig_sum_doit)
    try:
        yield counts
    finally:
        a1_runner.construct_antidifference = orig_runner_construct
        polynomials.construct_antidifference = orig_poly_construct
        polynomials.gosper_sum = orig_poly_gosper
        gosper_mod.gosper_sum = orig_sympy_gosper
        sp.summation = orig_summation
        summations_mod.summation = orig_summations_summation
        sp.Sum.doit = orig_sum_doit
