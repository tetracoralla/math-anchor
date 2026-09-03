import pytest

from math_anchor.catalog import (
    MAX_CATEGORY_LENGTH,
    MAX_OPERATION_ID_LENGTH,
    MAX_SEARCH_QUERY_LENGTH,
    describe_operation,
    search_operations,
)
from math_anchor.errors import CalculatorError
from math_anchor.runtime import execute_direct


def test_catalog_discovery_is_compact_and_descriptions_are_precise() -> None:
    searched = search_operations("numerically solve nonlinear equation")
    assert searched["matchStatus"] == "matched"
    assert searched["operations"][0]["id"] in {"numeric.root", "algebra.solve"}
    assert all(set(item) == {"id", "category", "summary"} for item in searched["operations"])

    described = describe_operation("calculus.integrate")
    assert described["operation"]["inputSchema"]["required"] == ["expression", "variable"]


def test_catalog_rejects_single_term_collisions_for_unsupported_domains() -> None:
    for query in (
        "cohomology characteristic class",
        "compute Dolbeault cohomology of this complex manifold",
        "compute characteristic classes of a complex manifold",
        "integrate a differential form over a complex manifold",
        "solve the PDE for a complex manifold",
        "integrate the Nijenhuis tensor",
        "计算复流形的层上同调",
        "计算复流形的 Dolbeault 上同调",
        "求解复流形上的偏微分方程",
        "积分复流形上的微分形式",
        "计算复流形的陈类",
        "验证六维球面存在可积复结构",
    ):
        unsupported = search_operations(query)
        assert unsupported["matchStatus"] == "no_registered_operation", query
        assert unsupported["operations"] == []
        assert unsupported["count"] == 0

    generic = search_operations("the")
    assert generic["matchStatus"] == "no_registered_operation"
    assert generic["operations"] == []


def test_catalog_routes_local_almost_complex_queries_without_overclaiming_global_support() -> None:
    searched = search_operations("tensor differential form manifold Nijenhuis")

    assert searched["matchStatus"] == "matched"
    assert searched["operations"][0]["id"] == "geometry.almost_complex.local_check"


def test_catalog_routes_a_registered_single_alias_when_the_complete_query_matches() -> None:
    searched = search_operations("factor expression")

    assert searched["matchStatus"] == "matched"
    assert searched["operations"][0]["id"] == "algebra.transform"


@pytest.mark.parametrize(
    ("query", "operation"),
    [
        ("expression equivalence", "expression.equivalent"),
        ("equivalent expressions", "expression.equivalent"),
        ("convert 72 watts to kilowatts", "units.convert"),
        ("solve cubic equation", "algebra.solve"),
        ("compound interest future value", "finance.calculate"),
        ("binomial coefficient 52 choose 5", "combinatorics.count"),
        ("standard deviation of data", "statistics.describe"),
        ("compute determinant of matrix", "matrix.determinant"),
    ],
)
def test_catalog_routes_supported_natural_concepts(
    query: str,
    operation: str,
) -> None:
    searched = search_operations(query)

    assert searched["matchStatus"] == "matched"
    assert searched["operations"][0]["id"] == operation


@pytest.mark.parametrize(
    "query",
    [
        "obligation",
        "receipt",
        "check polynomial obligation",
        "replay mathematical receipt",
    ],
)
def test_catalog_stops_at_provider_native_obligation_terms(query: str) -> None:
    searched = search_operations(query)

    assert searched["matchStatus"] == "no_registered_operation"
    assert searched["operations"] == []


@pytest.mark.parametrize(
    "call",
    [
        lambda: search_operations("x" * (MAX_SEARCH_QUERY_LENGTH + 1)),
        lambda: search_operations("", "x" * (MAX_CATEGORY_LENGTH + 1)),
        lambda: describe_operation("x" * (MAX_OPERATION_ID_LENGTH + 1)),
    ],
)
def test_catalog_discovery_rejects_oversized_coordinates_without_reflecting_them(
    call,
) -> None:
    with pytest.raises(CalculatorError) as caught:
        call()

    assert caught.value.code == "E_LIMIT"
    assert len(caught.value.message) < 128


