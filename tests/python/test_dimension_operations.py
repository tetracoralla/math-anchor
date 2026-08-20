from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator

from math_anchor.catalog import describe_operation, search_operations
from math_anchor.dimension_expression import DimensionVector
from math_anchor.errors import CalculatorError
from math_anchor.runtime import execute_direct


def test_dimension_check_reports_exact_canonical_vectors_without_overclaiming() -> None:
    result = execute_direct(
        "dimension.check",
        {
            "left": "F",
            "right": "m * a",
            "symbols": {
                "F": "newton",
                "m": "kilogram",
                "a": "meter / second^2",
            },
        },
    )

    expected = {"mass": "1", "length": "1", "time": "-2"}
    assert result["status"] == "ok"
    assert result["kind"] == "dimensional_analysis"
    assert result["scope"] == "dimensional_consistency_only"
    assert result["dimensionallyConsistent"] is True
    assert result["leftDimension"] == expected
    assert result["rightDimension"] == expected
    assert result["leftDisplay"] == "[mass] * [length] / [time]^2"
    assert result["issues"] == []


def test_dimension_check_validates_every_additive_term() -> None:
    consistent = execute_direct(
        "dimension.check",
        {
            "left": "d",
            "right": "v * t + 0.5 * a * t^2",
            "symbols": {
                "d": "meter",
                "v": "meter / second",
                "a": "meter / second^2",
                "t": "second",
            },
        },
    )
    assert consistent["dimensionallyConsistent"] is True

    mismatch = execute_direct(
        "dimension.check",
        {
            "left": "d",
            "right": "v + 0.5 * a * t^2",
            "symbols": {
                "d": "meter",
                "v": "meter / second",
                "a": "meter / second^2",
                "t": "second",
            },
        },
    )
    assert mismatch["status"] == "ok"
    assert mismatch["dimensionallyConsistent"] is False
    assert mismatch["leftDimension"] == {"length": "1"}
    assert mismatch["rightDimension"] is None
    assert mismatch["rightDisplay"] is None
    assert [issue["code"] for issue in mismatch["issues"]] == ["DIMENSION_ADD_MISMATCH"]
    additive_issue = next(
        issue for issue in mismatch["issues"] if issue["code"] == "DIMENSION_ADD_MISMATCH"
    )
    assert additive_issue["left"] == {"length": "1", "time": "-1"}
    assert additive_issue["right"] == {"length": "1"}


def test_dimension_check_reports_a_top_level_equation_mismatch() -> None:
    result = execute_direct(
        "dimension.check",
        {
            "left": "distance",
            "right": "duration",
            "symbols": {"distance": "meter", "duration": "second"},
        },
    )

    assert result["dimensionallyConsistent"] is False
    assert result["leftDimension"] == {"length": "1"}
    assert result["rightDimension"] == {"time": "1"}
    assert result["issues"] == [
        {
            "code": "DIMENSION_EQUATION_MISMATCH",
            "expression": "distance = duration",
            "message": "the two sides of the equation have different dimensions",
            "left": {"length": "1"},
            "right": {"time": "1"},
        }
    ]

    normalized = execute_direct(
        "dimension.check",
        {
            "left": "distance",
            "right": "duration × 1",
            "symbols": {"distance": "meter", "duration": "second"},
        },
    )
    assert normalized["rightExpression"] == "duration × 1"
    assert normalized["issues"][0]["expression"] == "distance = duration * 1"


@pytest.mark.parametrize("function", ["sin", "cos", "tan", "log", "exp"])
def test_dimension_check_requires_dimensionless_function_arguments(function: str) -> None:
    accepted = execute_direct(
        "dimension.check",
        {
            "left": "y",
            "right": f"{function}(theta)",
            "symbols": {"y": {}, "theta": "radian"},
        },
    )
    assert accepted["dimensionallyConsistent"] is True

    rejected = execute_direct(
        "dimension.check",
        {
            "left": "y",
            "right": f"{function}(distance)",
            "symbols": {"y": {}, "distance": "meter"},
        },
    )
    assert rejected["dimensionallyConsistent"] is False
    assert rejected["issues"] == [
        {
            "code": "DIMENSION_FUNCTION_ARGUMENT",
            "expression": f"{function}(distance)",
            "message": f"{function} requires a dimensionless argument",
            "function": function,
            "actual": {"length": "1"},
        }
    ]


