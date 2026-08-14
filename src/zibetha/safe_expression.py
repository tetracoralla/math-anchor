from __future__ import annotations

import ast
import re
from collections.abc import Mapping
from typing import Any

import sympy as sp

from .errors import CalculatorError, require


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CONSTANTS: dict[str, sp.Expr] = {
    "pi": sp.pi,
    "e": sp.E,
    "E": sp.E,
    "i": sp.I,
    "I": sp.I,
    "inf": sp.oo,
}
_FUNCTIONS = {
    "abs": sp.Abs,
    "acos": sp.acos,
    "asin": sp.asin,
    "atan": sp.atan,
    "ceil": sp.ceiling,
    "cos": sp.cos,
    "cosh": sp.cosh,
    "exp": sp.exp,
    "factorial": sp.factorial,
    "floor": sp.floor,
    "gamma": sp.gamma,
    "ln": sp.log,
    "log": sp.log,
    "max": sp.Max,
    "min": sp.Min,
    "sin": sp.sin,
    "sinh": sp.sinh,
    "sqrt": sp.sqrt,
    "tan": sp.tan,
    "tanh": sp.tanh,
}
_BINARY = {
    ast.Add: lambda left, right: left + right,
    ast.Sub: lambda left, right: left - right,
    ast.Mult: lambda left, right: left * right,
    ast.Div: lambda left, right: left / right,
    ast.Mod: lambda left, right: sp.Mod(left, right),
    ast.Pow: lambda left, right: left**right,
}


def normalize_expression_source(source: str) -> str:
    return (
        source.strip()
        .replace("×", "*")
        .replace("÷", "/")
        .replace("−", "-")
        .replace("π", "pi")
        .replace("^", "**")
    )


class _Translator(ast.NodeVisitor):
    def __init__(
        self,
        symbols: Mapping[str, sp.Symbol],
        values: Mapping[str, sp.Expr],
        source: str,
    ) -> None:
        self.symbols = symbols
        self.values = values
        self.source = source
        self.node_count = 0

    def visit(self, node: ast.AST) -> sp.Expr:  # type: ignore[override]
        self.node_count += 1
        require(self.node_count <= 512, "E_LIMIT", "expression is too complex")
        return super().visit(node)

    def generic_visit(self, node: ast.AST) -> sp.Expr:
        raise CalculatorError(
            "E_AST_BLOCK",
            f"unsupported expression syntax: {type(node).__name__}",
        )

    def visit_Expression(self, node: ast.Expression) -> sp.Expr:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> sp.Expr:
        value = node.value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CalculatorError("E_AST_BLOCK", "only numeric literals are allowed")
        if isinstance(value, int):
            require(len(str(abs(value))) <= 1000, "E_LIMIT", "integer literal is too large")
            return sp.Integer(value)
        lexical_value = ast.get_source_segment(self.source, node)
        require(isinstance(lexical_value, str), "E_SYNTAX", "numeric literal could not be read")
        return sp.Float(lexical_value)

    def visit_Name(self, node: ast.Name) -> sp.Expr:
        if node.id in self.values:
            return self.values[node.id]
        if node.id in self.symbols:
            return self.symbols[node.id]
        if node.id in _CONSTANTS:
            return _CONSTANTS[node.id]
        raise CalculatorError("E_NAME", f"unknown name: {node.id}")

    def visit_UnaryOp(self, node: ast.UnaryOp) -> sp.Expr:
        operand = self.visit(node.operand)
        if isinstance(node.op, ast.UAdd):
            return operand
        if isinstance(node.op, ast.USub):
            return -operand
        raise CalculatorError("E_AST_BLOCK", "unsupported unary operator")

    def visit_BinOp(self, node: ast.BinOp) -> sp.Expr:
        operator = _BINARY.get(type(node.op))
        if operator is None:
            raise CalculatorError("E_AST_BLOCK", "unsupported binary operator")
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Pow) and right.is_number:
            try:
                numeric_exponent = float(sp.N(sp.Abs(right), 20))
            except (TypeError, ValueError, OverflowError) as error:
                raise CalculatorError("E_LIMIT", "exponent magnitude must be finite") from error
            require(numeric_exponent <= 10_000, "E_LIMIT", "exponent is too large")
        return operator(left, right)

    def visit_Call(self, node: ast.Call) -> sp.Expr:
        if not isinstance(node.func, ast.Name) or node.keywords:
            raise CalculatorError("E_AST_BLOCK", "only registered function calls are allowed")
        function = _FUNCTIONS.get(node.func.id)
        if function is None:
            raise CalculatorError("E_NAME", f"unknown function: {node.func.id}")
        require(len(node.args) <= 16, "E_LIMIT", "too many function arguments")
        arguments = [self.visit(argument) for argument in node.args]
        if node.func.id == "factorial" and arguments and arguments[0].is_Integer:
            require(int(arguments[0]) <= 5000, "E_LIMIT", "factorial input is too large")
        try:
            return function(*arguments)
        except (TypeError, ValueError) as error:
            raise CalculatorError("E_INPUT", f"invalid arguments for {node.func.id}: {error}") from error


