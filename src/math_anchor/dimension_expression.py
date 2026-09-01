from __future__ import annotations

import ast
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import re
from typing import Any, Iterable, Mapping

from .dimension_contract import (
    DIMENSION_EXPONENT_PATTERN,
    DIMENSION_SYMBOL_PATTERN,
    DIMENSION_VECTOR_NAME_PATTERN,
)
from .errors import CalculatorError, require
from .safe_expression import normalize_expression_source


MAX_DIMENSION_COMPONENTS = 16
MAX_DIMENSION_EXPONENT_PART = 1_000_000
MAX_DIMENSION_POWER = 12
MAX_DIMENSION_CONSTRAINTS = 256
# Expression fields are capped at 2048 characters, so an exact literal whose
# numerator or denominator would need more digits than that is rejected before
# the big integer is ever materialized.
MAX_LITERAL_DIGIT_BUDGET = 2048
_DIMENSION_RATIONAL_TEXT = re.compile(r"^[+-]?(?:0|[1-9]\d*)(?:/[1-9]\d*)?$", re.ASCII)
_DIMENSION_VECTOR_NAME = re.compile(DIMENSION_VECTOR_NAME_PATTERN, re.ASCII)

_BASE_DIMENSION_ORDER = (
    "mass",
    "length",
    "time",
    "current",
    "temperature",
    "substance",
    "luminosity",
    "information",
)
_BASE_DIMENSION_INDEX = {
    name: index for index, name in enumerate(_BASE_DIMENSION_ORDER)
}
_DIMENSIONLESS_FUNCTIONS = {"sin", "cos", "tan", "log", "exp"}
_SUPPORTED_FUNCTIONS = _DIMENSIONLESS_FUNCTIONS | {"sqrt", "abs"}


def normalize_dimension_source(source: str) -> str:
    return (
        normalize_expression_source(source)
        .replace("²", "**2")
        .replace("³", "**3")
    )


def _bounded_decimal(text: str) -> Decimal:
    value = Decimal(text)
    if value.is_finite():
        _, digits, exponent = value.as_tuple()
        if len(digits) + abs(exponent) > MAX_LITERAL_DIGIT_BUDGET:
            raise CalculatorError("E_LIMIT", "numeric literal is too complex")
    return value


def _dimension_sort_key(name: str) -> tuple[int, str]:
    return (_BASE_DIMENSION_INDEX.get(name, len(_BASE_DIMENSION_INDEX)), name)


def _canonical_dimension_name(name: Any) -> str:
    require(isinstance(name, str), "E_INPUT", "dimension names must be strings")
    require(len(name) <= 64, "E_LIMIT", "dimension names may not exceed 64 characters")
    require(
        bool(_DIMENSION_VECTOR_NAME.fullmatch(name)),
        "E_INPUT",
        f"invalid dimension name: {name}",
    )
    normalized = name
    if normalized.startswith("[") and normalized.endswith("]"):
        normalized = normalized[1:-1]
    return normalized


def _bounded_fraction(value: Any, *, label: str) -> Fraction:
    require(not isinstance(value, bool), "E_INPUT", f"{label} must be a rational number")
    try:
        if isinstance(value, int):
            parsed = Fraction(value)
        elif isinstance(value, str):
            require(
                bool(_DIMENSION_RATIONAL_TEXT.fullmatch(value)),
                "E_INPUT",
                f"{label} must be canonical integer or rational text",
            )
            parsed = Fraction(value)
        elif isinstance(value, Fraction):
            parsed = value
        else:
            raise ValueError
    except (ValueError, ZeroDivisionError, OverflowError) as error:
        raise CalculatorError("E_INPUT", f"{label} must be an integer or canonical rational text") from error
    require(
        abs(parsed.numerator) <= MAX_DIMENSION_EXPONENT_PART
        and parsed.denominator <= MAX_DIMENSION_EXPONENT_PART,
        "E_LIMIT",
        f"{label} is too complex",
    )
    return parsed