def test_dimension_check_supports_exact_fractional_powers_and_direct_vectors() -> None:
    for right in ("sqrt(area)", "area^0.5", "area^(1/2)"):
        result = execute_direct(
            "dimension.check",
            {
                "left": "length",
                "right": right,
                "symbols": {
                    "length": {"length": "1"},
                    "area": {"length": "2"},
                },
            },
        )
        assert result["dimensionallyConsistent"] is True
        assert result["rightDimension"] == {"length": "1"}

    absolute = execute_direct(
        "dimension.check",
        {
            "left": "speed",
            "right": "abs(velocity)",
            "symbols": {
                "speed": {"length": 1, "time": -1},
                "velocity": "meter / second",
            },
        },
    )
    assert absolute["dimensionallyConsistent"] is True


def test_dimension_check_separates_input_and_derived_exponent_limits() -> None:
    result = execute_direct(
        "dimension.check",
        {
            "left": "x^12",
            "right": "x^12",
            "symbols": {"x": {"length": 999_983}},
        },
    )
    assert result["dimensionallyConsistent"] is True
    assert result["leftDimension"] == {"length": "11999796"}


def test_dimension_check_accepts_safe_nondecimal_integer_literals() -> None:
    result = execute_direct(
        "dimension.check",
        {
            "left": "x",
            "right": "0x10 * x",
            "symbols": {"x": "meter"},
        },
    )
    assert result["dimensionallyConsistent"] is True


def test_dimension_parser_rejects_unknown_unsafe_and_nonconstant_power_syntax() -> None:
    with pytest.raises(CalculatorError) as unknown:
        execute_direct(
            "dimension.check",
            {"left": "F", "right": "m * missing", "symbols": {"F": "N", "m": "kg"}},
        )
    assert unknown.value.code == "E_NAME"

    with pytest.raises(CalculatorError) as unsafe:
        execute_direct(
            "dimension.check",
            {
                "left": "x",
                "right": "__import__('os').system('id')",
                "symbols": {"x": {}},
            },
        )
    assert unsafe.value.code == "E_AST_BLOCK"

    with pytest.raises(CalculatorError) as exponent:
        execute_direct(
            "dimension.check",
            {
                "left": "area",
                "right": "length^power",
                "symbols": {"area": "meter^2", "length": "meter", "power": {}},
            },
        )
    assert exponent.value.code == "E_INPUT"

    with pytest.raises(CalculatorError) as invalid_unit:
        execute_direct(
            "dimension.check",
            {
                "left": "x",
                "right": "x",
                "symbols": {"x": "definitely_not_a_real_unit"},
            },
        )
    assert invalid_unit.value.code == "E_UNIT"

    with pytest.raises(CalculatorError) as coefficient_limit:
        execute_direct(
            "dimension.infer",
            {
                "equations": [
                    {
                        "left": "length",
                        "right": "((((((x^12)^12)^12)^12)^12)^12)",
                    }
                ],
                "known": {"length": "meter"},
                "unknown": ["x"],
            },
        )
    assert coefficient_limit.value.code == "E_LIMIT"


def test_dimension_pi_groups_returns_an_exact_deterministic_basis() -> None:
    variables = {
        "rho": "kilogram / meter^3",
        "v": "meter / second",
        "L": "meter",
        "mu": "pascal * second",
    }
    result = execute_direct("dimension.pi_groups", {"variables": variables})
    reordered = execute_direct(
        "dimension.pi_groups",
        {"variables": dict(reversed(list(variables.items())))},
    )

    assert result == reordered
    assert result["kind"] == "dimensionless_groups"
    assert result["scope"] == "dimensionless_basis_only"
    assert result["basisConvention"] == "primitive_integer_exponents"
    assert result["variables"] == ["L", "mu", "rho", "v"]
    assert result["rank"] == 3
    assert result["nullity"] == 1
    assert result["groups"] == [
        {
            "index": 1,
            "exponents": {"L": "1", "mu": "-1", "rho": "1", "v": "1"},
            "expression": "L * rho * v / mu",
        }
    ]
    assert result["warnings"]


