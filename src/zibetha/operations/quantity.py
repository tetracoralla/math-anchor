from __future__ import annotations

import ast
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Any

import pint
from pint.util import UnitsContainer
import sympy as sp

from ..errors import CalculatorError, require
from ..formatting import effective_precision, value_result
from ..validation import integer_arg, string_arg
from .data import _EXACT_UNIT_REGISTRY, _FLOAT_UNIT_REGISTRY, _sympy_fraction, _unit_path_is_rational


def evaluate(arguments: dict[str, Any]) -> dict[str, Any]:
    expression = string_arg(arguments, "expression", max_length=2048)
    target_unit = arguments.get("toUnit")
    require(target_unit is None or isinstance(target_unit, str), "E_INPUT", "toUnit must be a string")
    if isinstance(target_unit, str):
        target_unit = target_unit.strip()
        require(bool(target_unit), "E_INPUT", "toUnit must not be empty")
        require(len(target_unit) <= 128, "E_LIMIT", "toUnit is too long")
    precision = integer_arg(arguments, "precision", default=30, minimum=2, maximum=200)
    warnings: list[str] = []

    exact = True
    try:
        translator = _QuantityTranslator(_EXACT_UNIT_REGISTRY, exact=True)
        quantity = translator.translate(expression)
        if target_unit is not None:
            parsed_target = _EXACT_UNIT_REGISTRY.parse_units(target_unit)
            exact = (
                translator.conversions_are_rational
                and _unit_path_is_rational(_EXACT_UNIT_REGISTRY, quantity.units)
                and _unit_path_is_rational(_EXACT_UNIT_REGISTRY, parsed_target)
            )
            quantity = quantity.to(parsed_target)
        else:
            exact = translator.conversions_are_rational
    except TypeError:
        exact = False
        warnings.append("This quantity expression uses an approximate or irrational unit conversion path.")
        try:
            quantity = _QuantityTranslator(_FLOAT_UNIT_REGISTRY, exact=False).translate(expression)
            if target_unit is not None:
                quantity = quantity.to(_FLOAT_UNIT_REGISTRY.parse_units(target_unit))
        except (pint.PintError, TypeError, ValueError, ZeroDivisionError) as error:
            raise CalculatorError("E_UNIT", f"quantity expression failed: {error}") from error
    except (InvalidOperation, pint.PintError, ValueError, ZeroDivisionError) as error:
        raise CalculatorError("E_UNIT", f"quantity expression failed: {error}") from error

    magnitude = quantity.magnitude
    if exact and isinstance(magnitude, Fraction):
        result_value = _sympy_fraction(magnitude)
        reported_precision = precision
    else:
        exact = False
        if isinstance(magnitude, Fraction):
            result_value = sp.N(_sympy_fraction(magnitude), min(precision, 15))
        else:
            require(isinstance(magnitude, (int, float)) and not isinstance(magnitude, bool), "E_DOMAIN", "quantity magnitude must be numeric")
            require(sp.Float(str(magnitude)).is_finite is True, "E_DOMAIN", "quantity magnitude must be finite")
            result_value = sp.Float(str(magnitude), 15)
        reported_precision = effective_precision([result_value], precision)
        if not warnings:
            warnings.append("The reported magnitude follows floating-point unit arithmetic and is approximate.")

    formatted = value_result(result_value, reported_precision)
    display_units = UnitsContainer(
        {
            name: int(exponent) if isinstance(exponent, Fraction) and exponent.denominator == 1 else float(exponent)
            for name, exponent in quantity.units._units.items()
        }
    )
    conventional_unit = _FLOAT_UNIT_REGISTRY.Unit(display_units)
    display_unit = f"{conventional_unit:~}"
    return {
        "status": "ok",
        "operation": "quantity.evaluate",
        "kind": "quantity_expression",
        "expression": expression,
        "exact": formatted["exact"] if exact else None,
        "approx": formatted["approx"],
        "precision": reported_precision,
        "unit": display_unit,
        "dimensionality": str(conventional_unit.dimensionality),
        "convertedTo": target_unit,
        "warnings": warnings,
    }