def _numeric_value(value: Any) -> sp.Expr:
    if isinstance(value, bool):
        raise CalculatorError("E_INPUT", "boolean variable values are not allowed")
    if isinstance(value, int):
        return sp.Integer(value)
    if isinstance(value, float):
        return sp.Float(str(value))
    if isinstance(value, str):
        return parse_expression(value)
    raise CalculatorError("E_INPUT", "variable values must be numbers or numeric expressions")


def make_symbols(names: list[str]) -> dict[str, sp.Symbol]:
    require(len(names) <= 16, "E_LIMIT", "too many variables")
    require(len(set(names)) == len(names), "E_INPUT", "variables must not contain duplicates")
    for name in names:
        require(bool(_IDENTIFIER.match(name)), "E_INPUT", f"invalid variable name: {name}")
        require(name not in _CONSTANTS and name not in _FUNCTIONS, "E_INPUT", f"reserved variable name: {name}")
    return {name: sp.Symbol(name) for name in names}


def parse_expression(
    source: str,
    *,
    symbols: Mapping[str, sp.Symbol] | None = None,
    values: Mapping[str, Any] | None = None,
) -> sp.Expr:
    require(isinstance(source, str), "E_INPUT", "expression must be a string")
    require(0 < len(source) <= 4096, "E_LIMIT", "expression must contain 1 to 4096 characters")
    normalized = normalize_expression_source(source)
    try:
        parsed = ast.parse(normalized, mode="eval")
    except SyntaxError as error:
        raise CalculatorError("E_SYNTAX", f"invalid expression: {error.msg}") from error
    translated_values = {name: _numeric_value(value) for name, value in (values or {}).items()}
    return _Translator(symbols or {}, translated_values, normalized).visit(parsed)


def parse_equation(source: str, symbols: Mapping[str, sp.Symbol]) -> sp.Equality:
    parts = source.split("=")
    require(len(parts) <= 2, "E_SYNTAX", "equation may contain at most one equals sign")
    if len(parts) == 1:
        return sp.Eq(parse_expression(parts[0], symbols=symbols), 0)
    require(bool(parts[0].strip()) and bool(parts[1].strip()), "E_SYNTAX", "both sides of an equation are required")
    return sp.Eq(
        parse_expression(parts[0], symbols=symbols),
        parse_expression(parts[1], symbols=symbols),
    )


def parse_matrix(values: Any) -> sp.Matrix:
    require(isinstance(values, list) and values, "E_INPUT", "matrix must be a non-empty array of rows")
    require(len(values) <= 50, "E_LIMIT", "matrix may contain at most 50 rows")
    require(all(isinstance(row, list) and row for row in values), "E_INPUT", "matrix rows must be non-empty arrays")
    width = len(values[0])
    require(width <= 50, "E_LIMIT", "matrix may contain at most 50 columns")
    require(all(len(row) == width for row in values), "E_INPUT", "matrix rows must have equal length")
    return sp.Matrix([[parse_expression(str(cell)) for cell in row] for row in values])
