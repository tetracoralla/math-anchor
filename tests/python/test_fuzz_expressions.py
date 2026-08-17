"""Bounded fuzz and property suite for the safe expression evaluator.

Invariants enforced for every generated grammatical input:

* the call returns a structurally valid result, OR raises ``CalculatorError``
  whose code belongs to the known 15-code taxonomy;
* no other exception ever escapes (zero tracebacks);
* no ``E_RUNTIME`` is produced by a grammatical input -- E_RUNTIME is the
  "handler crashed" code and grammatical inputs must map to a typed code.
  The escape shapes found by the P1 fuzz run (modulo/float division by zero,
  min/max ordering over complex values, Mod over undefined operands,
  astronomical-magnitude ceil/cos) were fixed in P2 and are now pinned to
  their classified codes in the boundary corpus below; ANY E_RUNTIME shape
  fails the suite, so a new escape cannot slip in silently.

Numeric-honesty findings F-8 (cancellation trailing digits) and F-9
(catastrophic underflow to zero) were also fixed; the checker below enforces
digit consistency at the reported precision with one unit-in-the-last-place
of double-rounding slack, and no longer skips sub-precision nonzero values.
Finding F-7 (the DECIMAL EXPONENT of astronomically large values being only
as accurate as the requested precision) remains a documented checker
limitation mirroring mpmath semantics, not a pass.

No ``hypothesis`` dependency is used: ``requirements-dev.lock`` does not
contain it and stdlib ``random.Random`` with fixed seeds is fully
deterministic, which also keeps the suite reproducible in the packaged
runtime verification lane.
"""

from __future__ import annotations

from decimal import Decimal, MAX_EMAX, MIN_EMIN, localcontext
import os
import random
import re
from typing import Any

import pytest
import sympy as sp

from math_anchor.errors import CalculatorError
from math_anchor.runtime import execute_direct


KNOWN_CODES = frozenset(
    {
        "E_INPUT",
        "E_DOMAIN",
        "E_LIMIT",
        "E_PROVIDER",
        "E_RUNTIME",
        "E_AST_BLOCK",
        "E_UNIT",
        "E_SYNTAX",
        "E_CONVERGENCE",
        "E_TIMEOUT",
        "E_OPERATION",
        "E_OUTPUT_LIMIT",
        "E_NAME",
        "E_MEMORY",
        "E_CURRENCY",
    }
)

FAST_CASES = 2200
DEEP_CASES = 50_000
DEEP_FUZZ_ENV = "MATH_ANCHOR_DEEP_FUZZ"


# --------------------------------------------------------------------------
# Grammar generator (fixed-seed, whitelisted AST shapes only)
# --------------------------------------------------------------------------

_FUNCTIONS_1 = ["sqrt", "exp", "sin", "cos", "tan", "asin", "acos", "atan",
                "sinh", "cosh", "tanh", "ln", "abs", "floor", "ceil", "gamma",
                "erf", "log10", "zeta"]
_FUNCTIONS_N = ["max", "min"]
_CONSTANTS = ["pi", "e", "i", "inf", "2", "3", "5", "7", "10", "42", "1/4"]
_FLOATS = ["0.1", "0.2", "0.5", "1.25", "2.5", "3.75", "0.0625", "12.5", "0.0", "1e3"]
_BINOPS = ["+", "-", "*", "/", "%", "^"]


def generate_expression(rng: random.Random, depth: int = 4) -> str:
    """Emit a grammatical expression over the translator whitelist only."""
    pick = rng.random()
    if depth <= 0 or pick < 0.4:
        return rng.choice(_CONSTANTS + _FLOATS)
    if pick < 0.62:
        left = generate_expression(rng, depth - 1)
        right = generate_expression(rng, depth - 1)
        return f"({left} {rng.choice(_BINOPS)} {right})"
    if pick < 0.74:
        return f"-({generate_expression(rng, depth - 1)})"
    if pick < 0.9:
        function = rng.choice(_FUNCTIONS_1)
        # gamma keeps literal arguments for corpus ECONOMY only: pathological
        # shapes such as floor(gamma(exp(7))) run minutes each. In-process
        # evaluation is now bounded (E_TIMEOUT, runtime.py guard pinned in
        # test_runtime_timeout.py), so such shapes can no longer hang a run;
        # they are still excluded here because thousands of 10-second cases
        # would multiply the corpus wall time for no new invariant.
        argument = rng.choice(_CONSTANTS) if function == "gamma" else generate_expression(rng, depth - 1)
        return f"{function}({argument})"
    function = rng.choice(_FUNCTIONS_N)
    arity = rng.randint(1, 3)
    arguments = ", ".join(generate_expression(rng, depth - 1) for _ in range(arity))
    return f"{function}({arguments})"