def _bounded_derived_fraction(value: Any, *, label: str) -> Fraction:
    try:
        parsed = value if isinstance(value, Fraction) else Fraction(value)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError) as error:
        raise CalculatorError("E_RUNTIME", f"{label} is not rational") from error
    require(
        len(str(abs(parsed.numerator))) <= MAX_LITERAL_DIGIT_BUDGET
        and len(str(parsed.denominator)) <= MAX_LITERAL_DIGIT_BUDGET,
        "E_LIMIT",
        f"{label} is too complex",
    )
    return parsed


@dataclass(frozen=True)
class DimensionVector:
    components: tuple[tuple[str, Fraction], ...] = ()

    @classmethod
    def from_mapping(cls, values: Mapping[Any, Any]) -> DimensionVector:
        return cls._from_mapping(values, derived=False)

    @classmethod
    def _from_derived_mapping(cls, values: Mapping[Any, Any]) -> DimensionVector:
        return cls._from_mapping(values, derived=True)

    @classmethod
    def _from_mapping(
        cls,
        values: Mapping[Any, Any],
        *,
        derived: bool,
    ) -> DimensionVector:
        require(
            len(values) <= MAX_DIMENSION_COMPONENTS,
            "E_LIMIT",
            f"dimension vectors may contain at most {MAX_DIMENSION_COMPONENTS} components",
        )
        normalized: dict[str, Fraction] = {}
        for raw_name, raw_exponent in values.items():
            name = _canonical_dimension_name(raw_name)
            require(name not in normalized, "E_INPUT", f"duplicate dimension component: {name}")
            exponent = (
                _bounded_derived_fraction(
                    raw_exponent,
                    label=f"derived dimension exponent for {name}",
                )
                if derived
                else _bounded_fraction(
                    raw_exponent,
                    label=f"dimension exponent for {name}",
                )
            )
            if exponent:
                normalized[name] = exponent
        return cls(tuple(sorted(normalized.items(), key=lambda item: _dimension_sort_key(item[0]))))

    def as_dict(self) -> dict[str, Fraction]:
        return dict(self.components)

    def to_json(self) -> dict[str, str]:
        return {name: str(exponent) for name, exponent in self.components}

    def exponent(self, name: str) -> Fraction:
        return self.as_dict().get(name, Fraction())

    def __add__(self, other: DimensionVector) -> DimensionVector:
        combined = self.as_dict()
        for name, exponent in other.components:
            combined[name] = combined.get(name, Fraction()) + exponent
        return DimensionVector._from_derived_mapping(combined)

    def __sub__(self, other: DimensionVector) -> DimensionVector:
        return self + other.scale(Fraction(-1))

    def scale(self, factor: Fraction) -> DimensionVector:
        return DimensionVector._from_derived_mapping(
            {name: exponent * factor for name, exponent in self.components}
        )

    def display(self) -> str:
        if not self.components:
            return "dimensionless"
        positive: list[str] = []
        negative: list[str] = []
        for name, exponent in self.components:
            target = positive if exponent > 0 else negative
            absolute = abs(exponent)
            if absolute == 1:
                target.append(f"[{name}]")
            else:
                rendered = str(absolute)
                suffix = rendered if absolute.denominator == 1 else f"({rendered})"
                target.append(f"[{name}]^{suffix}")
        numerator = " * ".join(positive) if positive else "1"
        if not negative:
            return numerator
        denominator = " * ".join(negative)
        if len(negative) > 1:
            denominator = f"({denominator})"
        return f"{numerator} / {denominator}"


@dataclass(frozen=True)
class DimensionFormula:
    constant: DimensionVector = DimensionVector()
    coefficients: tuple[tuple[str, Fraction], ...] = ()

    @classmethod
    def known(cls, dimension: DimensionVector) -> DimensionFormula:
        return cls(constant=dimension)

    @classmethod
    def unknown(cls, symbol: str) -> DimensionFormula:
        return cls(coefficients=((symbol, Fraction(1)),))

    def coefficient_dict(self) -> dict[str, Fraction]:
        return dict(self.coefficients)

    def __add__(self, other: DimensionFormula) -> DimensionFormula:
        coefficients = self.coefficient_dict()
        for name, coefficient in other.coefficients:
            coefficients[name] = coefficients.get(name, Fraction()) + coefficient
        bounded_coefficients = (
            (
                name,
                _bounded_fraction(value, label=f"dimension coefficient for {name}"),
            )
            for name, value in coefficients.items()
            if value
        )
        return DimensionFormula(
            constant=self.constant + other.constant,
            coefficients=tuple(sorted(bounded_coefficients)),
        )

    def __sub__(self, other: DimensionFormula) -> DimensionFormula:
        return self + other.scale(Fraction(-1))

    def scale(self, factor: Fraction) -> DimensionFormula:
        return DimensionFormula(
            constant=self.constant.scale(factor),
            coefficients=tuple(
                (
                    name,
                    _bounded_fraction(
                        coefficient * factor,
                        label=f"dimension coefficient for {name}",
                    ),
                )
                for name, coefficient in self.coefficients
                if coefficient * factor
            ),
        )


