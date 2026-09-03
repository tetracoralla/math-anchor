"""Differential accuracy suite for the Math Anchor calculation core.

Every registered operation is executed against independent oracles:

* exact results must agree with high-precision (>= 50 dps) recomputation;
* the approximate field must be digit-correct at the *reported* precision;
* the reported precision must follow the current float-atom clamping
  semantics of ``src/math_anchor/formatting.py`` exactly as implemented today.

This suite locks CORRECTED expectations (P2): findings F-1, F-6, F-8, and
F-9 were fixed in the product and their locks were flipped from as-current
reproductions to the corrected contracts below. The three owner-decision
semantics items (9.81 exact-rational vs binary64 lane, exp(100000) vs
e^100000, the decimal dps-15 policy) are deliberately not locked here.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from fractions import Fraction
import math
import random
from typing import Any, Callable

import pytest
import sympy as sp
from mpmath.libmp import prec_to_dps

from math_anchor.catalog import OPERATIONS
from math_anchor.currency import ECBRateService, RateSnapshot
from math_anchor.errors import CalculatorError
from math_anchor.runtime import execute_direct
from math_anchor.safe_expression import normalize_expression_source, parse_expression


# --------------------------------------------------------------------------
# Generic contract and differential helpers
# --------------------------------------------------------------------------


def _as_decimal(text: str) -> Decimal:
    return Decimal(text)


def _numeric(text: str) -> sp.Expr | None:
    """Parse an exact-result string and return it, or None when non-numeric."""
    try:
        value = sp.sympify(text, locals=_SYMPY_LOCALS)
    except (sp.SympifyError, SyntaxError, TypeError, ValueError):
        return None
    return value if value.is_number else None


_SYMPY_LOCALS: dict[str, Any] = {
    "e": sp.E,
    "E": sp.E,
    "i": sp.I,
    "I": sp.I,
    "inf": sp.oo,
    "ln": sp.log,
}


def _assert_agrees(label: str, approx_text: str | None, expected: sp.Expr, precision: int) -> None:
    """The approximate value must be digit-correct at the reported precision."""
    assert approx_text is not None, f"{label}: approx is missing"
    want = sp.N(expected, max(precision + 20, 30))
    if want in (sp.oo, -sp.oo, sp.zoo, sp.nan):
        assert approx_text.replace("+", "") in {"oo", "-oo", "inf", "-inf", "zoo", "nan"}, (
            f"{label}: approx {approx_text} for non-finite {want}"
        )
        return
    got = _as_decimal(approx_text)
    want_dec = _as_decimal(sp.sstr(want))
    if want_dec == 0:
        assert got == 0, f"{label}: approx {got} != 0"
        return
    relative_error = abs(got - want_dec) / abs(want_dec)
    tolerance = Decimal(5).scaleb(-(precision - 1))
    assert relative_error <= tolerance, (
        f"{label}: approx {approx_text} deviates from {sp.sstr(want)} "
        f"by {relative_error} at precision {precision}"
    )


def _collect_pairs(node: Any) -> list[tuple[str, dict[str, Any]]]:
    """Yield every (label, dict) that carries an exact/approx/precision triple."""
    found: list[tuple[str, dict[str, Any]]] = []
    if isinstance(node, dict):
        if "precision" in node and ("exact" in node or "approx" in node):
            found.append((str(node.get("operation", "value")), node))
        for child in node.values():
            found.extend(_collect_pairs(child))
    elif isinstance(node, list):
        for child in node:
            found.extend(_collect_pairs(child))
    return found


def _pair_leaf(label: str, exact: str | None, approx: str | None, precision: int) -> None:
    if approx is not None:
        assert isinstance(approx, str), f"{label}: approx leaf must be text"
    if exact is None or approx is None:
        return
    assert isinstance(exact, str), f"{label}: exact leaf must be text"
    exact_value = _numeric(exact)
    if exact_value is None:
        return
    _assert_agrees(label, approx, exact_value, precision)


def _walk_pair(label: str, exact: Any, approx: Any, precision: int) -> None:
    """Compare an exact/approx pair, tolerating nested matrices of strings."""
    if isinstance(approx, list) or isinstance(exact, list):
        assert isinstance(approx, list) and isinstance(exact, list), (
            f"{label}: exact/approx shapes disagree: {exact!r} vs {approx!r}"
        )
        assert len(exact) == len(approx), f"{label}: exact/approx lengths disagree"
        for index, (exact_item, approx_item) in enumerate(zip(exact, approx)):
            _walk_pair(f"{label}[{index}]", exact_item, approx_item, precision)
        return
    if isinstance(approx, dict) or isinstance(exact, dict):
        assert isinstance(approx, dict) and isinstance(exact, dict), (
            f"{label}: exact/approx shapes disagree"
        )
        for key, approx_item in approx.items():
            _walk_pair(f"{label}.{key}", exact.get(key), approx_item, precision)
        return
    if approx is not None and not isinstance(approx, str):
        approx = str(approx)
    _pair_leaf(label, exact if exact is None or isinstance(exact, str) else str(exact), approx, precision)


def _verify_generic(label: str, result: dict[str, Any], requested: int | None) -> None:
    """Contract checks that hold for every successful result, any operation."""
    assert result.get("status") in {"ok", "uncertain"}, f"{label}: status {result.get('status')}"
    for where, entry in _collect_pairs(result):
        precision = entry["precision"]
        assert isinstance(precision, int) and precision >= 2, (
            f"{label}/{where}: precision {precision}"
        )
        if requested is not None:
            assert precision <= requested, f"{label}/{where}: precision {precision} > requested {requested}"
        _walk_pair(f"{label}/{where}", entry.get("exact"), entry.get("approx"), precision)


def _expected_clamped_precision(expression: str, variables: dict[str, Any] | None, requested: int) -> int:
    """Mirror formatting.effective_precision over the parsed expression."""
    expr = parse_expression(normalize_expression_source(expression), values=variables)
    float_atoms = [atom for atom in expr.atoms(sp.Float)]
    if not float_atoms:
        return requested
    available = min(prec_to_dps(atom._prec) for atom in float_atoms)
    return max(2, min(requested, available))


# --------------------------------------------------------------------------
# Corpus
# --------------------------------------------------------------------------

Oracle = Callable[[dict[str, Any]], None]


def _ev(expression: str, precision: int = 16, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    arguments: dict[str, Any] = {"expression": expression, "precision": precision}
    if variables is not None:
        arguments["variables"] = variables
    return arguments


def _oracle_expression(expression: str, precision: int, variables: dict[str, Any] | None = None) -> Oracle:
    def check(result: dict[str, Any]) -> None:
        normalized = normalize_expression_source(expression)
        # Provenance mirror: the translated value decides exactness and clamping
        # (this mirrors formatting.py over the same parse the product performs).
        parsed_value = parse_expression(normalized, values=variables)
        reported = result["precision"]
        assert reported == _expected_clamped_precision(expression, variables, precision)
        if parsed_value.atoms(sp.Float):
            assert result["exact"] is None, (
                f"a Float-valued result must never be labeled exact (got {result['exact']!r})"
            )
        else:
            assert result["exact"] is not None, "an exact value disappeared"

        # Independent numeric truth from plain SymPy.
        expected = sp.sympify(normalized, locals=_SYMPY_LOCALS)
        for name, value in (variables or {}).items():
            substitution = sp.Float(str(value)) if isinstance(value, float) else sp.sympify(value)
            expected = expected.subs(sp.Symbol(name), substitution)

        if expected.is_finite:
            anchor = result["exact"] if result["exact"] is not None else result["approx"]
            anchor_value = sp.N(sp.sympify(anchor, locals=_SYMPY_LOCALS), 50)
            oracle_high = sp.N(expected, 50)
            assert abs(anchor_value - oracle_high) <= abs(oracle_high) * sp.Float("1e-45"), (
                f"{expression}: value {anchor} != oracle {oracle_high}"
            )
            if result["approx"] is not None:
                _assert_agrees(expression, result["approx"], expected, reported)
        else:
            assert sp.sympify(result["exact"], locals=_SYMPY_LOCALS) == expected


def _loan_payment_oracle() -> Oracle:
    def check(result: dict[str, Any]) -> None:
        with localcontext() as context:
            context.prec = 60
            rate = Decimal("0.045") / 12
            periods = 360
            payment = Decimal(300000) * rate / (1 - (1 + rate) ** -periods)
        for estimate in result["results"]:
            if estimate["name"] != "payment":
                continue
            places = int(estimate.get("decimalPlaces", 2))
            actual = Decimal(_estimate_text(estimate))
            assert abs(actual - payment) <= Decimal("0.5").scaleb(-places) * Decimal("1.000000001"), (
                f"loan payment {actual} != oracle {payment}"
            )
    return check


_CASES: list[tuple[str, str, dict[str, Any], Oracle | None]] = []


def _case(operation: str, arguments: dict[str, Any], oracle: Oracle | None = None) -> None:
    _CASES.append((f"{operation}[{len(_CASES)}]", operation, arguments, oracle))


def _build_corpus() -> None:
    # 1. Every catalog example, for all 29 registered operations.
    for operation, spec in OPERATIONS.items():
        for example in spec.examples:
            _case(operation, dict(example))

    # 2. Crafted cases with independent oracles.
    for expression, precision in [
        ("2+3*4", 16), ("1/3", 50), ("(2^10)^2", 16), ("sqrt(2)*sqrt(2)", 30),
        ("-(3-5)", 16), ("10 % 3", 16), ("abs(-7)", 16), ("exp(1)", 40),
        ("ln(e^3)", 30), ("floor(3.7)", 16), ("ceil(-3.2)", 16), ("gamma(10)", 16),
        ("2^-2", 16), ("1e300 * 1e10", 16), ("max(3, 7, 5)", 16), ("min(4, -2)", 16),
        ("factorial(20)", 16), ("sin(0)", 30), ("cos(pi)", 30), ("atan(inf)", 30),
        ("1000000007 * 1000000009", 16), ("2^200 + 2^-200", 50),
    ]:
        _case("expression.evaluate", _ev(expression, precision), _oracle_expression(expression, precision))

    _case("expression.evaluate", _ev("power * hours * days", 50, {"power": 72, "hours": 9.5, "days": 30}),
          _oracle_expression("power * hours * days", 50, {"power": 72, "hours": 9.5, "days": 30}))

    for expression, variables in [
        ("(x^3 - 8)/(x - 2)", ["x"]),
        ("x^2 + 2*x + 1", ["x"]),
        ("sin(x)^2 + cos(x)^2", ["x"]),
    ]:
        _case("expression.simplify", {"expression": expression, "variables": variables})

    def _check_transformation(expected: sp.Expr) -> Oracle:
        def check(result: dict[str, Any]) -> None:
            actual = sp.sympify(result["exact"], locals=_SYMPY_LOCALS)
            _assert_agrees(
                "transform-numeric",
                sp.sstr(sp.N(actual.subs(sp.Symbol("x"), 7), 30)),
                expected.subs(sp.Symbol("x"), 7),
                30,
            )
        return check

    _case("algebra.transform", {"action": "factor", "expression": "x^2 - 9", "variables": ["x"]},
          _check_transformation((sp.Symbol("x") - 3) * (sp.Symbol("x") + 3)))
    _case("algebra.transform", {"action": "apart", "expression": "1/(x*(x+2))", "variable": "x"})

    def _residual_oracle(equations: list[str], tolerance: str = "1e-35") -> Oracle:
        def check(result: dict[str, Any]) -> None:
            for solution in result["solutions"]:
                substitutions = {
                    sp.Symbol(name): _numeric(_unwrap(value))
                    for name, value in solution.items()
                }
                for equation in equations:
                    lhs, _, rhs = equation.partition("=")
                    residual = sp.sympify(lhs, locals=_SYMPY_LOCALS) - sp.sympify(rhs or "0", locals=_SYMPY_LOCALS)
                    residual = residual.subs(substitutions)
                    assert abs(sp.N(residual, 50)) < sp.Float(tolerance), (
                        f"solution {solution} leaves residual {residual}"
                    )
        return check

    _case("algebra.solve", {"equations": "2*x + 3 = 11", "variables": ["x"], "precision": 30},
          _residual_oracle(["2*x + 3 = 11"]))
    _case("algebra.solve", {"equations": "x^2 - 5*x + 6 = 0", "variables": ["x"], "precision": 30},
          _residual_oracle(["x^2 - 5*x + 6 = 0"]))
    _case("algebra.solve", {"equations": ["x + y = 7", "x - y = 1"], "variables": ["x", "y"], "precision": 30},
          _residual_oracle(["x + y = 7", "x - y = 1"]))
    _case("algebra.solve", {"equations": "x^3 - 2*x - 5 = 0", "variables": ["x"], "domain": "real", "precision": 50},
          _residual_oracle(["x^3 - 2*x - 5 = 0"], "1e-40"))

    _case("solution.verify", {"constraints": ["x + y = 7", "x > y"], "variables": ["x", "y"],
                              "candidates": [{"x": 4, "y": 3}]},
          lambda result: (_ for _ in ()).throw(AssertionError("valid candidates rejected")) if not result["allValid"] else None)
    _case("solution.verify", {"constraints": "x^2 = 2", "variables": ["x"],
                              "candidates": [{"x": 1}]},
          lambda result: (_ for _ in ()).throw(AssertionError("invalid candidate accepted")) if result["allValid"] else None)

    def _symbolic_oracle(expression: str, expected: sp.Expr, variable: str = "x") -> Oracle:
        def check(result: dict[str, Any]) -> None:
            actual = sp.sympify(result["exact"], locals=_SYMPY_LOCALS).removeO()
            symbol = sp.Symbol(variable)
            for point in (sp.Rational(7, 13), sp.Rational(-3, 11)):
                difference = actual.subs(symbol, point) - expected.removeO().subs(symbol, point)
                assert abs(sp.N(difference, 40)) < sp.Float("1e-30"), (
                    f"{expression}: {result['exact']} != oracle {expected}"
                )
        return check

    _case("calculus.derivative", {"expression": "x^3", "variable": "x"}, _symbolic_oracle("x^3", 3 * sp.Symbol("x") ** 2))
    _case("calculus.derivative", {"expression": "1/x", "variable": "x"}, _symbolic_oracle("1/x", -1 / sp.Symbol("x") ** 2))
    _case("calculus.integrate", {"expression": "x^2", "variable": "x"}, _symbolic_oracle("x^2", sp.Symbol("x") ** 3 / 3))
    _case("calculus.integrate", {"expression": "sin(x)", "variable": "x"}, _symbolic_oracle("sin(x)", -sp.cos(sp.Symbol("x"))))
    _case("calculus.integrate", {"expression": "x^2", "lower": 0, "upper": 1, "variable": "x"},
          _oracle_expression("1/3", 16))
    _case("calculus.limit", {"expression": "sin(x)/x", "point": "0", "variable": "x"},
          lambda result: _assert_agrees("limit", result["approx"], sp.Integer(1), result["precision"]))
    _case("calculus.series", {"expression": "exp(x)", "order": 6, "point": 0, "variable": "x"},
          _symbolic_oracle("exp(x)", sp.exp(sp.Symbol("x")).series(sp.Symbol("x"), 0, 6).removeO()))

    _case("calculus.multivariate", {"action": "gradient", "expression": "x*y", "variables": ["x", "y"]})

    def _known_root(expected: sp.Expr) -> Oracle:
        return lambda result: _assert_agrees("root", result["approx"], expected, result["precision"])

    _case("numeric.root", {"expression": "x^2 - 2", "bracket": ["1", "2"], "variable": "x", "precision": 30, "tolerance": "1e-30"},
          _known_root(sp.sqrt(2)))
    _case("numeric.root", {"expression": "cos(x) - x", "bracket": ["0", "1"], "variable": "x", "precision": 30, "tolerance": "1e-30"},
          _known_root(sp.nsolve(sp.cos(sp.Symbol("x")) - sp.Symbol("x"), 0.7, prec=50)))
    _case("numeric.integrate", {"expression": "sin(x)", "lower": "0", "upper": "3.14159265358979323846", "variable": "x", "precision": 30},
          lambda result: _assert_agrees("integral", result["approx"],
                                        1 - sp.cos(sp.Float("3.14159265358979323846", 40)), 12))
    _case("numeric.integrate", {"expression": "x^2", "lower": "0", "upper": "1", "variable": "x", "precision": 30},
          lambda result: _assert_agrees("integral", result["approx"], sp.Rational(1, 3), 12))

    def _is_prime(candidate: int) -> bool:
        if candidate < 2:
            return False
        if candidate % 2 == 0:
            return candidate == 2
        divisor = 3
        while divisor * divisor <= candidate:
            if candidate % divisor == 0:
                return False
            divisor += 2
        return True

    def _factorization_oracle(value: int) -> Oracle:
        def check(result: dict[str, Any]) -> None:
            product = 1
            for factor in result["factors"]:
                prime, exponent = int(factor["prime"]), int(factor["exponent"])
                assert _is_prime(prime), f"{prime} is reported prime but is composite"
                product *= prime ** exponent
            assert product == abs(value), (
                f"factors multiply to {product}, expected {abs(value)}"
            )
            assert result["isPrime"] == _is_prime(abs(value))
        return check

    for value in [360, 97, 2**53 - 1, 999_983]:
        _case("integer.factorization", {"value": value}, _factorization_oracle(value))
    _case("integer.factorization", {"value": "9007199254740991"}, _factorization_oracle(9007199254740991))
    _case("integer.factorization", {"value": "1000036000099"}, _factorization_oracle(1000003 * 1000033))

    def _gcd_lcm_oracle(values: list[int]) -> Oracle:
        def check(result: dict[str, Any]) -> None:
            assert int(result["gcd"]) == math.gcd(*values)
            expected_lcm = 1
            for value in values:
                expected_lcm = expected_lcm * value // math.gcd(expected_lcm, value)
            assert int(result["lcm"]) == expected_lcm
        return check

    _case("integer.gcd_lcm", {"values": [12, 18, 30]}, _gcd_lcm_oracle([12, 18, 30]))
    _case("integer.gcd_lcm", {"values": [17, 5]}, _gcd_lcm_oracle([17, 5]))
    _case("integer.gcd_lcm", {"values": [1024, 64]}, _gcd_lcm_oracle([1024, 64]))
    _case("integer.modular", {"action": "power", "value": 7, "exponent": 128, "modulus": 13},
          lambda result: _assert_agrees("modpow", result["approx"], sp.Integer(pow(7, 128, 13)), result["precision"]))
    _case("integer.modular", {"action": "power", "value": 2, "exponent": 1_000_000, "modulus": 10**9 + 7},
          lambda result: _assert_agrees("modpow", result["approx"], sp.Integer(pow(2, 1_000_000, 10**9 + 7)), result["precision"]))
    _case("integer.modular", {"action": "inverse", "value": 3, "modulus": 11},
          lambda result: _assert_agrees("inverse", result["approx"], sp.Integer(4), result["precision"]))

    _case("combinatorics.count", {"action": "binomial", "n": 52, "k": 5},
          lambda result: _assert_agrees("binomial", result["approx"], sp.Integer(math.comb(52, 5)), result["precision"]))
    _case("combinatorics.count", {"action": "binomial", "n": 10, "k": 0},
          lambda result: _assert_agrees("binomial", result["approx"], sp.Integer(1), result["precision"]))
    _case("combinatorics.count", {"action": "multinomial", "counts": [2, 3, 1]},
          lambda result: _assert_agrees("multinomial", result["approx"], sp.Integer(60), result["precision"]))
    _case("combinatorics.count", {"action": "multinomial", "counts": [1, 1, 1]},
          lambda result: _assert_agrees("multinomial", result["approx"], sp.Integer(6), result["precision"]))
    _case("combinatorics.count", {"action": "binomial", "n": 1000, "k": 500},
          lambda result: _assert_agrees("binomial", result["approx"], sp.Integer(math.comb(1000, 500)), result["precision"]))

    _case("matrix.determinant", {"matrix": [[1, 2], [3, 4]]},
          lambda result: _assert_agrees("det", result["approx"], sp.Integer(-2), result["precision"]))
    _case("matrix.determinant", {"matrix": [[5]]},
          lambda result: _assert_agrees("det", result["approx"], sp.Integer(5), result["precision"]))
    _case("matrix.determinant", {"matrix": [[2, -3, 1], [2, 0, -1], [1, 4, 5]]},
          lambda result: _assert_agrees("det", result["approx"], sp.Matrix([[2, -3, 1], [2, 0, -1], [1, 4, 5]]).det(), result["precision"]))
    _case("matrix.inverse", {"matrix": [[2, 0], [0, 4]]},
          lambda result: _assert_agrees("inverse", result["approx"][0][0], sp.Rational(1, 2), result["precision"]))
    _case("matrix.eigenvalues", {"matrix": [[0, 1], [1, 0]]},
          lambda result: all(
              _assert_agrees("eigen", entry["approx"], expected, result["precision"])
              for entry, expected in zip(sorted(result["values"], key=lambda e: Decimal(e["approx"])), [sp.Integer(-1), sp.Integer(1)])
          ))
    _case("matrix.solve", {"matrix": [[1, 1], [1, -1]], "constants": [7, 1], "variables": ["x", "y"]},
          lambda result: _assert_agrees("solve", result["particular"][0]["approx"], sp.Integer(4), result["precision"]))
    _case("matrix.solve", {"matrix": [[1, 2], [2, 4]], "constants": [3, 6]},
          lambda result: (_ for _ in ()).throw(AssertionError("singular consistent system must not be unique")) if result["classification"] == "unique" else None)
    _case("matrix.solve_approximate", {"matrix": [["3", "1"], ["1", "2"]], "constants": ["9", "8"], "tolerance": "1e-12"},
          lambda result: _assert_agrees("approx-solve", _unwrap(result["solution"][0]), sp.Integer(2), 12))
    _case("matrix.reduce", {"action": "rref", "matrix": [[1, 2, 3], [2, 4, 6]]},
          lambda result: _assert_agrees("rref", result["approx"][0][2], sp.Integer(3), result["precision"]))
    _case("matrix.reduce", {"action": "rank", "matrix": [[1, 2], [2, 4]]},
          lambda result: (_ for _ in ()).throw(AssertionError("rank")) if result["rank"] != 1 else None)

    def _describe_oracle(values: list[Fraction], ddof: int) -> Oracle:
        def check(result: dict[str, Any]) -> None:
            count = len(values)
            mean = sum(values) / count
            assert _numeric(result["mean"]["exact"]) == sp.Rational(mean.numerator, mean.denominator)
            assert _numeric(result["minimum"]["exact"]) == sp.Integer(min(values).numerator)
            assert _numeric(result["maximum"]["exact"]) == sp.Integer(max(values).numerator)
            variance = sum((value - mean) ** 2 for value in values) / (count - ddof)
            _assert_agrees("stddev", result["standardDeviation"]["approx"],
                           sp.sqrt(sp.Rational(variance.numerator, variance.denominator)),
                           result["precision"])
        return check

    _case("statistics.describe", {"values": [12, 15, 18, 21, 24], "ddof": 1},
          _describe_oracle([Fraction(value) for value in [12, 15, 18, 21, 24]], 1))
    _case("statistics.describe", {"values": [1, 2, 3, 10], "ddof": 1},
          _describe_oracle([Fraction(value) for value in [1, 2, 3, 10]], 1))
    _case("statistics.describe", {"values": ["2", "4", "4", "4", "5", "5", "7", "9"], "ddof": 1},
          _describe_oracle([Fraction(2), Fraction(4), Fraction(4), Fraction(4), Fraction(5), Fraction(5), Fraction(7), Fraction(9)], 1))

    def _ci_oracle(sample: list[str]) -> Oracle:
        def check(result: dict[str, Any]) -> None:
            values = [Fraction(item) for item in sample]
            count = len(values)
            mean = sum(values) / count
            variance = sum((value - mean) ** 2 for value in values) / (count - 1)
            standard_error = sp.sqrt(sp.Rational(variance.numerator, variance.denominator)) / sp.sqrt(count)
            critical = sp.Float("2.7764451051977987335")  # t(0.975, df=4)
            for estimate in result["estimates"]:
                if estimate.get("name") == "mean":
                    _assert_agrees("ci-mean", _unwrap(estimate.get("value")), sp.Rational(mean.numerator, mean.denominator), 12)
            interval = result["interval"]
            upper = sp.sympify(_unwrap(interval["upper"]), locals=_SYMPY_LOCALS)
            lower = sp.sympify(_unwrap(interval["lower"]), locals=_SYMPY_LOCALS)
            margin = abs(sp.N(upper - lower, 30)) / 2
            expected_margin = sp.N(critical * standard_error, 30)
            assert abs(margin - expected_margin) <= abs(expected_margin) * sp.Float("1e-12"), (
                f"CI margin {margin} != {expected_margin}"
            )
        return check

    _case("statistics.infer", {"action": "mean_confidence_interval", "sample": ["10", "12", "9", "11", "13"], "confidenceLevel": "0.95"},
          _ci_oracle(["10", "12", "9", "11", "13"]))
    _case("statistics.infer", {"action": "one_sample_t_test", "sample": ["10", "12", "9", "11", "13"], "nullMean": "10"},
          lambda result: _assert_agrees("t-stat", _t_statistic(result), sp.sqrt(2), 12))

    def _regression_oracle() -> Oracle:
        def check(result: dict[str, Any]) -> None:
            xs = [Fraction(1), Fraction(2), Fraction(3)]
            ys = [Fraction(2), Fraction(41, 10), Fraction(59, 10)]
            count = len(xs)
            mean_x = sum(xs) / count
            mean_y = sum(ys) / count
            slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / sum((x - mean_x) ** 2 for x in xs)
            intercept = mean_y - slope * mean_x
            for estimate in result["estimates"]:
                if estimate.get("name") == "slope":
                    _assert_agrees("slope", _unwrap(estimate.get("value")), sp.Rational(slope.numerator, slope.denominator), 12)
                if estimate.get("name") == "intercept":
                    _assert_agrees("intercept", _unwrap(estimate.get("value")), sp.Rational(intercept.numerator, intercept.denominator), 12)
        return check

    _case("statistics.infer", {"action": "linear_regression", "x": ["1", "2", "3"], "y": ["2", "4.1", "5.9"]},
          _regression_oracle())

    def _normal_cdf_oracle(x: str) -> Oracle:
        return lambda result: _assert_agrees("normal-cdf", _distribution_value(result),
                                             (1 + sp.erf(sp.Float(x, 40) / sp.sqrt(2))) / 2, 12)

    _case("probability.distribution", {"distribution": "normal", "function": "cdf", "x": "1.96"}, _normal_cdf_oracle("1.96"))
    _case("probability.distribution", {"distribution": "normal", "function": "pdf", "x": "0"},
          lambda result: _assert_agrees("normal-pdf", _distribution_value(result), 1 / sp.sqrt(2 * sp.pi), 12))

    def _binomial_oracle(n: int, k: int, p: str, function: str) -> Oracle:
        def check(result: dict[str, Any]) -> None:
            with localcontext() as context:
                context.prec = 60
                probability = Decimal(p)
                if function == "pmf":
                    expected = Decimal(math.comb(n, k)) * probability ** k * (1 - probability) ** (n - k)
                else:
                    expected = sum(
                        Decimal(math.comb(n, i)) * probability ** i * (1 - probability) ** (n - i)
                        for i in range(k + 1)
                    )
            _assert_agrees("binomial", _distribution_value(result), sp.Float(str(expected), 50), 12)
        return check

    _case("probability.distribution", {"distribution": "binomial", "function": "pmf", "n": 20, "k": 4, "probability": "0.1"},
          _binomial_oracle(20, 4, "0.1", "pmf"))
    _case("probability.distribution", {"distribution": "binomial", "function": "cdf", "n": 20, "k": 4, "probability": "0.1"},
          _binomial_oracle(20, 4, "0.1", "cdf"))
    _case("probability.distribution", {"distribution": "poisson", "function": "pmf", "k": 3, "rate": "2.5"},
          lambda result: _assert_agrees("poisson", _distribution_value(result),
                                        sp.exp(sp.Float(-2.5, 40)) * sp.Float(2.5, 40) ** 3 / sp.factorial(3), 12))

    def _units_oracle(expected: Fraction | str) -> Oracle:
        def check(result: dict[str, Any]) -> None:
            if isinstance(expected, str):
                assert result["approx"] is not None
                _assert_agrees("units", result["approx"], sp.Float(expected, 40), 12)
            else:
                assert _numeric(result["exact"]) == sp.Rational(expected.numerator, expected.denominator)
        return check

    _case("units.convert", {"value": 72, "fromUnit": "watt", "toUnit": "kilowatt"}, _units_oracle(Fraction(9, 125)))
    _case("units.convert", {"value": 1, "fromUnit": "mile", "toUnit": "meter"}, _units_oracle(Fraction(1609344, 1000)))
    _case("units.convert", {"value": 100, "fromUnit": "degC", "toUnit": "degF"}, _units_oracle(Fraction(212)))
    _case("units.convert", {"value": 0, "fromUnit": "kelvin", "toUnit": "degC"}, _units_oracle("-273.15"))
    _case("units.convert", {"value": 1, "fromUnit": "hour", "toUnit": "second"}, _units_oracle(Fraction(3600)))
    _case("units.convert", {"value": 2.5, "fromUnit": "kilogram", "toUnit": "gram"},
          lambda result: (_ for _ in ()).throw(AssertionError("float input labeled exact")) if result["exact"] is not None else _assert_agrees("units", result["approx"], sp.Integer(2500), result["precision"]))

    def _quantity_oracle(numerator: int, denominator: int) -> Oracle:
        def check(result: dict[str, Any]) -> None:
            assert result["unit"], "quantity result must carry a unit"
            assert _numeric(result["exact"]) == sp.Rational(numerator, denominator), (
                f"exact {result['exact']!r} != {numerator}/{denominator}"
            )
        return check

    _case("quantity.evaluate", {"expression": "3 * meter + 25 * centimeter", "toUnit": "meter"}, _quantity_oracle(13, 4))
    _case("quantity.evaluate", {"expression": "80 * kg * 9.81 * m / s^2", "toUnit": "newton"}, _quantity_oracle(3924, 5))
    _case("quantity.evaluate", {"expression": "1 * kilometer / hour", "toUnit": "meter / second"}, _quantity_oracle(5, 18))

    def _finance_oracle(expected_for: dict[str, Decimal]) -> Oracle:
        """Independent Decimal oracle, honoring each estimate's rounding scale."""
        def check(result: dict[str, Any]) -> None:
            for estimate in result["results"]:
                expected = expected_for.get(estimate["name"])
                if expected is None:
                    continue
                places = int(estimate.get("decimalPlaces", 12))
                # Values are rounded half-even to this many DECIMAL PLACES, so the
                # honest contract is a half-ulp absolute tolerance, not relative.
                tolerance = Decimal("0.5").scaleb(-places) * Decimal("1.000000001")
                actual = Decimal(_estimate_text(estimate))
                assert abs(actual - expected) <= tolerance, (
                    f"{estimate['name']}: {actual} != oracle {expected} (places={places})"
                )
        return check

    def _compound_value() -> tuple[dict[str, Any], dict[str, Decimal]]:
        arguments = {"action": "compound_value", "principal": "10000", "annualRate": "0.05",
                     "periodsPerYear": 12, "numberOfPeriods": 120}
        with localcontext() as context:
            context.prec = 60
            periodic = Decimal("0.05") / 12
            expected = {"future_value": Decimal(10000) * (1 + periodic) ** 120,
                        "periodic_rate": periodic}
        return arguments, expected

    compound_arguments, compound_expected = _compound_value()
    _case("finance.calculate", compound_arguments, _finance_oracle(compound_expected))
    with localcontext() as context:
        context.prec = 60
        effective = (1 + Decimal("0.12") / 12) ** 12 - 1
    _case("finance.calculate", {"action": "effective_annual_rate", "nominalAnnualRate": "0.12", "compoundsPerYear": 12},
          _finance_oracle({"effective_annual_rate": effective}))
    _case("finance.calculate", {"action": "npv", "cashFlows": ["-1000", "400", "400", "400"], "ratePerPeriod": "0.1"},
          _finance_oracle({"net_present_value": sum(
              Decimal(flow) / Decimal("1.1") ** index
              for index, flow in enumerate(["-1000", "400", "400", "400"])
          )}))
    _case("finance.calculate", {"action": "irr", "cashFlows": ["-1000", "400", "400", "400"],
                                "lowerRate": "0", "upperRate": "1"},
          lambda result: _irr_residual_check(result, ["-1000", "400", "400", "400"]))

    # 3. Adversarial numerics (as-current-behavior locks; see findings report).
    _case("expression.evaluate", _ev("0.1+0.2", 50), _oracle_expression("0.1+0.2", 50))
    _case("expression.evaluate", _ev("0.1 + 0.000000000123", 50), _oracle_expression("0.1 + 0.000000000123", 50))
    _case("expression.evaluate", _ev("0.10000000000000000000 + 0.20000000000000000000", 50),
          _oracle_expression("0.10000000000000000000 + 0.20000000000000000000", 50))
    _case("expression.evaluate", _ev("1.23456789012345678901234567890", 50),
          _oracle_expression("1.23456789012345678901234567890", 50))
    big_integer = "9" * 999
    _case("expression.evaluate", _ev(f"{big_integer} + 1", 16),
          lambda result: _assert_agrees("bigint", result["approx"], sp.Integer(10**999), 16))
    _case("expression.evaluate", _ev("2^9999", 16),
          lambda result: _assert_agrees("pow", result["approx"], sp.Integer(2) ** 9999, 16))
    _case("expression.evaluate", _ev("2^10000", 16),
          lambda result: _assert_agrees("pow", result["approx"], sp.Integer(2) ** 10000, 16))
    _case("expression.evaluate", _ev("factorial(5000)", 30),
          lambda result: _assert_agrees("factorial", result["approx"], sp.factorial(5000), 16))
    _case("expression.evaluate", _ev("1/3", 50), _oracle_expression("1/3", 50))
    _case("expression.evaluate", _ev("0.5*4", 30), _oracle_expression("0.5*4", 30))
    for expression in ["2 × 3 ÷ 4 − 1", "π", "2 ^ 10", "√" if False else "sqrt(2)", "e^2", "i^2", "inf + 1"]:
        _case("expression.evaluate", _ev(expression, 20), _oracle_expression(expression, 20))

    # 3b. Breadth cases: every operation family gets more numeric coverage.
    for expression in [
        "1+1", "2*3+4", "7-2-3", "8/2/2", "9%4", "2^3^2", "sqrt(16)", "abs(3.5)",
        "exp(0)", "ln(1)", "cos(0)", "sin(pi/6)", "tan(0)", "acos(1)", "asin(1)",
        "atan(1)", "cosh(0)", "sinh(0)", "tanh(0)", "max(1,2)", "min(3,4)",
        "ceil(2.1)", "floor(2.9)", "gamma(5)", "factorial(6)", "10^-3",
    ]:
        _case("expression.evaluate", _ev(expression, 20), _oracle_expression(expression, 20))
    for value, source_unit, target_unit, precision in [
        (5, "kilometer", "meter", 16), (1500, "gram", "kilogram", 16),
        (180, "minute", "hour", 16), (48, "hour", "day", 16),
        (2500, "joule", "kilojoule", 16), (2, "liter", "milliliter", 16),
        (1, "centimeter", "inch", 16), (0, "degF", "degC", 16),
    ]:
        _case("units.convert", {"value": value, "fromUnit": source_unit, "toUnit": target_unit, "precision": precision})
    _case("matrix.determinant", {"matrix": [[1, 0, 0, 0], [0, 2, 0, 0], [0, 0, 3, 0], [0, 0, 0, 4]]},
          lambda result: _assert_agrees("det", result["approx"], sp.Integer(24), result["precision"]))
    _case("matrix.inverse", {"matrix": [[1, 2, 3], [0, 1, 4], [5, 6, 0]]})
    _case("matrix.reduce", {"action": "rref", "matrix": [[1, 3], [2, 7]]})
    _case("matrix.eigenvalues", {"matrix": [[4, 1], [2, 3]]},
          lambda result: sorted(int(sp.floor(_numeric(entry["exact"]))) for entry in result["values"]) == [2, 5] or (_ for _ in ()).throw(AssertionError("eigenvalues")))
    _case("matrix.solve", {"matrix": [[2, 0, 0], [0, 3, 0], [0, 0, 4]], "constants": [10, 9, 8]},
          lambda result: _assert_agrees("solve", result["particular"][0]["approx"], sp.Rational(5), result["precision"]))
    _case("matrix.solve_approximate", {"matrix": [["2", "0"], ["0", "4"]], "constants": ["10", "8"], "tolerance": "1e-12"})
    for sample in [[4, 8, 15, 16, 23, 42], [7, 7, 7], [-5, 5, -5, 5, -5]]:
        _case("statistics.describe", {"values": sample, "ddof": 1})
    for arguments in [
        {"distribution": "normal", "function": "cdf", "x": "0"},
        {"distribution": "normal", "function": "cdf", "x": "2"},
        {"distribution": "normal", "function": "pdf", "x": "1.5"},
        {"distribution": "binomial", "function": "pmf", "n": 10, "k": 3, "probability": "0.5"},
        {"distribution": "binomial", "function": "cdf", "n": 10, "k": 9, "probability": "0.5"},
        {"distribution": "poisson", "function": "pmf", "k": 0, "rate": "1"},
    ]:
        _case("probability.distribution", arguments)
    _case("finance.calculate", {"action": "compound_value", "principal": "1", "annualRate": "0.07", "periodsPerYear": 1, "numberOfPeriods": 1},
          _finance_oracle({"future_value": Decimal("1.07"), "periodic_rate": Decimal("0.07")}))
    _case("finance.calculate", {"action": "loan_payment", "principal": "300000", "annualRate": "0.045",
                               "paymentsPerYear": 12, "numberOfPayments": 360},
          _loan_payment_oracle())
    _case("finance.calculate", {"action": "npv", "cashFlows": ["-100", "60", "60"], "ratePerPeriod": "0.1"},
          _finance_oracle({"net_present_value": Decimal("-100") + Decimal("60") / Decimal("1.1") + Decimal("60") / Decimal("1.21")}))
    _case("combinatorics.count", {"action": "binomial", "n": 30, "k": 15},
          lambda result: _assert_agrees("binomial", result["approx"], sp.Integer(math.comb(30, 15)), result["precision"]))
    _case("combinatorics.count", {"action": "binomial", "n": 5, "k": 2},
          lambda result: _assert_agrees("binomial", result["approx"], sp.Integer(10), result["precision"]))
    _case("combinatorics.count", {"action": "multinomial", "counts": [4, 4, 2]},
          lambda result: _assert_agrees("multinomial", result["approx"],
                                        sp.factorial(10) // (sp.factorial(4) * sp.factorial(4) * sp.factorial(2)),
                                        result["precision"]))
    _case("integer.gcd_lcm", {"values": [21, 14]}, _gcd_lcm_oracle([21, 14]))
    _case("integer.gcd_lcm", {"values": [2, 3, 5, 7]}, _gcd_lcm_oracle([2, 3, 5, 7]))
    for value, modulus in [(7, 31), (10, 17)]:
        _case("integer.modular", {"action": "inverse", "value": value, "modulus": modulus},
              lambda result, value=value, modulus=modulus: _assert_agrees("inverse", result["approx"], sp.Integer(pow(value, -1, modulus)), result["precision"]))
    _case("quantity.evaluate", {"expression": "5 * kilometer / hour", "toUnit": "meter / second"})
    _case("quantity.evaluate", {"expression": "100 * centimeter", "toUnit": "meter"})
    _case(
        "geometry.almost_complex.local_check",
        {
            "coordinates": ["x", "y"],
            "structure": [["0", "-1"], ["1", "0"]],
        },
        lambda result: (
            result["square"]["satisfied"] is True
            and result["nijenhuis"]["vanished"] is True
            and result["nijenhuis"]["independentComponentsChecked"] == 2
        )
        or (_ for _ in ()).throw(AssertionError("local almost-complex oracle mismatch")),
    )
    _case("algebra.solve", {"equations": "2^x = 8", "variables": ["x"]})
    _case("algebra.solve", {"equations": ["x + y + z = 6", "x - y + z = 2", "x + y - z = 0"], "variables": ["x", "y", "z"]})
    _case("solution.verify", {"constraints": "x^3 = 27", "variables": ["x"], "candidates": [{"x": 3}]})
    _case("expression.simplify", {"expression": "exp(x) * exp(-x)", "variables": ["x"]})
    _case("expression.simplify", {"expression": "(x^2 - 1)/(x + 1)", "variables": ["x"]})
    _case("algebra.transform", {"action": "factor", "expression": "x^2 + 5*x + 6", "variables": ["x"]})
    _case("algebra.transform", {"action": "apart", "expression": "1/((x+1)*(x+2))", "variable": "x"})
    _case("calculus.derivative", {"expression": "exp(x) * cos(x)", "variable": "x"})
    _case("calculus.derivative", {"expression": "x^2 * sin(x)", "variable": "x"})
    _case("calculus.integrate", {"expression": "exp(-x)", "variable": "x"})
    _case("calculus.integrate", {"expression": "x^3", "variable": "x"})
    _case("calculus.limit", {"expression": "(1 + 1/x)^x", "point": "inf", "variable": "x"})
    _case("calculus.limit", {"expression": "x^2", "point": "3", "variable": "x"})
    _case("calculus.series", {"expression": "ln(1+x)", "order": 5, "point": 0, "variable": "x"})
    _case("numeric.root", {"expression": "x^3 - 2", "bracket": ["1", "2"], "variable": "x", "precision": 30, "tolerance": "1e-30"},
          _known_root(sp.root(2, 3)))

    def _minimize_oracle(expression: str, expected: sp.Expr) -> Oracle:
        def check(result: dict[str, Any]) -> None:
            assert result["certified"] is True, result
            low = sp.Float(result["valueEnclosure"][0], 55)
            high = sp.Float(result["valueEnclosure"][1], 55)
            expected_value = sp.N(expected, 55)
            assert low <= expected_value <= high, (result["valueEnclosure"], expected)
        return check

    _case("numeric.minimize", {"expression": "x^2 - 2", "variable": "x", "bracket": ["-2", "2"]},
          _minimize_oracle("x^2 - 2", sp.Integer(-2)))
    _case("numeric.minimize", {"expression": "sin(x)", "variable": "x", "bracket": ["0", "7"]},
          _minimize_oracle("sin(x)", sp.Integer(-1)))

    def _all_roots_oracle(expected: list[sp.Expr]) -> Oracle:
        def check(result: dict[str, Any]) -> None:
            assert result["count"] == len(expected), (result["count"], expected)
            for entry, truth in zip(result["roots"], expected):
                _assert_agrees("root", entry["approx"], truth, result["precision"])
        return check

    _case("numeric.root", {"expression": "x^4 - 5*x^2 + 4", "variable": "x", "bracket": ["-3", "3"],
                           "findAll": True, "resolution": 256, "tolerance": "1e-25", "precision": 25},
          _all_roots_oracle([sp.Integer(-2), sp.Integer(-1), sp.Integer(1), sp.Integer(2)]))

    def _sample_oracle(expression: str, variable: str, points: list[str]) -> Oracle:
        def check(result: dict[str, Any]) -> None:
            assert result["count"] == len(points)
            for row, text in zip(result["points"], points):
                assert row["x"] == text
                if row["undefined"]:
                    continue
                truth = sp.N(sp.sympify(expression, locals=_SYMPY_LOCALS).subs(sp.Symbol(variable), sp.sympify(text, locals=_SYMPY_LOCALS)), 50)
                assert abs(sp.Float(row["approx"], 50) - truth) < sp.Float("1e-30"), (row, truth)
        return check

    # Rational point texts keep exact provenance; decimal point texts take
    # the deliberate 15-digit float-atom lane and are covered elsewhere.
    _case("function.sample", {"expression": "sin(x)*exp(-x/4)", "variable": "x",
                              "points": ["-3", "-3/2", "0", "3/2", "3"], "precision": 40},
          _sample_oracle("sin(x)*exp(-x/4)", "x", ["-3", "-3/2", "0", "3/2", "3"]))


    # 4. Seeded random expressions with the independent SymPy oracle.
    generator = random.Random(20260815)
    functions = ["sqrt", "exp", "sin", "cos", "abs", "floor", "ln"]
    constants = ["pi", "e", "2", "3", "7", "10", "1/4", "2^16"]
    floats = ["0.1", "0.5", "1.25", "3.75", "0.0625", "12.5"]

    def random_expression(depth: int) -> str:
        pick = generator.random()
        if depth <= 0 or pick < 0.35:
            return generator.choice(constants + floats)
        if pick < 0.55:
            return f"({random_expression(depth - 1)} {generator.choice(['+', '-', '*', '/'])} {random_expression(depth - 1)})"
        if pick < 0.7:
            return f"-({random_expression(depth - 1)})"
        return f"{generator.choice(functions)}({random_expression(depth - 1)})"

    for index in range(80):
        expression = random_expression(3)
        precision = generator.choice([16, 30, 50])
        _case("expression.evaluate", _ev(expression, precision), _oracle_expression(expression, precision))


