from __future__ import annotations

from decimal import Decimal, DecimalException, InvalidOperation, ROUND_HALF_EVEN, ROUND_HALF_UP, localcontext
from typing import Any

from ..errors import CalculatorError, require
from ..validation import enum_arg, integer_arg, list_arg, string_arg


_ROUNDING_MODES = {
    "half_even": ROUND_HALF_EVEN,
    "half_up": ROUND_HALF_UP,
}


def calculate(arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        return _calculate(arguments)
    except CalculatorError:
        raise
    except DecimalException as error:
        raise CalculatorError("E_DOMAIN", "financial calculation exceeded the configured decimal range") from error


def _calculate(arguments: dict[str, Any]) -> dict[str, Any]:
    action = enum_arg(
        arguments,
        "action",
        ("compound_value", "effective_annual_rate", "loan_payment", "npv", "irr"),
        default="compound_value",
    )
    precision = integer_arg(arguments, "precision", default=40, minimum=16, maximum=100)
    decimal_places = integer_arg(
        arguments,
        "decimalPlaces",
        default=12 if action in {"effective_annual_rate", "irr"} else 2,
        minimum=0,
        maximum=24,
    )
    rounding_mode = enum_arg(arguments, "roundingMode", tuple(_ROUNDING_MODES), default="half_even")
    warnings: list[str] = []

    with localcontext() as context:
        context.prec = precision
        if action == "compound_value":
            principal = _decimal_arg(arguments, "principal")
            annual_rate = _decimal_arg(arguments, "annualRate")
            periods_per_year = integer_arg(arguments, "periodsPerYear", default=12, minimum=1, maximum=100_000)
            number_of_periods = integer_arg(arguments, "numberOfPeriods", default=1, minimum=0, maximum=10_000_000)
            periodic_rate = annual_rate / Decimal(periods_per_year)
            require(Decimal(1) + periodic_rate > 0, "E_DOMAIN", "the periodic growth factor must be positive")
            value = principal * (Decimal(1) + periodic_rate) ** number_of_periods
            results = [
                _metric("future_value", value, "money", decimal_places, rounding_mode),
                _metric("periodic_rate", periodic_rate, "rate", min(24, max(decimal_places, 12)), rounding_mode),
            ]
            conventions = [
                "annualRate is a nominal decimal rate, not a percentage number",
                "interest compounds once per period and numberOfPeriods is an integer",
                "cash flow occurs at the start and the result at the end of the final period",
            ]
            method = "closed_form_compound_interest"
            converged = None
            iterations = None
            error_bound = None
            residual = None
        elif action == "effective_annual_rate":
            nominal_rate = _decimal_arg(arguments, "nominalAnnualRate")
            compounds_per_year = integer_arg(arguments, "compoundsPerYear", default=12, minimum=1, maximum=100_000)
            periodic_rate = nominal_rate / Decimal(compounds_per_year)
            require(Decimal(1) + periodic_rate > 0, "E_DOMAIN", "the periodic growth factor must be positive")
            effective_rate = (Decimal(1) + periodic_rate) ** compounds_per_year - Decimal(1)
            results = [
                _metric("effective_annual_rate", effective_rate, "rate", decimal_places, rounding_mode),
                _metric("periodic_rate", periodic_rate, "rate", min(24, max(decimal_places, 12)), rounding_mode),
            ]
            conventions = [
                "nominalAnnualRate is an APR-style nominal decimal rate, not a percentage number",
                "the nominal rate is divided evenly across compoundsPerYear",
                "fees, day-count rules, and jurisdiction-specific regulatory APR disclosures are excluded",
            ]
            method = "nominal_to_effective_annual_rate"
            converged = None
            iterations = None
            error_bound = None
            residual = None
        elif action == "loan_payment":
            principal = _decimal_arg(arguments, "principal")
            annual_rate = _decimal_arg(arguments, "annualRate")
            payments_per_year = integer_arg(arguments, "paymentsPerYear", default=12, minimum=1, maximum=100_000)
            number_of_payments = integer_arg(arguments, "numberOfPayments", default=1, minimum=1, maximum=10_000_000)
            require(principal >= 0, "E_DOMAIN", "principal must be nonnegative")
            periodic_rate = annual_rate / Decimal(payments_per_year)
            require(periodic_rate > -1, "E_DOMAIN", "the periodic rate must be greater than -1")
            if periodic_rate == 0:
                payment = principal / Decimal(number_of_payments)
            else:
                factor = (Decimal(1) + periodic_rate) ** number_of_payments
                payment = principal * periodic_rate * factor / (factor - Decimal(1))
            total_paid = payment * number_of_payments
            results = [
                _metric("payment", payment, "money", decimal_places, rounding_mode),
                _metric("total_paid", total_paid, "money", decimal_places, rounding_mode),
                _metric("total_interest", total_paid - principal, "money", decimal_places, rounding_mode),
                _metric("periodic_rate", periodic_rate, "rate", min(24, max(decimal_places, 12)), rounding_mode),
            ]
            conventions = [
                "annualRate is a nominal decimal rate divided evenly across paymentsPerYear",
                "payments are equal and occur at the end of each period",
                "fees, taxes, day-count adjustments, and irregular dates are excluded",
            ]
            method = "closed_form_ordinary_annuity"
            converged = None
            iterations = None
            error_bound = None
            residual = None
        elif action == "npv":
            cash_flows = _cash_flows(arguments)
            periodic_rate = _decimal_arg(arguments, "ratePerPeriod")
            require(periodic_rate > -1, "E_DOMAIN", "ratePerPeriod must be greater than -1")
            value = _npv(cash_flows, periodic_rate)
            results = [_metric("net_present_value", value, "money", decimal_places, rounding_mode)]
            conventions = [
                "cashFlows[0] occurs now and each later cash flow occurs one equal period later",
                "ratePerPeriod is a decimal rate for exactly one cash-flow interval",
                "irregular dates, taxes, and reinvestment assumptions are excluded",
            ]
            method = "discounted_cash_flow_sum"
            converged = None
            iterations = None
            error_bound = None
            residual = None
        else:
            cash_flows = _cash_flows(arguments)
            require(any(value < 0 for value in cash_flows) and any(value > 0 for value in cash_flows), "E_DOMAIN", "IRR requires at least one negative and one positive cash flow")
            lower = _decimal_arg(arguments, "lowerRate")
            upper = _decimal_arg(arguments, "upperRate")
            require(Decimal(-1) < lower < upper, "E_INPUT", "IRR bounds must satisfy -1 < lowerRate < upperRate")
            tolerance = _decimal_arg(arguments, "tolerance", default="1e-18")
            require(tolerance > 0, "E_INPUT", "tolerance must be positive")
            max_iterations = integer_arg(arguments, "maxIterations", default=256, minimum=1, maximum=2_000)
            root, error, residual_value, iterations = _bracketed_irr(
                cash_flows,
                lower,
                upper,
                tolerance,
                max_iterations,
            )
            results = [_metric("internal_rate_of_return", root, "rate", decimal_places, rounding_mode)]
            conventions = [
                "cashFlows[0] occurs now and later cash flows occur at equal period intervals",
                "IRR is the bracketed rate where NPV is zero; the returned rate is per cash-flow interval",
                "the supplied bracket selects one root and does not prove that another IRR is absent",
            ]
            sign_changes = _cash_flow_sign_changes(cash_flows)
            if sign_changes > 1:
                warnings.append("Cash flows change sign more than once, so multiple IRRs may exist outside or inside other brackets.")
            method = "decimal_bisection"
            converged = True
            error_bound = str(error)
            residual = str(residual_value)

    return {
        "status": "ok",
        "operation": "finance.calculate",
        "kind": "financial",
        "action": action,
        "results": results,
        "method": method,
        "conventions": conventions,
        "precision": precision,
        "rounding": {"decimalPlaces": decimal_places, "mode": rounding_mode},
        "converged": converged,
        "iterations": iterations,
        "errorBound": error_bound,
        "residual": residual,
        "warnings": warnings,
    }


def _decimal_arg(arguments: dict[str, Any], name: str, *, default: str | None = None) -> Decimal:
    text = string_arg(arguments, name, default=default, max_length=256)
    try:
        value = Decimal(text)
    except InvalidOperation as error:
        raise CalculatorError("E_INPUT", f"{name} must be decimal text") from error
    require(value.is_finite(), "E_DOMAIN", f"{name} must be finite")
    return value


def _cash_flows(arguments: dict[str, Any]) -> list[Decimal]:
    raw_values = list_arg(arguments, "cashFlows", minimum=2, maximum=10_000)
    values = []
    for index, raw_value in enumerate(raw_values):
        require(isinstance(raw_value, str), "E_INPUT", f"cashFlows[{index}] must be decimal text")
        try:
            value = Decimal(raw_value)
        except InvalidOperation as error:
            raise CalculatorError("E_INPUT", f"cashFlows[{index}] must be decimal text") from error
        require(value.is_finite(), "E_DOMAIN", f"cashFlows[{index}] must be finite")
        values.append(value)
    return values


def _metric(
    name: str,
    value: Decimal,
    unit: str,
    decimal_places: int,
    rounding_mode: str,
) -> dict[str, Any]:
    quantum = Decimal(1).scaleb(-decimal_places)
    rounded = value.quantize(quantum, rounding=_ROUNDING_MODES[rounding_mode])
    return {
        "name": name,
        "exact": None,
        "approx": format(rounded, "f"),
        "unit": unit,
        "decimalPlaces": decimal_places,
        "roundingMode": rounding_mode,
    }


def _npv(cash_flows: list[Decimal], rate: Decimal) -> Decimal:
    growth = Decimal(1) + rate
    require(growth > 0, "E_DOMAIN", "discount growth factor must be positive")
    return sum(
        (cash_flow / (growth**period) for period, cash_flow in enumerate(cash_flows)),
        Decimal(0),
    )


def _bracketed_irr(
    cash_flows: list[Decimal],
    lower: Decimal,
    upper: Decimal,
    tolerance: Decimal,
    max_iterations: int,
) -> tuple[Decimal, Decimal, Decimal, int]:
    lower_value = _npv(cash_flows, lower)
    upper_value = _npv(cash_flows, upper)
    require(
        lower_value == 0 or upper_value == 0 or (lower_value < 0 < upper_value) or (upper_value < 0 < lower_value),
        "E_DOMAIN",
        "IRR bounds must bracket an NPV sign change",
    )
    if lower_value == 0:
        return lower, Decimal(0), Decimal(0), 0
    if upper_value == 0:
        return upper, Decimal(0), Decimal(0), 0
    midpoint = (lower + upper) / Decimal(2)
    midpoint_value = _npv(cash_flows, midpoint)
    for iteration in range(1, max_iterations + 1):
        midpoint = (lower + upper) / Decimal(2)
        midpoint_value = _npv(cash_flows, midpoint)
        error = (upper - lower) / Decimal(2)
        if midpoint_value == 0 or error <= tolerance:
            return midpoint, error, abs(midpoint_value), iteration
        if (lower_value < 0 < midpoint_value) or (midpoint_value < 0 < lower_value):
            upper = midpoint
            upper_value = midpoint_value
        else:
            lower = midpoint
            lower_value = midpoint_value
    raise CalculatorError(
        "E_CONVERGENCE",
        f"IRR bisection did not reach tolerance within {max_iterations} iterations",
        {"errorBound": str((upper - lower) / Decimal(2)), "residual": str(abs(midpoint_value))},
    )


def _cash_flow_sign_changes(cash_flows: list[Decimal]) -> int:
    nonzero_signs = [value > 0 for value in cash_flows if value != 0]
    return sum(left != right for left, right in zip(nonzero_signs, nonzero_signs[1:]))
