from __future__ import annotations

from contextlib import contextmanager
from fractions import Fraction
import heapq
from typing import Any

import mpmath as mp
import sympy as sp

from ..errors import CalculatorError, require
from ..safe_expression import make_symbols, parse_expression
from ..validation import enum_arg, integer_arg, string_arg

iv = mp.iv

# Functions mpmath's interval context evaluates directly. Hyperbolic functions
# are expressed only in terms of interval exp and arithmetic because mpmath
# 1.3 does not expose interval sinh/cosh/tanh methods.
def _interval_sinh(value: Any) -> Any:
    positive = iv.exp(value)
    negative = iv.exp(-value)
    return (positive - negative) / 2


def _interval_cosh(value: Any) -> Any:
    positive = iv.exp(value)
    negative = iv.exp(-value)
    return (positive + negative) / 2


def _interval_tanh(value: Any) -> Any:
    positive = iv.exp(value)
    negative = iv.exp(-value)
    return (positive - negative) / (positive + negative)


_DIRECT_FUNCTIONS = {
    sp.sin: iv.sin,
    sp.cos: iv.cos,
    sp.tan: iv.tan,
    sp.exp: iv.exp,
    sp.log: iv.log,
    sp.sqrt: iv.sqrt,
    sp.gamma: iv.gamma,
    sp.sinh: _interval_sinh,
    sp.cosh: _interval_cosh,
    sp.tanh: _interval_tanh,
}
_MONOTONE_FUNCTIONS = {
    sp.asin: mp.asin,
    sp.acos: mp.acos,
    sp.atan: mp.atan,
}
_MAX_INTERVAL_EXPONENT = 128


@contextmanager
def _interval_workdps(precision: int) -> Any:
    previous = iv.dps
    iv.dps = precision
    try:
        yield
    finally:
        iv.dps = previous


class _BudgetExhausted(Exception):
    """Internal signal that the evaluation budget ran out; the caller
    degrades to a best-known enclosure instead of failing."""


