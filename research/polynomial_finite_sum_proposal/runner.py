"""Ordinary Python procedure chain for the polynomial finite-sum proposal.

Steps:
1. parse and reject out-of-domain input;
2. construct G with SymPy Gosper/summation (untrusted construction);
3. check G(k+1)-G(k)=p(k) through the existing polynomial-identity obligation
   plus the independent stdlib certificate checker;
4. evaluate G at the integer endpoints with that same checker language;
5. apply the hand-provided telescoping combination rule.

The obligation runtime is used as one identity check. It is not a workflow DSL:
dependsOn is unused, and the combination rule is ordinary Python.
"""

from __future__ import annotations

from typing import Any

from math_anchor import __version__
from math_anchor.obligations import OBLIGATION_SET_SCHEMA_VERSION, check_obligation_set
from math_anchor.safe_expression import make_symbols

from .baseline import sympy_finite_sum
from .polynomials import (
    DomainError,
    construct_antidifference,
    difference_identity_sources,
    evaluate_univariate,
    fraction_payload,
    parse_antidifference,
    parse_summand,
    require_integer,
)
from .telescoping import (
    TelescopingRuleError,
    apply_finite_telescoping_sum,
    rule_metadata,
)


PROPOSAL_ID = "math-anchor.research.polynomial-finite-sum.v0"


def run_polynomial_finite_sum(
    *,
    summand: str,
    variable: str = "k",
    lower: object,
    upper: object,
    antidifference: str | None = None,
    compare_baseline: bool = True,
) -> dict[str, Any]:
    start = require_integer("lower", lower)
    stop = require_integer("upper", upper)
    if stop < start - 1:
        raise DomainError(
            "E_DOMAIN",
            "reversed bounds with upper < lower - 1 are unsupported; "
            "empty sums are only the case upper == lower - 1",
        )

    summand_source, summand_terms, summand_expr = parse_summand(summand, variable)
    if antidifference is None:
        symbol = make_symbols([variable])[variable]
        g_terms, constructor = construct_antidifference(summand_expr, symbol)
    else:
        g_terms = parse_antidifference(antidifference, variable)
        constructor = "caller-supplied-antidifference"

    sources = difference_identity_sources(g_terms, summand_terms, variable)
    feedback, receipt = check_obligation_set(
        {
            "schemaVersion": OBLIGATION_SET_SCHEMA_VERSION,
            "assumptionSets": [
                {
                    "id": "discrete-sum-domain",
                    "assumptions": [
                        f"{variable} is a commuting indeterminate over the rationals",
                        "the summation index ranges over integers",
                    ],
                }
            ],
            "obligations": [
                {
                    "id": "difference-identity",
                    "kind": "polynomial_identity",
                    "claim": {
                        "left": sources["left"],
                        "right": sources["right"],
                        "variables": [variable],
                    },
                    "assumptionSet": "discrete-sum-domain",
                }
            ],
            "responseMode": "full",
        }
    )
    identity_entry = receipt["obligations"][0]
    if identity_entry["status"] != "checked":
        return {
            "status": identity_entry["status"],
            "kind": PROPOSAL_ID,
            "reason": "difference_identity_not_checked",
            "summand": summand_source,
            "variable": variable,
            "lower": start,
            "upper": stop,
            "antidifference": sources["antidifference"],
            "constructor": constructor,
            "identity": {
                "left": sources["left"],
                "right": sources["right"],
                "status": identity_entry["status"],
                "assuranceLevel": identity_entry["assuranceLevel"],
                "detail": identity_entry["detail"],
            },
            "obligationReceipt": receipt,
            "obligationFeedback": feedback,
            "combinationRule": rule_metadata(),
            "formalKernelChecked": False,
            "limitations": [
                "difference_identity_was_not_established",
                "formal_kernel_not_used",
                "combination_rule_is_hand_provided_infrastructure",
            ],
        }

    g_source = sources["antidifference"]
    g_at_upper_plus_one = evaluate_univariate(g_source, variable, stop + 1)
    g_at_lower = evaluate_univariate(g_source, variable, start)
    try:
        value = apply_finite_telescoping_sum(
            difference_identity_checked=True,
            lower=start,
            upper=stop,
            g_at_upper_plus_one=g_at_upper_plus_one,
            g_at_lower=g_at_lower,
        )
    except TelescopingRuleError as error:
        raise DomainError(error.code, error.message) from error

    result: dict[str, Any] = {
        "status": "ok",
        "kind": PROPOSAL_ID,
        "runtime": {"name": "math-anchor", "version": __version__},
        "summand": summand_source,
        "variable": variable,
        "lower": start,
        "upper": stop,
        "antidifference": g_source,
        "constructor": constructor,
        "identity": {
            "left": sources["left"],
            "right": sources["right"],
            "status": identity_entry["status"],
            "assuranceLevel": identity_entry["assuranceLevel"],
            "scope": identity_entry["scope"],
            "certificateDigest": identity_entry["detail"].get("certificateDigest"),
            "checker": identity_entry["detail"].get("checker"),
            "claimDigest": identity_entry["claimDigest"],
        },
        "boundsConvention": {
            "inclusive": True,
            "integerIndex": True,
            "emptySum": "upper == lower - 1 yields 0",
            "reversedBounds": "unsupported when upper < lower - 1",
        },
        "endpoints": {
            "gAtUpperPlusOne": fraction_payload(g_at_upper_plus_one),
            "gAtLower": fraction_payload(g_at_lower),
        },
        "combinationRule": rule_metadata(),
        "value": fraction_payload(value),
        "formula": "G(upper + 1) - G(lower)",
        "obligationReceipt": receipt,
        "formalKernelChecked": False,
        "assuranceLevel": "exact_symbolic",
        "limitations": [
            "formal_kernel_not_used",
            "combination_rule_is_hand_provided_infrastructure",
            "natural_language_to_claim_translation_unchecked",
            "identity_scope_is_rational_polynomials_with_constant_denominators",
        ],
    }

    if compare_baseline:
        baseline = sympy_finite_sum(
            summand=summand,
            variable=variable,
            lower=start,
            upper=stop,
        )
        result["baseline"] = {
            "engine": baseline["engine"],
            "value": baseline["value"],
            "agrees": baseline["value"] == result["value"],
        }
        if not result["baseline"]["agrees"]:
            raise DomainError(
                "E_RUNTIME",
                "checked telescoping value disagrees with the SymPy summation baseline",
            )
    return result