def _evaluate(expression: str, precision: int = 16) -> dict[str, Any]:
    return execute_direct(
        "expression.evaluate", {"expression": expression, "precision": precision}
    )


_EXPONENT_PATTERN = re.compile(r"e[+-]?(\d+)")


def _exponent_magnitude(text: str) -> int:
    match = _EXPONENT_PATTERN.search(text)
    return int(match.group(1)) if match else 0


def _assert_result_contract(expression: str, result: dict[str, Any]) -> None:
    assert result.get("status") == "ok", f"{expression!r}: status {result.get('status')}"
    exact, approx = result.get("exact"), result.get("approx")
    if exact is None or approx is None:
        return
    value = sp.sympify(exact, locals={"ln": sp.log})
    # Complex results are excluded from this DECIMAL-text comparison only (the
    # checker compares plain Decimal strings; complex precision honoring is
    # locked in test_accuracy_differential.py after the F-6 fix). Symbolic
    # residues (e.g. Mod(I, pi)) have no numeric deviation to compare either.
    if not (value.is_number and value.is_finite and value.is_real is True):
        return
    digits = max(result["precision"] + 5, 30)
    # Compare as Decimal text: approx may carry astronomically large exponents
    # (e.g. 1.5e+188839377403738621, seen in the deep corpus) that SymPy's
    # parser cannot materialize, while Decimal handles them in constant space.
    try:
        expected_text = sp.sstr(sp.N(value, digits))
        expected = Decimal(expected_text)
        actual = Decimal(approx)
    except (sp.SympifyError, ArithmeticError, ValueError, TypeError):
        return
    if expected == 0:
        assert actual == 0, f"{expression!r}: approx {approx} but exact is zero"
        return
    # Finding F-7 (reproduced): for |x| beyond float64 range the DECIMAL
    # EXPONENT itself is only as accurate as the requested precision, so the
    # exponent's own trailing digits cannot be checked (e.g. cosh(cosh(42)) at
    # precision 8). Digit comparison is skipped for such magnitudes; this is a
    # documented checker limitation mirroring mpmath semantics, not a pass.
    if _exponent_magnitude(approx) > 10**5 or _exponent_magnitude(expected_text) > 10**5:
        return
    if expected == 0 and actual != 0:
        # After the F-9 fix a true zero must be reported as zero.
        assert actual == 0, f"{expression!r}: approx {approx} but exact is zero"
    with localcontext() as context:
        # Exponents like e+377678754807477311 (cosh(cosh(42))) exceed the
        # default Decimal Emax; arithmetic must stay in constant space.
        context.Emax = MAX_EMAX
        context.Emin = MIN_EMIN
        context.prec = 60
        deviation = abs(actual - expected) / abs(expected)
    # The product evaluates with guard digits and rounds once to the reported
    # precision (F-8 fix), so digits are trustworthy up to one
    # unit-in-the-last-place of double-rounding slack. Before the fix,
    # cancellation-heavy inputs deviated by ~1e-(precision-4).
    assert deviation <= Decimal(1).scaleb(-(result["precision"] - 1)), (
        f"{expression!r}: approx {approx} inconsistent with exact {exact} "
        f"at precision {result['precision']}"
    )


def assert_invariant(expression: str, precision: int = 16) -> None:
    """A grammatical input must yield a result or a KNOWN typed error, never a crash."""
    try:
        result = _evaluate(expression, precision)
    except CalculatorError as error:
        assert error.code in KNOWN_CODES, (
            f"{expression!r}: unknown error code {error.code!r}"
        )
        # E_RUNTIME is the handler-crashed code: a grammatical input must
        # never produce it after the P2 escape fixes. Strict zero-E_RUNTIME,
        # no message-shape exemptions.
        assert error.code != "E_RUNTIME", (
            f"{expression!r}: grammatical input escaped as E_RUNTIME: {error.message!r}"
        )
        return
    _assert_result_contract(expression, result)