@pytest.mark.parametrize(
    ("query", "operation"),
    [
        ("帮我求导", "calculus.derivative"),
        ("计算这个积分", "calculus.integrate"),
        ("做单位换算", "units.convert"),
        ("计算带单位的表达式并检测不同维度单位相加，例如 1 米 + 1 秒", "quantity.evaluate"),
        ("检查物理公式的量纲一致性", "dimension.check"),
        ("根据公式推断未知变量的量纲", "dimension.infer"),
        ("根据白金汉 Pi 定理生成无量纲组合", "dimension.pi_groups"),
        ("矩阵特征值", "matrix.eigenvalues"),
    ],
)
def test_catalog_supports_common_chinese_task_language(query: str, operation: str) -> None:
    searched = search_operations(query)
    assert searched["operations"][0]["id"] == operation


def test_expression_preserves_exact_and_approximate_results() -> None:
    result = execute_direct("expression.evaluate", {"expression": "sqrt(2)", "precision": 50})
    assert result["exact"] == "sqrt(2)"
    assert result["approx"].startswith("1.4142135623730950488")
    assert result["precision"] == 50


@pytest.mark.parametrize("expression", ["1/0", "0/0", "log(0)"])
def test_undefined_expression_is_a_domain_error(expression: str) -> None:
    with pytest.raises(CalculatorError) as caught:
        execute_direct("expression.evaluate", {"expression": expression})
    assert caught.value.code == "E_DOMAIN"


def test_syntax_error_is_a_correctable_input_failure() -> None:
    # Negative regression: malformed but safe input used to inherit the
    # execution/stop fallback, telling an Agent to abandon a request it can
    # correct locally.
    with pytest.raises(CalculatorError) as caught:
        execute_direct("expression.evaluate", {"expression": "1+"})

    assert caught.value.code == "E_SYNTAX"
    payload = caught.value.as_dict()
    assert payload["phase"] == "input"
    assert payload["suggestedAction"] == "correct_input"
    assert payload["retryable"] is False


def test_symbolic_solve_and_calculus() -> None:
    solved = execute_direct(
        "algebra.solve",
        {"equations": "x^2 = 2", "variables": ["x"], "domain": "real", "precision": 30},
    )
    assert {item["x"]["exact"] for item in solved["solutions"]} == {"-sqrt(2)", "sqrt(2)"}
    assert solved["classification"] == "finite"
    assert solved["complete"] is True

    derivative = execute_direct(
        "calculus.derivative",
        {"expression": "sin(x) * exp(x)", "variable": "x"},
    )
    assert "sin(x)" in derivative["exact"]
    assert "cos(x)" in derivative["exact"]

    integral = execute_direct(
        "calculus.integrate",
        {"expression": "sin(x)", "variable": "x", "lower": 0, "upper": "pi"},
    )
    assert integral["exact"] == "2"


def test_numeric_matrix_statistics_and_units() -> None:
    root = execute_direct(
        "numeric.root",
        {"expression": "x^3 - 2*x - 5", "variable": "x", "bracket": [2, 3]},
    )
    assert root["exact"] is None
    assert root["approx"].startswith("2.094")

    inverse = execute_direct("matrix.inverse", {"matrix": [[1, 2], [3, 4]]})
    assert inverse["exact"] == [["-2", "1"], ["3/2", "-1/2"]]

    statistics = execute_direct("statistics.describe", {"values": [1, 2, 3, 4]})
    assert statistics["mean"]["exact"] == "5/2"
    assert statistics["median"]["exact"] == "5/2"
    assert statistics["standardDeviation"]["exact"] == "sqrt(5)/2"
    assert statistics["range"]["exact"] == "3"
    assert statistics["quartiles"]["method"] == "linear"
    assert statistics["quartiles"]["q1"]["exact"] == "7/4"

    units = execute_direct(
        "units.convert",
        {"value": 1000, "fromUnit": "meter", "toUnit": "kilometer"},
    )
    assert units["exact"] == "1"
    assert units["unit"] == "km"


def test_inverse_timeout_is_not_misreported_as_a_singular_matrix() -> None:
    # Negative regression: an in-process evaluation timeout raised inside
    # matrix.inv() must surface as E_TIMEOUT, never as a false singular-matrix
    # domain claim.
    hilbert = [
        [f"1/{row + column + 1}" for column in range(50)]
        for row in range(50)
    ]
    with pytest.raises(CalculatorError) as raised:
        execute_direct("matrix.inverse", {"matrix": hilbert}, timeout_ms=100)
    assert raised.value.code == "E_TIMEOUT"

    with pytest.raises(CalculatorError) as singular:
        execute_direct("matrix.inverse", {"matrix": [[1, 2], [2, 4]]})
    assert singular.value.code == "E_DOMAIN"