def run_from_task(task: dict[str, Any], *, compare_baseline: bool = True) -> dict[str, Any]:
    if not isinstance(task, dict):
        raise DomainError("E_INPUT", "task must be a JSON object")
    unknown = set(task) - {
        "summand",
        "variable",
        "lower",
        "upper",
        "antidifference",
        "compareBaseline",
    }
    if unknown:
        raise DomainError("E_INPUT", f"unknown task fields: {', '.join(sorted(unknown))}")
    if "summand" not in task or "lower" not in task or "upper" not in task:
        raise DomainError("E_INPUT", "task requires summand, lower, and upper")
    variable = task.get("variable", "k")
    if not isinstance(variable, str):
        raise DomainError("E_INPUT", "variable must be a string")
    compare = task.get("compareBaseline", compare_baseline)
    if not isinstance(compare, bool):
        raise DomainError("E_INPUT", "compareBaseline must be a boolean")
    antidifference = task.get("antidifference")
    if antidifference is not None and not isinstance(antidifference, str):
        raise DomainError("E_INPUT", "antidifference must be a string when supplied")
    return run_polynomial_finite_sum(
        summand=str(task["summand"]),
        variable=variable,
        lower=task["lower"],
        upper=task["upper"],
        antidifference=antidifference,
        compare_baseline=compare,
    )