def _estimate_text(estimate: dict[str, Any]) -> str:
    """Financial estimates flatten the value: approx/exact sit at top level."""
    text = estimate.get("approx") or estimate.get("exact")
    assert isinstance(text, str), f"estimate {estimate.get('name')} has no value"
    return text


def _unwrap(value: Any) -> str | None:
    """Result leaves are either text or {exact, approx} objects."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("approx") or value.get("exact")
    return str(value)


def _t_statistic(result: dict[str, Any]) -> str | None:
    for estimate in result.get("estimates", []):
        if estimate.get("name") in {"t", "tStatistic", "t_statistic"}:
            return estimate.get("value")
    test = result.get("test") or {}
    for key in ("statistic", "t", "tStatistic", "t_statistic"):
        if key in test:
            return _unwrap(test[key])
    raise AssertionError(f"no t statistic found in {result}")


def _distribution_value(result: dict[str, Any]) -> str | None:
    value = result["value"]
    if isinstance(value, str):
        return value
    return value.get("approx") or value.get("exact")


def _irr_residual_check(result: dict[str, Any], cash_flows: list[str]) -> None:
    rate = None
    for estimate in result["results"]:
        if estimate.get("name") in {"irr", "internal_rate_of_return", "internalRateOfReturn", "rate"}:
            rate = _estimate_text(estimate)
    assert rate is not None, f"no irr value in {result}"
    with localcontext() as context:
        context.prec = 60
        parsed_rate = Decimal(rate)
        net_present_value = sum(
            Decimal(cash_flow) / (1 + parsed_rate) ** index
            for index, cash_flow in enumerate(cash_flows)
        )
    # The rate is reported rounded to 12 decimal places; the residual scale must
    # absorb that rounding (dNPV/dr ~ 1e3 for these flows).
    assert abs(net_present_value) < Decimal("1e-8"), (
        f"irr {rate} leaves NPV {net_present_value}"
    )


_build_corpus()


def test_algebra_solve_abs_equation_returns_domain_error() -> None:
    """Finding F-1 (fixed): a grammatical algebra.solve input that SymPy cannot
    invert (abs over the complex domain raises ValueError inside solveset)
    maps to E_DOMAIN ("cannot be solved over the requested domain") instead of
    escaping as E_RUNTIME. Reverting the algebra.py catch fails this test.
    """
    with pytest.raises(CalculatorError) as raised:
        execute_direct("algebra.solve", {"equations": "abs(x - 3) = 2", "variables": ["x"]})
    assert raised.value.code == "E_DOMAIN", (
        f"expected E_DOMAIN for an uninvertable equation, got {raised.value.code}"
    )


def test_complex_approximation_honors_requested_precision() -> None:
    """Finding F-6 (fixed): complex results print every requested digit
    (sp.sstr full_prec) instead of a shortest binary64-style repr, so the
    complex lane honors precision exactly like the real lane. Reverting the
    full_prec flag in formatting.approximate fails this test.
    """
    result = execute_direct(
        "expression.evaluate",
        {"expression": "7 / (5/(12*i))", "precision": 30},
    )
    assert result["exact"] == "84*I/5"
    assert result["precision"] == 30
    assert result["approx"] == "16.8000000000000000000000000000*I", (
        f"complex approximation lost full precision: {result['approx']!r}"
    )
    real_result = execute_direct(
        "expression.evaluate",
        {"expression": "12.5 - 12.5 + 5", "precision": 30},
    )
    assert real_result["approx"] == "5.00000000000000000000000000000"


def test_cancellation_trailing_digits_agree_with_high_precision_oracle() -> None:
    """Finding F-8 (fixed): the approximation is evaluated with guard digits
    and then rounded to the requested precision, so cancellation-heavy values
    agree with an independent 50-dps oracle at the reported precision (before
    the fix the relative error was ~1.1e-26 at precision 30). Reverting the
    guard digits in formatting.approximate fails this test.
    """
    result = execute_direct(
        "expression.evaluate", {"expression": "acos(abs(tanh(10)))", "precision": 30}
    )
    assert result["exact"] == "acos(tanh(10))"
    oracle = sp.N(sp.acos(sp.tanh(10)), 50)
    approx_value = sp.Float(result["approx"])
    relative_error = abs(approx_value - oracle) / abs(oracle)
    assert relative_error <= sp.Float("1e-29"), (
        f"approx deviates from the 50-dps oracle by {relative_error} at precision 30"
    )


def test_underflow_cancellation_reports_representable_nonzero() -> None:
    """Finding F-9 (fixed): ln(tanh(42 + pi)) at precision 30 evaluates the
    near-unit argument with guard digits, so the representable nonzero value
    (-1.2346e-39) is printed in scientific notation instead of collapsing to
    "0". Reverting the guard digits in formatting.approximate fails this test.
    """
    result = execute_direct(
        "expression.evaluate",
        {"expression": "ln(tanh(max((42 + pi), -(pi), (3.75 % 1e3))))", "precision": 30},
    )
    assert result["approx"] == "-1.23464132172937528189477969123e-39", (
        f"underflow behavior changed: approx {result['approx']!r}"
    )
    assert result["exact"] == "log(tanh(pi + 42))"


def test_corpus_size_and_operation_coverage() -> None:
    assert len(_CASES) >= 300, f"corpus has only {len(_CASES)} cases"
    covered = {operation for _, operation, _, _ in _CASES}
    assert covered == set(OPERATIONS), (
        f"missing operations: {sorted(set(OPERATIONS) - covered)}"
    )


@pytest.mark.parametrize("label,operation,arguments,oracle", _CASES, ids=[case[0] for case in _CASES])
def test_case_is_accurate(label: str, operation: str, arguments: dict[str, Any], oracle: Oracle | None) -> None:
    requested = arguments.get("precision")
    result = execute_direct(operation, arguments)
    _verify_generic(label, result, requested)
    if oracle is not None:
        oracle(result)


def test_currency_cross_rates_use_exact_decimal_arithmetic() -> None:
    far_future = datetime(2100, 1, 1, tzinfo=timezone.utc)
    snapshot = RateSnapshot(
        rate_date="2026-08-14",
        published_at=None,
        checked_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
        expires_at=far_future,
        next_refresh_attempt_at=far_future + timedelta(minutes=15),
        rates={
            "EUR": Decimal("1"),
            "USD": Decimal("1.1545"),
            "JPY": Decimal("171.82"),
        },
    )
    service = ECBRateService(clock=lambda: datetime(2026, 8, 15, tzinfo=timezone.utc))
    service._snapshot_for_conversion = lambda now, force_refresh: (snapshot, False, False, False)  # type: ignore[method-assign]
    from math_anchor.currency import currency_convert

    for value, source, target, precision in [
        ("100", "USD", "EUR", 12),
        ("1000", "EUR", "JPY", 12),
        ("5000", "JPY", "USD", 10),
    ]:
        result = currency_convert(
            {"value": value, "fromCurrency": source, "toCurrency": target, "precision": precision},
            service=service,
        )
        assert result["status"] == "ok", result
        assert result["exact"] is None, "currency must never claim exactness"
        with localcontext() as context:
            context.prec = 44
            expected = Decimal(value) / snapshot.rates[source] * snapshot.rates[target]
        _assert_agrees(
            f"{source}->{target}", result["approx"], sp.Float(str(expected), 50), precision
        )