class _QuantityTranslator(ast.NodeVisitor):
    def __init__(self, registry: pint.UnitRegistry, *, exact: bool) -> None:
        self.registry = registry
        self.exact = exact
        self.source = ""
        self.node_count = 0
        self.conversions_are_rational = True

    def translate(self, source: str) -> pint.Quantity:
        normalized = (
            source.strip()
            .replace("×", "*")
            .replace("÷", "/")
            .replace("−", "-")
            .replace("²", "**2")
            .replace("³", "**3")
            .replace("^", "**")
        )
        self.source = normalized
        try:
            parsed = ast.parse(normalized, mode="eval")
        except SyntaxError as error:
            raise CalculatorError("E_SYNTAX", f"invalid quantity expression: {error.msg}") from error
        result = self.visit(parsed)
        require(isinstance(result, pint.Quantity), "E_RUNTIME", "quantity parser produced an invalid result")
        return result

    def visit(self, node: ast.AST) -> Any:  # type: ignore[override]
        self.node_count += 1
        require(self.node_count <= 256, "E_LIMIT", "quantity expression is too complex")
        return super().visit(node)

    def generic_visit(self, node: ast.AST) -> Any:
        raise CalculatorError("E_AST_BLOCK", f"unsupported quantity syntax: {type(node).__name__}")

    def visit_Expression(self, node: ast.Expression) -> pint.Quantity:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> pint.Quantity:
        value = node.value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CalculatorError("E_AST_BLOCK", "only numeric literals and unit names are allowed")
        lexical = ast.get_source_segment(self.source, node)
        require(isinstance(lexical, str), "E_SYNTAX", "numeric literal could not be read")
        if self.exact:
            magnitude: Fraction | float = Fraction(Decimal(lexical))
        else:
            magnitude = float(lexical)
        require(abs(magnitude) <= 10**300, "E_LIMIT", "numeric literal is too large")
        return self.registry.Quantity(magnitude)

    def visit_Name(self, node: ast.Name) -> pint.Quantity:
        try:
            unit = self.registry.parse_units(node.id)
        except (pint.PintError, TypeError, ValueError) as error:
            raise CalculatorError("E_UNIT", f"unknown unit: {node.id}") from error
        return self.registry.Quantity(Fraction(1) if self.exact else 1.0, unit)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> pint.Quantity:
        operand = self.visit(node.operand)
        if isinstance(node.op, ast.UAdd):
            return operand
        if isinstance(node.op, ast.USub):
            return -operand
        raise CalculatorError("E_AST_BLOCK", "unsupported unary operator")

    def visit_BinOp(self, node: ast.BinOp) -> pint.Quantity:
        left = self.visit(node.left)
        right = self.visit(node.right)
        try:
            if isinstance(node.op, ast.Add):
                if left.units != right.units:
                    self.conversions_are_rational = (
                        self.conversions_are_rational
                        and _unit_path_is_rational(self.registry, left.units)
                        and _unit_path_is_rational(self.registry, right.units)
                    )
                return left + right
            if isinstance(node.op, ast.Sub):
                if left.units != right.units:
                    self.conversions_are_rational = (
                        self.conversions_are_rational
                        and _unit_path_is_rational(self.registry, left.units)
                        and _unit_path_is_rational(self.registry, right.units)
                    )
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                require(right.dimensionless, "E_UNIT", "quantity exponents must be dimensionless")
                exponent = right.magnitude
                require(
                    isinstance(exponent, (int, float, Fraction)) and float(exponent).is_integer(),
                    "E_UNIT",
                    "quantity exponents must be integers",
                )
                exponent_int = int(exponent)
                require(abs(exponent_int) <= 12, "E_LIMIT", "quantity exponent magnitude may not exceed 12")
                return left**exponent_int
        except (pint.PintError, TypeError, ValueError, ZeroDivisionError) as error:
            raise CalculatorError("E_UNIT", f"quantity operation failed: {error}") from error
        raise CalculatorError("E_AST_BLOCK", "unsupported binary operator")