@dataclass(frozen=True)
class DimensionConstraint:
    code: str
    expression: str
    message: str
    left: DimensionFormula
    right: DimensionFormula
    function: str | None = None

    @property
    def difference(self) -> DimensionFormula:
        return self.left - self.right

    def constant_issue(self) -> dict[str, Any] | None:
        difference = self.difference
        require(
            not difference.coefficients,
            "E_RUNTIME",
            "a concrete dimension check retained unresolved symbols",
        )
        if not difference.constant.components:
            return None
        issue: dict[str, Any] = {
            "code": self.code,
            "expression": self.expression,
            "message": self.message,
        }
        if self.function is None:
            issue["left"] = self.left.constant.to_json()
            issue["right"] = self.right.constant.to_json()
        else:
            issue["function"] = self.function
            issue["actual"] = self.left.constant.to_json()
        return issue


class DimensionExpressionAnalyzer(ast.NodeVisitor):
    def __init__(
        self,
        bindings: Mapping[str, DimensionFormula],
        *,
        max_total_nodes: int,
    ) -> None:
        self.bindings = dict(bindings)
        self.max_total_nodes = max_total_nodes
        self.total_nodes = 0
        self.source = ""
        self.constraints: list[DimensionConstraint] = []

    def analyze(self, source: str) -> DimensionFormula:
        normalized = normalize_dimension_source(source)
        self.source = normalized
        try:
            parsed = ast.parse(normalized, mode="eval")
        except (SyntaxError, ValueError) as error:
            message = error.msg if isinstance(error, SyntaxError) else str(error)
            raise CalculatorError("E_SYNTAX", f"invalid dimension expression: {message}") from error
        expression_nodes = sum(1 for _ in ast.walk(parsed))
        require(expression_nodes <= 256, "E_LIMIT", "dimension expression is too complex")
        self.total_nodes += expression_nodes
        require(
            self.total_nodes <= self.max_total_nodes,
            "E_LIMIT",
            "dimensional analysis request contains too many expression nodes",
        )
        result = self.visit(parsed)
        require(
            isinstance(result, DimensionFormula),
            "E_RUNTIME",
            "dimension parser produced an invalid result",
        )
        return result

    def add_equation(
        self,
        left: DimensionFormula,
        right: DimensionFormula,
        expression: str,
    ) -> None:
        self._add_constraint(
            DimensionConstraint(
                code="DIMENSION_EQUATION_MISMATCH",
                expression=expression,
                message="the two sides of the equation have different dimensions",
                left=left,
                right=right,
            )
        )

    def concrete_issues(
        self,
        constraints: Iterable[DimensionConstraint],
    ) -> list[dict[str, Any]]:
        return [
            issue
            for constraint in constraints
            if (issue := constraint.constant_issue()) is not None
        ]

    def _add_constraint(self, constraint: DimensionConstraint) -> None:
        require(
            len(self.constraints) < MAX_DIMENSION_CONSTRAINTS,
            "E_LIMIT",
            f"dimensional analysis may generate at most {MAX_DIMENSION_CONSTRAINTS} constraints",
        )
        self.constraints.append(constraint)

    def _segment(self, node: ast.AST) -> str:
        return ast.get_source_segment(self.source, node) or self.source

    def generic_visit(self, node: ast.AST) -> Any:
        raise CalculatorError("E_AST_BLOCK", f"unsupported dimension syntax: {type(node).__name__}")

    def visit_Expression(self, node: ast.Expression) -> DimensionFormula:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> DimensionFormula:
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise CalculatorError("E_AST_BLOCK", "only numeric literals and declared symbols are allowed")
        if isinstance(node.value, int):
            return DimensionFormula()
        lexical = self._segment(node)
        try:
            value = Fraction(_bounded_decimal(lexical))
        except (InvalidOperation, ValueError) as error:
            raise CalculatorError("E_SYNTAX", "numeric literal could not be read exactly") from error
        require(abs(value) <= 10**300, "E_LIMIT", "numeric literal is too large")
        return DimensionFormula()

    def visit_Name(self, node: ast.Name) -> DimensionFormula:
        dimension = self.bindings.get(node.id)
        if dimension is None:
            raise CalculatorError(
                "E_NAME",
                f"unknown dimension symbol: {node.id}",
                {"symbol": node.id},
            )
        return dimension

    def visit_UnaryOp(self, node: ast.UnaryOp) -> DimensionFormula:
        if not isinstance(node.op, (ast.UAdd, ast.USub)):
            raise CalculatorError("E_AST_BLOCK", "unsupported unary operator in dimension expression")
        return self.visit(node.operand)

    def visit_BinOp(self, node: ast.BinOp) -> DimensionFormula:
        if isinstance(node.op, ast.Pow):
            base = self.visit(node.left)
            exponent = self._literal_fraction(node.right)
            require(abs(exponent) <= MAX_DIMENSION_POWER, "E_LIMIT", "dimension power magnitude may not exceed 12")
            return base.scale(exponent)

        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, (ast.Add, ast.Sub)):
            self._add_constraint(
                DimensionConstraint(
                    code="DIMENSION_ADD_MISMATCH",
                    expression=self._segment(node),
                    message="additive terms must have the same dimension",
                    left=left,
                    right=right,
                )
            )
            return left
        if isinstance(node.op, ast.Mult):
            return left + right
        if isinstance(node.op, ast.Div):
            return left - right
        raise CalculatorError("E_AST_BLOCK", "unsupported binary operator in dimension expression")

    def visit_Call(self, node: ast.Call) -> DimensionFormula:
        if not isinstance(node.func, ast.Name) or node.func.id not in _SUPPORTED_FUNCTIONS:
            raise CalculatorError("E_AST_BLOCK", "unsupported function in dimension expression")
        require(not node.keywords and len(node.args) == 1, "E_INPUT", "dimension functions require one positional argument")
        function = node.func.id
        argument = self.visit(node.args[0])
        if function == "abs":
            return argument
        if function == "sqrt":
            return argument.scale(Fraction(1, 2))
        self._add_constraint(
            DimensionConstraint(
                code="DIMENSION_FUNCTION_ARGUMENT",
                expression=self._segment(node),
                message=f"{function} requires a dimensionless argument",
                left=argument,
                right=DimensionFormula(),
                function=function,
            )
        )
        return DimensionFormula()

    def _literal_fraction(self, node: ast.AST) -> Fraction:
        if isinstance(node, ast.Constant) and not isinstance(node.value, bool) and isinstance(node.value, (int, float)):
            if isinstance(node.value, int):
                parsed = Fraction(node.value)
            else:
                try:
                    parsed = Fraction(_bounded_decimal(self._segment(node)))
                except (InvalidOperation, ValueError) as error:
                    raise CalculatorError("E_INPUT", "dimension powers must be exact numeric literals") from error
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            parsed = self._literal_fraction(node.operand)
            if isinstance(node.op, ast.USub):
                parsed = -parsed
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            numerator = self._literal_fraction(node.left)
            denominator = self._literal_fraction(node.right)
            require(denominator != 0, "E_INPUT", "dimension power denominator may not be zero")
            parsed = numerator / denominator
        else:
            raise CalculatorError("E_INPUT", "dimension powers must be constant rational numbers")
        require(
            abs(parsed.numerator) <= MAX_DIMENSION_EXPONENT_PART
            and parsed.denominator <= MAX_DIMENSION_EXPONENT_PART,
            "E_LIMIT",
            "dimension power is too complex; use a simpler rational exponent",
        )
        return parsed