def test_dimension_pi_groups_normalizes_integer_exponents_and_empty_nullspaces() -> None:
    normalized = execute_direct(
        "dimension.pi_groups",
        {
            "variables": {
                "area": "meter^2",
                "length": "meter",
            }
        },
    )
    assert normalized["groups"] == [
        {
            "index": 1,
            "exponents": {"area": "1", "length": "-2"},
            "expression": "area / length^2",
        }
    ]

    independent = execute_direct(
        "dimension.pi_groups",
        {"variables": {"distance": "meter", "duration": "second"}},
    )
    assert independent["rank"] == 2
    assert independent["nullity"] == 0
    assert independent["groups"] == []
    assert independent["warnings"] == []


def test_dimension_pi_groups_rejects_empty_or_invalid_declarations() -> None:
    for variables in (
        {},
        {"x": "definitely_not_a_real_unit"},
        {"x": {"length": 1}},
    ):
        with pytest.raises(CalculatorError) as caught:
            execute_direct("dimension.pi_groups", {"variables": variables})
        assert caught.value.code in {"E_INPUT", "E_UNIT"}


def test_dimension_infer_returns_one_unique_dimension_not_a_preferred_unit() -> None:
    result = execute_direct(
        "dimension.infer",
        {
            "equations": [{"left": "F", "right": "m * a"}],
            "known": {"F": "newton", "m": "kilogram"},
            "unknown": ["a"],
        },
    )

    assert result["classification"] == "unique"
    assert result["scope"] == "dimensional_consistency_only"
    assert result["inferred"] == {
        "a": {
            "dimension": {"length": "1", "time": "-2"},
            "display": "[length] / [time]^2",
        }
    }
    assert result["unresolved"] == []
    assert result["rank"] == 1
    assert result["degreesOfFreedom"] == 0

    large_exact = execute_direct(
        "dimension.infer",
        {
            "equations": [{"left": "x", "right": "reference^12"}],
            "known": {"reference": {"length": 999_983}},
            "unknown": ["x"],
        },
    )
    assert large_exact["classification"] == "unique"
    assert large_exact["inferred"]["x"]["dimension"] == {"length": "11999796"}


def test_dimension_infer_uses_addition_and_function_constraints() -> None:
    acceleration = execute_direct(
        "dimension.infer",
        {
            "equations": [{"left": "d", "right": "v * t + (1/2) * a * t^2"}],
            "known": {"d": "meter", "v": "meter / second", "t": "second"},
            "unknown": ["a"],
        },
    )
    assert acceleration["classification"] == "unique"
    assert acceleration["inferred"]["a"]["dimension"] == {"length": "1", "time": "-2"}
    assert acceleration["constraintCount"] == 2

    dimensionless = execute_direct(
        "dimension.infer",
        {
            "equations": [{"left": "y", "right": "exp(x)"}],
            "known": {"y": {}},
            "unknown": ["x"],
        },
    )
    assert dimensionless["classification"] == "unique"
    assert dimensionless["inferred"]["x"] == {
        "dimension": {},
        "display": "dimensionless",
    }


def test_dimension_infer_distinguishes_underdetermined_and_inconsistent() -> None:
    underdetermined = execute_direct(
        "dimension.infer",
        {
            "equations": [{"left": "z", "right": "x * y"}],
            "known": {"z": "meter"},
            "unknown": ["x", "y"],
        },
    )
    assert underdetermined["classification"] == "underdetermined"
    assert underdetermined["inferred"] == {}
    assert underdetermined["unresolved"] == ["x", "y"]
    assert underdetermined["rank"] == 1
    assert underdetermined["degreesOfFreedom"] == 1

    partially_determined = execute_direct(
        "dimension.infer",
        {
            "equations": [
                {"left": "x", "right": "length_reference"},
                {"left": "z", "right": "y * time_reference"},
            ],
            "known": {"length_reference": "meter", "time_reference": "second"},
            "unknown": ["x", "y", "z"],
        },
    )
    assert partially_determined["classification"] == "underdetermined"
    assert partially_determined["inferred"] == {
        "x": {"dimension": {"length": "1"}, "display": "[length]"}
    }
    assert partially_determined["unresolved"] == ["y", "z"]
    assert partially_determined["rank"] == 2
    assert partially_determined["degreesOfFreedom"] == 1

    inconsistent = execute_direct(
        "dimension.infer",
        {
            "equations": [
                {"left": "x", "right": "length_reference"},
                {"left": "x", "right": "time_reference"},
            ],
            "known": {"length_reference": "meter", "time_reference": "second"},
            "unknown": ["x"],
        },
    )
    assert inconsistent["status"] == "ok"
    assert inconsistent["classification"] == "inconsistent"
    assert set(inconsistent["conflictingDimensions"]) == {"length", "time"}
    assert inconsistent["inferred"] == {}