class _IntervalTranslator:
    """Evaluate a parsed SymPy expression over mpmath intervals.

    Every enclosure is checked for finiteness: mpmath returns (-inf, +inf)
    style enclosures for operations that are undefined somewhere inside the
    interval (log across zero, tan across a pole, division by an interval
    containing zero), and those cases must surface as domain errors because
    the enclosure only holds where the expression is defined everywhere
    on the bracket.
    """

    def __init__(self, symbol: sp.Symbol, precision: int) -> None:
        self.symbol = symbol
        self.precision = precision
        self.padding = mp.mpf(10) ** (-(precision + 5))

    def enclosure(self, expression: sp.Expr, interval: Any) -> Any:
        if expression == self.symbol:
            return interval
        if expression is sp.pi:
            return iv.pi
        if expression is sp.E:
            return iv.e
        if isinstance(expression, sp.Rational):
            return iv.mpf(str(expression))
        if expression.is_Number:
            return iv.mpf(sp.sstr(expression))
        if isinstance(expression, sp.Add):
            total = self.enclosure(expression.args[0], interval)
            for term in expression.args[1:]:
                total = total + self.enclosure(term, interval)
            return self._checked(total)
        if isinstance(expression, sp.Mul):
            product = self.enclosure(expression.args[0], interval)
            for factor in expression.args[1:]:
                product = product * self.enclosure(factor, interval)
            return self._checked(product)
        if isinstance(expression, sp.Pow):
            base = self.enclosure(expression.args[0], interval)
            exponent = expression.args[1]
            if not exponent.is_number:
                raise CalculatorError("E_DOMAIN", "interval evaluation requires numeric exponents")
            return self._checked(self._power(base, exponent))
        if isinstance(expression, sp.Abs):
            inner = self.enclosure(expression.args[0], interval)
            return self._checked(iv.mpf([iv.absmin(inner), iv.absmax(inner)]))
        if isinstance(expression, sp.floor):
            inner = self.enclosure(expression.args[0], interval)
            return self._checked(iv.mpf([mp.floor(mp.mpf(inner.a)), mp.floor(mp.mpf(inner.b))]))
        if isinstance(expression, sp.ceiling):
            inner = self.enclosure(expression.args[0], interval)
            return self._checked(iv.mpf([mp.ceil(mp.mpf(inner.a)), mp.ceil(mp.mpf(inner.b))]))
        if isinstance(expression, (sp.Max, sp.Min)):
            combine = max if isinstance(expression, sp.Max) else min
            result = self.enclosure(expression.args[0], interval)
            for argument in expression.args[1:]:
                other = self.enclosure(argument, interval)
                result = iv.mpf(
                    [
                        combine(mp.mpf(result.a), mp.mpf(other.a)),
                        combine(mp.mpf(result.b), mp.mpf(other.b)),
                    ]
                )
            return self._checked(result)
        if isinstance(expression, sp.Function):
            evaluator = _DIRECT_FUNCTIONS.get(expression.func)
            if evaluator is not None and len(expression.args) == 1:
                return self._checked(evaluator(self.enclosure(expression.args[0], interval)))
            scalar = _MONOTONE_FUNCTIONS.get(expression.func)
            if scalar is not None and len(expression.args) == 1:
                inner = self.enclosure(expression.args[0], interval)
                return self._checked(
                    self._monotone_enclosure(scalar, mp.mpf(inner.a), mp.mpf(inner.b))
                )
            if isinstance(expression, sp.factorial) and len(expression.args) == 1:
                inner = self.enclosure(expression.args[0], interval)
                return self._checked(iv.gamma(inner + iv.mpf([1, 1])))
            raise CalculatorError(
                "E_DOMAIN",
                f"global optimization does not support {expression.func.__name__} over intervals",
            )
        raise CalculatorError("E_DOMAIN", "global optimization cannot evaluate this expression over intervals")

    def _monotone_enclosure(self, scalar: Any, low: mp.mpf, high: mp.mpf) -> Any:
        try:
            lower_values = (scalar(low, rounding="f"), scalar(high, rounding="f"))
            upper_values = (scalar(low, rounding="c"), scalar(high, rounding="c"))
        except (ArithmeticError, ValueError) as error:
            raise CalculatorError(
                "E_DOMAIN",
                "the expression is undefined or not real somewhere inside the bracket",
            ) from error
        return iv.mpf([min(lower_values), max(upper_values)])

    def _power(self, base: Any, exponent: sp.Expr) -> Any:
        if isinstance(exponent, sp.Float):
            fraction = Fraction(sp.sstr(exponent))
        elif isinstance(exponent, sp.Rational):
            fraction = Fraction(str(exponent))
        elif isinstance(exponent, sp.Integer):
            fraction = Fraction(int(exponent))
        elif exponent in (sp.pi, sp.E):
            raise CalculatorError("E_DOMAIN", "transcendental exponents are not supported by interval optimization")
        else:
            raise CalculatorError("E_DOMAIN", "interval evaluation requires numeric exponents")
        numerator, denominator = fraction.numerator, fraction.denominator
        require(
            abs(numerator) <= _MAX_INTERVAL_EXPONENT and abs(denominator) <= _MAX_INTERVAL_EXPONENT,
            "E_LIMIT",
            "interval exponents and root degrees are limited in magnitude",
        )
        result = base
        if denominator != 1:
            result = self._rational_root(base, denominator)
        power = abs(numerator)
        accumulated = iv.mpf([1, 1])
        while power:
            if power & 1:
                accumulated = accumulated * result
            result = result * result
            power >>= 1
        if numerator < 0:
            return iv.mpf([1, 1]) / self._checked(accumulated)
        return accumulated

    def _rational_root(self, base: Any, degree: int) -> Any:
        low, high = mp.mpf(base.a), mp.mpf(base.b)
        padded_low = low - abs(low) * self.padding - self.padding
        padded_high = high + abs(high) * self.padding + self.padding
        if degree % 2 == 0:
            require(
                padded_low >= 0,
                "E_DOMAIN",
                "even roots are undefined on intervals containing negative values",
            )
            padded_low = max(padded_low, mp.mpf(0))
        return iv.mpf(
            [
                self._pad_scalar(mp.root(padded_low, degree), -1),
                self._pad_scalar(mp.root(padded_high, degree), 1),
            ]
        )

    def _pad_scalar(self, value: mp.mpf, direction: int) -> mp.mpf:
        return value + direction * (abs(value) * self.padding + self.padding)

    @staticmethod
    def _checked(interval: Any) -> Any:
        if not (mp.isfinite(interval.a) and mp.isfinite(interval.b)):
            raise CalculatorError(
                "E_DOMAIN",
                "the expression is undefined or not real somewhere inside the bracket",
            )
        return interval