def test_unprintable_exact_integer_is_an_output_limit_not_a_runtime_failure() -> None:
    # Negative regression: a node-bounded expression whose exact result exceeds
    # the interpreter's integer-string limit is an output limit, and the
    # interpreter's remediation hint must not leak into the message. The code
    # and envelope must agree with that: output phase and reduce_request, not
    # an instruction to fix mathematically valid input.
    with pytest.raises(CalculatorError) as raised:
        execute_direct("expression.evaluate", {"expression": "(10**10000)**2"})
    assert raised.value.code == "E_OUTPUT_LIMIT"
    assert "set_int_max_str_digits" not in raised.value.message
    payload = raised.value.as_dict()
    assert payload["phase"] == "output"
    assert payload["suggestedAction"] == "reduce_request"
    assert payload["retryable"] is False


def test_integer_text_accepts_only_ascii_digit_strings() -> None:
    # Negative regression: isdigit()-style acceptance let Unicode digits and
    # multi-sign text through to int() (E_RUNTIME or silent success).
    for bad in ["٥", "²", "+-5"]:
        with pytest.raises(CalculatorError) as raised:
            execute_direct("integer.factorization", {"value": bad})
        assert raised.value.code == "E_INPUT"


def test_variable_names_are_capped_at_sixty_four_characters() -> None:
    with pytest.raises(CalculatorError) as raised:
        execute_direct(
            "expression.equivalent",
            {"left": "a", "right": "a", "variables": ["a" * 65]},
        )
    assert raised.value.code == "E_LIMIT"


def test_numeric_provenance_is_explicit_for_statistics_and_units() -> None:
    approximate_statistics = execute_direct("statistics.describe", {"values": [0.1, 0.2]})
    assert approximate_statistics["mean"]["exact"] is None
    assert approximate_statistics["mean"]["approx"].startswith("0.15")
    assert approximate_statistics["warnings"]
    assert approximate_statistics["precision"] <= 15

    exact_statistics = execute_direct("statistics.describe", {"values": ["0.1", "0.2"]})
    assert exact_statistics["mean"]["exact"] == "3/20"
    assert exact_statistics["warnings"] == []

    approximate_units = execute_direct(
        "units.convert",
        {"value": 0.1, "fromUnit": "meter", "toUnit": "centimeter"},
    )
    assert approximate_units["exact"] is None
    assert approximate_units["warnings"]

    exact_units = execute_direct(
        "units.convert",
        {"value": "0.1", "fromUnit": "meter", "toUnit": "centimeter"},
    )
    assert exact_units["exact"] == "10"
    assert exact_units["warnings"] == []

    exact_ratio = execute_direct(
        "units.convert",
        {"value": 1, "fromUnit": "meter", "toUnit": "inch"},
    )
    assert exact_ratio["exact"] == "5000/127"

    exact_area = execute_direct(
        "units.convert",
        {"value": 1, "fromUnit": "meter ** 2", "toUnit": "kilometer ** 2"},
    )
    assert exact_area["exact"] == "1/1000000"
    assert exact_area["unit"] == "km ** 2"

    irrational_units = execute_direct(
        "units.convert",
        {"value": 1, "fromUnit": "radian", "toUnit": "degree"},
    )
    assert irrational_units["exact"] is None
    assert irrational_units["warnings"]


def test_symbolic_solve_classifies_infinite_none_and_general_sets() -> None:
    periodic = execute_direct(
        "algebra.solve",
        {"equations": "sin(x)=0", "variables": ["x"], "domain": "real"},
    )
    assert periodic["classification"] == "infinite"
    assert periodic["complete"] is True
    assert "ImageSet" in periodic["solutionSet"]
    assert periodic["solutions"] == []

    identity = execute_direct(
        "algebra.solve",
        {"equations": "x=x", "variables": ["x"], "domain": "real"},
    )
    assert identity["classification"] == "infinite"
    assert identity["solutionSet"] == "Reals"

    contradiction = execute_direct(
        "algebra.solve",
        {"equations": "x=x+1", "variables": ["x"], "domain": "real"},
    )
    assert contradiction["classification"] == "none"
    assert contradiction["solutionSet"] == "EmptySet"

    contradictory_system = execute_direct(
        "algebra.solve",
        {"equations": ["x=1", "x=2"], "variables": ["x"], "domain": "real"},
    )
    assert contradictory_system["classification"] == "none"
    assert contradictory_system["complete"] is True
    assert contradictory_system["solutions"] == []

    redundant_system = execute_direct(
        "algebra.solve",
        {"equations": ["x=1", "2*x=2"], "variables": ["x"], "domain": "real"},
    )
    assert redundant_system["classification"] == "finite"
    assert redundant_system["complete"] is True
    assert redundant_system["solutions"] == [
        {"x": {"exact": "1", "approx": "1.000000000000000"}}
    ]


