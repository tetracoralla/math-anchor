import pytest
import sympy as sp

from math_anchor.errors import CalculatorError
from math_anchor.safe_expression import make_symbols, parse_expression


def test_exact_arithmetic_and_registered_functions() -> None:
    value = parse_expression("sqrt(2) + 1/3")
    assert value == sp.sqrt(2) + sp.Rational(1, 3)


@pytest.mark.parametrize(
    "source",
    ["9007199254740993.0", "1.0000000000000001"],
)
def test_decimal_literals_preserve_the_lexical_value(source: str) -> None:
    assert sp.sstr(parse_expression(source)) == source


def test_explicit_symbols_and_values() -> None:
    symbols = make_symbols(["x"])
    assert parse_expression("x^2 + 1", symbols=symbols) == symbols["x"] ** 2 + 1
    assert parse_expression("hours * 72", values={"hours": "19/2"}) == 684


@pytest.mark.parametrize(
    "source",
    [
        "__import__('os').system('id')",
        "(1).__class__",
        "[x for x in [1]]",
        "lambda: 1",
        "open('/tmp/nope')",
        "globals()",
        "x[0]",
    ],
)
def test_blocks_code_and_unregistered_syntax(source: str) -> None:
    with pytest.raises(CalculatorError) as caught:
        parse_expression(source, symbols=make_symbols(["x"]))
    assert caught.value.code in {"E_AST_BLOCK", "E_NAME", "E_SYNTAX"}


def test_limits_exponents_and_factorials() -> None:
    with pytest.raises(CalculatorError, match="exponent"):
        parse_expression("2^10001")
    with pytest.raises(CalculatorError, match="factorial"):
        parse_expression("factorial(5001)")


def test_allows_bounded_complex_exponents() -> None:
    assert parse_expression("2^i") == sp.Pow(2, sp.I)
    with pytest.raises(CalculatorError, match="exponent"):
        parse_expression("2^(10001*i)")


def test_special_functions_are_registered_and_accurate() -> None:
    import mpmath as mp

    from math_anchor.runtime import execute_direct

    exact = execute_direct("expression.evaluate", {"expression": "atan2(1, 1)", "precision": 30})
    assert exact["exact"] == "pi/4"
    zeta_two = execute_direct("expression.evaluate", {"expression": "zeta(2)", "precision": 30})
    assert zeta_two["exact"] == "pi**2/6"
    lambert = execute_direct("expression.evaluate", {"expression": "lambertw(e)", "precision": 30})
    assert lambert["exact"] == "1"
    log_ten = execute_direct("expression.evaluate", {"expression": "log10(100)", "precision": 30})
    assert log_ten["exact"] == "2"

    for expression, truth in {
        "erf(1)": lambda: mp.erf(1),
        "besselj(0, 1)": lambda: mp.besselj(0, 1),
        "zeta(3)": lambda: mp.zeta(3),
        "log2(8)": lambda: mp.mpf(3),
    }.items():
        result = execute_direct("expression.evaluate", {"expression": expression, "precision": 45})
        with mp.workdps(50):
            # mpf(string) rounds to the current working precision, so the
            # comparison must run at guard precision.
            assert abs(mp.mpf(result["approx"]) - truth()) < mp.mpf("1e-42"), (expression, result["approx"])

    with pytest.raises(CalculatorError) as reserved:
        from math_anchor.safe_expression import make_symbols

        make_symbols(["erf"])
    assert reserved.value.code == "E_INPUT"