def minimize(arguments: dict[str, Any]) -> dict[str, Any]:
    expression_text = string_arg(arguments, "expression")
    variable = string_arg(arguments, "variable", max_length=64)
    bracket = arguments.get("bracket")
    require(
        isinstance(bracket, list)
        and len(bracket) == 2
        and all(isinstance(value, (int, float, str)) and not isinstance(value, bool) for value in bracket),
        "E_INPUT",
        "bracket must contain two numbers or decimal strings",
    )
    objective = enum_arg(arguments, "objective", ("minimum", "maximum"), default="minimum")
    tolerance_text = string_arg(arguments, "tolerance", default="1e-12", max_length=64)
    argmin_tolerance_text = string_arg(arguments, "argminTolerance", default="1e-8", max_length=64)
    precision = integer_arg(arguments, "precision", default=30, minimum=16, maximum=100)
    max_evaluations = integer_arg(arguments, "maxEvaluations", default=20_000, minimum=32, maximum=1_000_000)
    symbols = make_symbols([variable])
    expression = parse_expression(expression_text, symbols=symbols)
    target = expression if objective == "minimum" else -expression

    with mp.workdps(precision + 12), _interval_workdps(precision + 12):
        try:
            lower_input = iv.mpf(str(bracket[0]))
            upper_input = iv.mpf(str(bracket[1]))
            lower = mp.mpf(lower_input.a)
            upper = mp.mpf(upper_input.b)
            tolerance = mp.mpf(tolerance_text)
            argmin_tolerance = mp.mpf(argmin_tolerance_text)
        except (TypeError, ValueError) as error:
            raise CalculatorError("E_INPUT", "bracket and tolerances must be decimal text") from error
        require(mp.isfinite(lower) and mp.isfinite(upper), "E_DOMAIN", "bracket must be finite")
        require(lower < upper, "E_INPUT", "bracket must be ordered from lower to upper")
        require(
            mp.isfinite(tolerance) and tolerance > 0 and mp.isfinite(argmin_tolerance) and argmin_tolerance > 0,
            "E_INPUT",
            "tolerances must be positive and finite",
        )

        translator = _IntervalTranslator(symbols[variable], precision)
        derivative_target = sp.diff(target, symbols[variable])
        derivative_translator = (
            None if derivative_target == 0 else _IntervalTranslator(symbols[variable], precision)
        )
        state = {"evaluations": 0}

        def raw_enclosure(expression: sp.Expr, sub_translator: _IntervalTranslator, interval: Any) -> Any:
            try:
                return sub_translator.enclosure(expression, interval)
            except CalculatorError:
                raise
            except (ArithmeticError, ValueError) as error:
                # mpmath raises raw errors (log of a negative endpoint,
                # domain violations) instead of returning infinite
                # enclosures for some shapes; both mean the same thing.
                raise CalculatorError(
                    "E_DOMAIN",
                    "the expression is undefined or not real somewhere inside the bracket",
                ) from error

        def interval_enclosure(low: mp.mpf, high: mp.mpf) -> Any:
            if state["evaluations"] >= max_evaluations:
                raise _BudgetExhausted
            state["evaluations"] += 1
            interval = iv.mpf([low, high])
            base = raw_enclosure(target, translator, interval)
            if derivative_translator is None:
                return base
            # Mean-value form: f([low, high]) is contained in
            # f(m) + f'([low, high]) * ([low, high] - m). Around a critical
            # point the derivative enclosure itself shrinks with the width,
            # so this bound is quadratic where plain interval evaluation of
            # the expression stays linear (dependency slack between separate
            # occurrences of the variable). Intersecting both forms keeps
            # whichever is tighter.
            if state["evaluations"] >= max_evaluations:
                raise _BudgetExhausted
            state["evaluations"] += 1
            try:
                prime = raw_enclosure(derivative_target, derivative_translator, interval)
            except CalculatorError as error:
                if error.code != "E_DOMAIN":
                    raise
                # A function can be defined on a closed bracket while its
                # derivative is singular at an endpoint (acos on [-1, 1]) or
                # uses a derivative shape outside the supported interval
                # subset. Plain interval evaluation remains a valid enclosure;
                # only the optional mean-value tightening is unavailable.
                return base
            if state["evaluations"] >= max_evaluations:
                raise _BudgetExhausted
            state["evaluations"] += 1
            midpoint = (low + high) / 2
            middle_interval = iv.mpf([midpoint, midpoint])
            middle_value = raw_enclosure(target, translator, middle_interval)
            mean_value = middle_value + prime * (interval - middle_interval)
            combined_low = max(mp.mpf(base.a), mp.mpf(mean_value.a))
            combined_high = min(mp.mpf(base.b), mp.mpf(mean_value.b))
            require(
                mp.isfinite(combined_low)
                and mp.isfinite(combined_high)
                and combined_low <= combined_high,
                "E_DOMAIN",
                "the expression is undefined or not real somewhere inside the bracket",
            )
            return iv.mpf([combined_low, combined_high])

        def point_value(point: mp.mpf) -> mp.mpf:
            if state["evaluations"] >= max_evaluations:
                raise _BudgetExhausted
            state["evaluations"] += 1
            point_interval = raw_enclosure(target, translator, iv.mpf([point, point]))
            return mp.mpf(point_interval.b)

        # Branch and bound over interval lower bounds. The heap head bounds
        # the global minimum from below over everything unexplored; pruned
        # intervals have lower bound above the best attained value, so the
        # reported enclosure [global_lower, best_upper] is maintained at every
        # step, and the extremum intervals always form a cover of the true
        # minimizer set.
        heap: list[tuple[mp.mpf, int, mp.mpf, mp.mpf]] = []
        counter = 0
        explored = 0
        certified = False
        budget_exhausted = False
        argmin_intervals: list[tuple[mp.mpf, mp.mpf]] = []
        full = interval_enclosure(lower, upper)
        explored += 1
        best_upper = point_value((lower + upper) / 2)
        global_lower = mp.mpf(full.a)
        heapq.heappush(heap, (global_lower, counter, lower, upper))
        counter += 1
        try:
            while heap:
                bound, _, low, high = heapq.heappop(heap)
                global_lower = bound
                if best_upper - global_lower <= tolerance + tolerance * abs(best_upper):
                    # The popped interval is part of the minimizer cover;
                    # return it to the heap instead of dropping it.
                    certified = True
                    heapq.heappush(heap, (bound, counter, low, high))
                    counter += 1
                    break
                middle = (low + high) / 2
                for child_low, child_high in ((low, middle), (middle, high)):
                    child = interval_enclosure(child_low, child_high)
                    explored += 1
                    if mp.mpf(child.a) <= best_upper:
                        heapq.heappush(heap, (mp.mpf(child.a), counter, child_low, child_high))
                        counter += 1
                candidate = point_value(middle)
                if candidate < best_upper:
                    best_upper = candidate

            if certified:
                # Refine the surviving cover until every reported interval
                # is at most argminTolerance wide, pruning as the best value
                # tightens. Any interval left in the heap remains part of
                # the cover, so exhausting the budget here only widens the
                # reported intervals; it never invalidates them.
                while heap:
                    bound, _, low, high = heapq.heappop(heap)
                    if bound > best_upper:
                        continue
                    if high - low <= argmin_tolerance:
                        argmin_intervals.append((low, high))
                        continue
                    middle = (low + high) / 2
                    for child_low, child_high in ((low, middle), (middle, high)):
                        child = interval_enclosure(child_low, child_high)
                        explored += 1
                        if mp.mpf(child.a) <= best_upper:
                            heapq.heappush(heap, (mp.mpf(child.a), counter, child_low, child_high))
                            counter += 1
                    candidate = point_value(middle)
                    if candidate < best_upper:
                        best_upper = candidate
        except _BudgetExhausted:
            budget_exhausted = True

        if heap:
            remaining_lower = min(bound for bound, _, _, _ in heap)
            if not certified:
                # Everything unexplored still bounds the global minimum.
                global_lower = min(global_lower, remaining_lower)
            argmin_intervals.extend((low, high) for bound, _, low, high in heap if bound <= best_upper)
        evaluations = state["evaluations"]

    argmin_intervals.sort()
    merged: list[list[mp.mpf]] = []
    for low, high in argmin_intervals:
        if merged and low <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], high)
        else:
            merged.append([low, high])
    truncated = False
    if len(merged) > 64:
        merged = merged[:64]
        truncated = True
    widest = max((high - low for low, high in merged), default=mp.mpf(0))

    warnings = [
        "Internal mpmath interval bounds over the supported expression subset; certified means the requested value tolerance was reached, not an external certificate or proof-kernel check. The point estimate is the enclosure midpoint.",
    ]
    if not certified:
        warnings.append(
            "The value tolerance was not reached within maxEvaluations; the reported enclosure is the best internal interval bound obtained."
        )
    if certified and widest > argmin_tolerance:
        warnings.append(
            "The extremum intervals remain wider than argminTolerance because the evaluation budget was exhausted during refinement."
        )
    if truncated:
        warnings.append("More than 64 disjoint extremum intervals exist; the list was truncated.")

    value_low = mp.mpf(global_lower)
    value_high = mp.mpf(best_upper)
    if objective == "maximum":
        value_low, value_high = -value_high, -value_low
    enclosure_midpoint = (value_low + value_high) / 2
    return {
        "status": "ok" if certified else "uncertain",
        "operation": "numeric.minimize",
        "kind": "global_extremum",
        "objective": objective,
        "exact": None,
        "approx": mp.nstr(enclosure_midpoint, precision),
        "precision": precision,
        "method": "interval_branch_and_bound",
        "certified": certified,
        "tolerance": tolerance_text,
        "argminTolerance": argmin_tolerance_text,
        "valueEnclosure": [mp.nstr(value_low, precision), mp.nstr(value_high, precision)],
        "extremumIntervals": [[mp.nstr(low, precision), mp.nstr(high, precision)] for low, high in merged],
        "evaluations": evaluations,
        "intervalsExplored": explored,
        "warnings": warnings,
    }