def test_exact_statistics_are_not_limited_by_binary64_range() -> None:
    result = execute_direct("statistics.describe", {"values": ["1e400", "2e400"]})
    exact_mean = result["mean"]["exact"]
    assert exact_mean.startswith("15")
    assert len(exact_mean) == 401
    assert result["warnings"] == []


def test_operation_schema_rejects_unknown_arguments() -> None:
    with pytest.raises(CalculatorError) as caught:
        execute_direct(
            "expression.evaluate",
            {"expression": "sqrt(2)", "precison": 50},
        )
    assert caught.value.code == "E_INPUT"
    assert caught.value.details == {"path": [], "rule": "additionalProperties"}


def test_numeric_root_honors_requested_high_precision() -> None:
    root = execute_direct(
        "numeric.root",
        {
            "expression": "x^3 - 2*x - 5",
            "variable": "x",
            "bracket": [2, 3],
            "precision": 50,
        },
    )
    assert root["exact"] is None
    assert root["precision"] == 50
    assert root["approx"].startswith("2.094551481542326591482386540579302963857306105628")


def test_float_matrix_is_approximate_and_does_not_overclaim_precision() -> None:
    inverse = execute_direct(
        "matrix.inverse",
        {"matrix": [[1.0, 2.0], [3.0, 4.0]], "precision": 50},
    )
    assert inverse["exact"] is None
    assert inverse["precision"] <= 15
    assert inverse["approx"][0][0].startswith("-2")


def test_float_eigenvalues_do_not_overclaim_precision() -> None:
    eigenvalues = execute_direct(
        "matrix.eigenvalues",
        {"matrix": [[1.0, 2.0], [3.0, 4.0]], "precision": 50},
    )
    assert eigenvalues["precision"] <= 15
    assert all(value["exact"] is None for value in eigenvalues["values"])
    assert any(value["approx"].startswith("-0.372281323269014") for value in eigenvalues["values"])


def test_function_sample_builds_exact_function_tables() -> None:
    from decimal import Decimal

    grid = execute_direct(
        "function.sample",
        {"expression": "x^2", "variable": "x", "lower": "0", "upper": "1", "count": 5},
    )
    assert grid["kind"] == "function_table"
    assert grid["count"] == 5
    # Grid labels are decimal text, which deliberately takes the approximate
    # provenance lane; explicit rational point texts stay exact.
    assert grid["points"][1]["exact"] is None
    assert Decimal(grid["points"][1]["approx"]) == Decimal("0.0625")
    assert Decimal(grid["points"][2]["approx"]) == Decimal("0.25")

    poles = execute_direct(
        "function.sample",
        {"expression": "1/x", "variable": "x", "points": ["-1", "0", "2"]},
    )
    assert poles["points"][0]["exact"] == "-1"
    assert poles["points"][1]["undefined"] is True
    assert poles["points"][1]["exact"] is None
    assert any("undefined" in warning for warning in poles["warnings"])

    # sin(x)/x at zero is a removable discontinuity; the table keeps the
    # strict definedness rule instead of silently healing it.
    removable = execute_direct(
        "function.sample",
        {"expression": "sin(x)/x", "variable": "x", "lower": "-2", "upper": "2", "count": 5},
    )
    assert removable["points"][2]["undefined"] is True

    with pytest.raises(CalculatorError) as both_modes:
        execute_direct(
            "function.sample",
            {"expression": "x", "variable": "x", "points": ["1"], "count": 5},
        )
    assert both_modes.value.code == "E_INPUT"

    with pytest.raises(CalculatorError) as neither_mode:
        execute_direct("function.sample", {"expression": "x", "variable": "x"})
    assert neither_mode.value.code == "E_INPUT"