# --------------------------------------------------------------------------
# Boundary corpus: every limit at exactly +/- 1
# --------------------------------------------------------------------------

BOUNDARY_CASES: list[tuple[str, str]] = [
    # AST node limit: 512 nodes == 255 binary operators over 256 literals.
    ("1" + "+1" * 254, "result"),          # 511 nodes
    ("1" + "+1" * 255, "result"),          # 512 nodes, exactly at the limit
    ("1" + "+1" * 256, "E_LIMIT"),         # 514 nodes
    ("1" + "+1" * 300, "E_LIMIT"),
    # Expression length limit: 4096 characters via a single float literal.
    ("0." + "1" * 4094, "result"),         # 4096 chars
    ("0." + "1" * 4095, "E_LIMIT"),        # 4097 chars
    # Integer literal digit limit: 1000 digits.
    ("9" * 999, "result"),
    ("9" * 1000, "result"),
    ("9" * 1001, "E_LIMIT"),
    ("9" * 1000 + " + 1", "result"),
    # Exponent magnitude limit: |exponent| <= 10000.
    ("2^9999", "result"),
    ("2^10000", "result"),
    ("2^10001", "E_LIMIT"),
    ("10^-10000", "result"),
    ("10^-10001", "E_LIMIT"),
    ("2^10000.5", "E_LIMIT"),              # cap covers Float exponents too
    ("2^(10^6)", "E_LIMIT"),
    # Factorial limit: 5000 for Integer arguments.
    ("factorial(4999)", "result"),
    ("factorial(5000)", "result"),
    ("factorial(5001)", "E_LIMIT"),
    # F-3 (fixed): the magnitude cap covers every numeric argument, not only
    # Integers, while the non-Integer capability itself is preserved.
    ("factorial(4999.5)", "result"),
    ("factorial(5000.5)", "result"),
    ("factorial(5001.5)", "E_LIMIT"),
    ("factorial(100000.0)", "E_LIMIT"),
    # Undefined-value domain errors.
    ("1/0", "E_DOMAIN"),
    ("0/0", "E_DOMAIN"),
    ("0^-1", "E_DOMAIN"),
    ("ln(0)", "E_DOMAIN"),
    ("log(0, 5)", "E_DOMAIN"),
    ("gamma(0)", "E_DOMAIN"),
    ("1/(0.1-0.1)", "E_DOMAIN"),
    ("sqrt(-1)", "result"),                # complex lane: I
    ("ln(-1)", "result"),                  # complex lane: I*pi
    # Unicode input forms.
    ("2 × 3 ÷ 4 − 1", "result"),
    ("π", "result"),
    ("2 ^ 10", "result"),
    ("5 − −3", "result"),
    ("100 ÷ 7 × π", "result"),
    ("−(2 × 2)", "result"),
    # Parenthesis nesting: deep nesting is a typed syntax error.
    ("(" * 200 + "1" + ")" * 200, "result"),
    ("(" * 1000 + "1" + ")" * 1000, "E_SYNTAX"),
    # F-2 (fixed): division and modulo by zero use the established
    # division-by-zero path (E_DOMAIN, same code and message as 1/0 above).
    ("1 % 0", "E_DOMAIN"),
    ("3 % -(0.0)", "E_DOMAIN"),
    ("0.0/0.0", "E_DOMAIN"),
    ("0.5/(0.0)", "E_DOMAIN"),
    ("(2 + 1.25) / (10 % 0.5)", "E_DOMAIN"),
    # F-2 (fixed): ordering over non-real values has no defined answer.
    ("max(i, 1)", "E_DOMAIN"),
    ("min(max(i*250), 1)", "E_DOMAIN"),
    # F-2 (fixed): Mod over operands that only turn undefined inside SymPy's
    # numeric machinery maps to E_DOMAIN, whichever raw exception surfaces.
    ("(3.75 % 1e3) % cos(inf / (i + 3))", "E_DOMAIN"),
    ("((2 + 3.75 % 1e3) % acos(pi))", "E_DOMAIN"),
    # F-2 (fixed): astronomical magnitudes classify as E_LIMIT.
    ("ceil(cosh(3.75^1000))", "E_LIMIT"),
    ("cos(cosh(5^1000))", "E_LIMIT"),
    # F-4 (fixed): max/min require at least one argument (E_INPUT); the old
    # behavior leaked -oo/+oo for the empty call.
    ("max()", "E_INPUT"),
    ("min()", "E_INPUT"),
    ("min(1)", "result"),
    ("max(3, 7, 5)", "result"),
    # Complex-power branch semantics (principal branch, not the real root).
    ("(-8)^(1/3)", "result"),
    # F-2 (fixed): evaluations whose numeric result is nan print as "nan"
    # instead of escaping as E_RUNTIME from a raw "Invalid NaN comparison".
    ("asin(inf) / 0.2", "result"),
]