def test_dimension_infer_rejects_ambiguous_symbol_declarations_and_schema_drift() -> None:
    with pytest.raises(CalculatorError) as overlap:
        execute_direct(
            "dimension.infer",
            {
                "equations": [{"left": "x", "right": "x"}],
                "known": {"x": "meter"},
                "unknown": ["x"],
            },
        )
    assert overlap.value.code == "E_INPUT"

    with pytest.raises(CalculatorError) as misspelled:
        execute_direct(
            "dimension.infer",
            {
                "equations": [{"left": "x", "right": "y", "rigth": "y"}],
                "unknown": ["x", "y"],
            },
        )
    assert misspelled.value.code == "E_INPUT"
    assert misspelled.value.details == {"path": ["equations", 0], "rule": "additionalProperties"}


def test_dimension_operations_are_discoverable_with_closed_schemas() -> None:
    searched = search_operations("检查物理公式的量纲一致性")
    assert searched["operations"][0]["id"] == "dimension.check"
    assert search_operations("dimensional analysis")["operations"][0]["id"] == "dimension.check"
    assert search_operations("infer acceleration dimension")["operations"][0]["id"] == "dimension.infer"
    assert search_operations("Buckingham Pi theorem")["operations"][0]["id"] == "dimension.pi_groups"
    assert search_operations("生成无量纲组合")["operations"][0]["id"] == "dimension.pi_groups"

    check_description = describe_operation("dimension.check")["operation"]
    check_schema = check_description["inputSchema"]
    assert check_schema["additionalProperties"] is False
    assert check_schema["required"] == ["left", "right", "symbols"]

    check_validator = Draft202012Validator(check_schema)
    valid_vector = {
        "left": "x",
        "right": "x",
        "symbols": {"x": {"length": "1000000/999999"}},
    }
    assert check_validator.is_valid(valid_vector)
    assert execute_direct("dimension.check", valid_vector)["dimensionallyConsistent"] is True
    for invalid_exponent in ("1000001", "0.5", " 1", 1_000_001):
        invalid_vector = {
            "left": "x",
            "right": "x",
            "symbols": {"x": {"length": invalid_exponent}},
        }
        assert not check_validator.is_valid(invalid_vector)
        with pytest.raises(CalculatorError) as rejected:
            execute_direct("dimension.check", invalid_vector)
        assert rejected.value.code in {"E_INPUT", "E_LIMIT"}

    for invalid_name in (" [length] ", "[[length]]", "长度"):
        invalid_vector = {
            "left": "x",
            "right": "x",
            "symbols": {"x": {invalid_name: 1}},
        }
        assert not check_validator.is_valid(invalid_vector)
        with pytest.raises(CalculatorError) as rejected_name:
            DimensionVector.from_mapping({invalid_name: 1})
        assert rejected_name.value.code == "E_INPUT"

    infer_description = describe_operation("dimension.infer")["operation"]
    infer_schema = infer_description["inputSchema"]
    equation_schema = infer_schema["properties"]["equations"]["items"]
    assert equation_schema["additionalProperties"] is False
    assert infer_schema["properties"]["unknown"]["uniqueItems"] is True

    validator = Draft202012Validator(infer_schema)
    assert validator.is_valid(
        {"equations": [{"left": "x", "right": "x"}], "unknown": ["x"]}
    )
    assert not validator.is_valid(
        {"equations": [{"left": "x", "right": "x"}], "unknown": ["x-y"]}
    )
    assert not validator.is_valid(
        {"equations": [{"left": "for", "right": "for"}], "unknown": ["for"]}
    )
    assert not validator.is_valid(
        {
            "equations": [{"left": "x", "right": "x"}],
            "known": {"x-y": "meter"},
            "unknown": ["x"],
        }
    )

    pi_description = describe_operation("dimension.pi_groups")["operation"]
    pi_schema = pi_description["inputSchema"]
    assert pi_schema["additionalProperties"] is False
    assert pi_schema["required"] == ["variables"]
    pi_variables = pi_schema["properties"]["variables"]
    assert pi_variables["minProperties"] == 1
    assert pi_variables["maxProperties"] == 16