@pytest.mark.parametrize(
    "expression,expected", BOUNDARY_CASES, ids=[case[0][:48] for case in BOUNDARY_CASES]
)
def test_limit_boundary(expression: str, expected: str) -> None:
    try:
        result = _evaluate(expression)
    except CalculatorError as error:
        assert error.code == expected, (
            f"{expression[:48]!r}: expected {expected}, got {error.code} ({error.message})"
        )
        assert error.code in KNOWN_CODES
        return
    assert expected == "result", (
        f"{expression[:48]!r}: expected {expected}, got result {result.get('exact')!r}"
    )
    _assert_result_contract(expression, result)


def test_cancellation_beyond_evalf_range_keeps_requested_precision_lane() -> None:
    """The fractional part of sinh(-(sinh(10))) is exact (no Float atoms) but
    resolving its ~4600-digit cancellation is beyond any affordable working
    precision: N at 30 digits reports 0 while N at 40 digits returns the
    un-cancelled magnitude, which would even violate Mod's [0, 1) range. The
    guard-digit lane must reconcile: when the two evaluations disagree by more
    than the guard digits could reconcile, the requested-precision lane's
    output is kept. Reverting the reconciliation in formatting.approximate
    fails this test.
    """
    result = _evaluate("sinh(-(sinh(10))) % ln(e)", 30)
    assert result["exact"] is not None, "the exact symbolic value must survive"
    assert result["approx"].startswith("-0.e+"), (
        f"unresolvable cancellation fabricated magnitude digits: {result['approx']!r}"
    )


def test_astronomical_magnitude_failure_does_not_poison_later_evaluations() -> None:
    """State-hygiene regression: an aborted astronomical evaluation used to
    leave mpmath's global context precision at an unrepresentable huge value,
    after which every later evaluation in the process failed with
    "int too large to convert to float". runtime.execute_direct now restores
    the default precision; reverting that finally block fails this test.
    """
    for expression in ("cos(cosh(5^1000))", "ceil(cosh(3.75^1000))"):
        with pytest.raises(CalculatorError) as raised:
            _evaluate(expression)
        assert raised.value.code == "E_LIMIT"
    result = _evaluate("factorial(4999.5)")
    assert result["status"] == "ok"
    assert result["approx"] is not None and "e+" in result["approx"]


# --------------------------------------------------------------------------
# Randomized corpus (fast gate + optional deep run)
# --------------------------------------------------------------------------


def _run_corpus(seed: int, count: int) -> None:
    rng = random.Random(seed)
    failures: list[str] = []
    for index in range(count):
        expression = generate_expression(rng)
        precision = rng.choice([8, 16, 30])
        try:
            assert_invariant(expression, precision)
        except Exception as error:  # fuzz harness records everything, never dies
            failures.append(
                f"case {index} precision {precision} {expression!r}: "
                f"{type(error).__name__}: {error}"
            )
            if len(failures) >= 5:
                break
    assert not failures, "fuzz failures:\n" + "\n".join(failures)


def test_fuzz_fast_corpus_is_deterministic_and_clean() -> None:
    _run_corpus(seed=20260816, count=FAST_CASES)


@pytest.mark.skipif(
    os.environ.get(DEEP_FUZZ_ENV) != "1",
    reason=f"long deep-fuzz run; opt in with {DEEP_FUZZ_ENV}=1",
)
def test_fuzz_deep_corpus_opt_in() -> None:
    _run_corpus(seed=987654321, count=DEEP_CASES)


def test_generator_is_pure_whitelist_and_deterministic() -> None:
    first = random.Random(20260816)
    second = random.Random(20260816)
    for _ in range(200):
        expression = generate_expression(first)
        assert expression == generate_expression(second)
        assert len(expression) < 500
