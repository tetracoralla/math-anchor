from __future__ import annotations

import ast
from fractions import Fraction
from typing import Any

import sympy as sp
from sympy.polys.polyerrors import CoercionFailed, PolynomialError

from ..errors import CalculatorError, require
from ..safe_expression import make_symbols, normalize_expression_source, parse_expression


MAX_ENTRY_AST_NODES = 128
MAX_ENTRY_DEGREE = 8
MAX_ENTRY_TERMS = 32
MAX_INTERMEDIATE_TERMS = 1_024
MAX_TOTAL_SOURCE_CHARS = 16_384
MAX_COEFFICIENT_BITS = 4_096
MAX_WITNESS_CHARS = 4_096
PolynomialShape = set[tuple[int, ...]]


def _bounded_shape(shape: PolynomialShape) -> PolynomialShape:
    require(
        len(shape) <= MAX_ENTRY_TERMS,
        "E_LIMIT",
        f"each structure component may expand to at most {MAX_ENTRY_TERMS} terms",
    )
    if shape:
        require(
            max(sum(powers) for powers in shape) <= MAX_ENTRY_DEGREE,
            "E_LIMIT",
            f"structure component degree may not exceed {MAX_ENTRY_DEGREE}",
        )
    return shape


def _multiply_shapes(left: PolynomialShape, right: PolynomialShape) -> PolynomialShape:
    result: PolynomialShape = set()
    for left_powers in left:
        for right_powers in right:
            result.add(tuple(a + b for a, b in zip(left_powers, right_powers, strict=True)))
            _bounded_shape(result)
    return result


def _power_shape(base: PolynomialShape, exponent: int, variable_count: int) -> PolynomialShape:
    require(exponent >= 0, "E_DOMAIN", "polynomial exponents must be nonnegative integers")
    require(
        exponent <= MAX_ENTRY_DEGREE,
        "E_LIMIT",
        f"structure component degree may not exceed {MAX_ENTRY_DEGREE}",
    )
    result = {(0,) * variable_count}
    factor = base
    remaining = exponent
    while remaining:
        if remaining & 1:
            result = _multiply_shapes(result, factor)
        remaining >>= 1
        if remaining:
            factor = _multiply_shapes(factor, factor)
    return result


class _PolynomialShapeAnalyzer(ast.NodeVisitor):
    """Reject non-polynomial syntax and bound expansion before SymPy work."""

    def __init__(self, coordinates: list[str]) -> None:
        self.coordinates = tuple(coordinates)
        self.node_count = 0

    def visit(self, node: ast.AST) -> PolynomialShape:  # type: ignore[override]
        self.node_count += 1
        require(
            self.node_count <= MAX_ENTRY_AST_NODES,
            "E_LIMIT",
            "structure component is too complex",
        )
        return super().visit(node)

    def generic_visit(self, node: ast.AST) -> PolynomialShape:
        raise CalculatorError(
            "E_AST_BLOCK",
            f"unsupported structure-component syntax: {type(node).__name__}",
        )

    def visit_Expression(self, node: ast.Expression) -> PolynomialShape:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> PolynomialShape:
        require(
            isinstance(node.value, int) and not isinstance(node.value, bool),
            "E_DOMAIN",
            "structure components require integer literals; write rational coefficients as integer division",
        )
        return {(0,) * len(self.coordinates)}

    def visit_Name(self, node: ast.Name) -> PolynomialShape:
        require(
            node.id in self.coordinates,
            "E_DOMAIN",
            f"structure component contains an undeclared coordinate: {node.id}",
        )
        powers = [0] * len(self.coordinates)
        powers[self.coordinates.index(node.id)] = 1
        return {tuple(powers)}

    def visit_Call(self, node: ast.Call) -> PolynomialShape:
        raise CalculatorError(
            "E_DOMAIN",
            "structure components must be polynomials over rational coefficients",
        )

    def visit_UnaryOp(self, node: ast.UnaryOp) -> PolynomialShape:
        require(
            isinstance(node.op, (ast.UAdd, ast.USub)),
            "E_DOMAIN",
            "structure component contains an unsupported unary operator",
        )
        return self.visit(node.operand)

    def visit_BinOp(self, node: ast.BinOp) -> PolynomialShape:
        if isinstance(node.op, (ast.Add, ast.Sub)):
            return _bounded_shape(self.visit(node.left) | self.visit(node.right))
        if isinstance(node.op, ast.Mult):
            return _multiply_shapes(self.visit(node.left), self.visit(node.right))
        if isinstance(node.op, ast.Div):
            if (
                isinstance(node.right, ast.Constant)
                and isinstance(node.right.value, int)
                and not isinstance(node.right.value, bool)
                and node.right.value == 0
            ):
                raise CalculatorError("E_DOMAIN", "polynomial division by zero")
            numerator = self.visit(node.left)
            denominator = self.visit(node.right)
            require(
                denominator == {(0,) * len(self.coordinates)},
                "E_DOMAIN",
                "structure-component division requires a nonzero rational constant",
            )
            return numerator
        if isinstance(node.op, ast.Pow):
            require(
                isinstance(node.right, ast.Constant)
                and isinstance(node.right.value, int)
                and not isinstance(node.right.value, bool),
                "E_DOMAIN",
                "polynomial exponents must be nonnegative integers",
            )
            return _power_shape(
                self.visit(node.left),
                node.right.value,
                len(self.coordinates),
            )
        raise CalculatorError(
            "E_DOMAIN",
            "structure components support only +, -, *, / by a constant, and nonnegative integer powers",
        )


def _preflight_shape(source: str, coordinates: list[str]) -> PolynomialShape:
    try:
        parsed = ast.parse(source, mode="eval")
    except SyntaxError as error:
        raise CalculatorError("E_SYNTAX", f"invalid structure component: {error.msg}") from error
    return _PolynomialShapeAnalyzer(coordinates).visit(parsed)


def _bounded_polynomial(polynomial: sp.Poly) -> sp.Poly:
    terms = polynomial.terms()
    require(
        len(terms) <= MAX_INTERMEDIATE_TERMS,
        "E_LIMIT",
        f"derived component may contain at most {MAX_INTERMEDIATE_TERMS} terms",
    )
    for _, coefficient in terms:
        fraction = Fraction(int(coefficient.p), int(coefficient.q))
        require(
            fraction.numerator.bit_length() <= MAX_COEFFICIENT_BITS
            and fraction.denominator.bit_length() <= MAX_COEFFICIENT_BITS,
            "E_LIMIT",
            "derived component coefficient is too large",
        )
    return polynomial


def _zero(symbols: list[sp.Symbol]) -> sp.Poly:
    return sp.Poly(0, *symbols, domain=sp.QQ)


def _add_product(accumulator: sp.Poly, left: sp.Poly, right: sp.Poly, sign: int = 1) -> sp.Poly:
    product = left * right
    return _bounded_polynomial(accumulator + product if sign == 1 else accumulator - product)


def _polynomial_text(polynomial: sp.Poly) -> str:
    text = sp.sstr(polynomial.as_expr(), order="lex")
    require(
        len(text) <= MAX_WITNESS_CHARS,
        "E_LIMIT",
        "counterexample component is too large to return",
    )
    return text


def _coordinate_names(arguments: dict[str, Any]) -> list[str]:
    values = arguments.get("coordinates")
    require(isinstance(values, list), "E_INPUT", "coordinates must be an array")
    require(all(isinstance(value, str) for value in values), "E_INPUT", "coordinates must contain strings")
    names = [value.strip() for value in values]
    require(len(names) in {2, 4, 6}, "E_DOMAIN", "local almost-complex checks require dimension 2, 4, or 6")
    make_symbols(names)
    return names


def _structure_polynomials(
    arguments: dict[str, Any],
    coordinates: list[str],
    symbols_by_name: dict[str, sp.Symbol],
) -> list[list[sp.Poly]]:
    raw_structure = arguments.get("structure")
    dimension = len(coordinates)
    require(
        isinstance(raw_structure, list) and len(raw_structure) == dimension,
        "E_INPUT",
        "structure must have one row per coordinate",
    )
    require(
        all(isinstance(row, list) and len(row) == dimension for row in raw_structure),
        "E_INPUT",
        "structure must be square with one column per coordinate",
    )
    require(
        all(isinstance(entry, str) for row in raw_structure for entry in row),
        "E_INPUT",
        "structure components must be strings",
    )
    require(
        sum(len(entry) for row in raw_structure for entry in row) <= MAX_TOTAL_SOURCE_CHARS,
        "E_LIMIT",
        f"structure components may contain at most {MAX_TOTAL_SOURCE_CHARS} characters in total",
    )
    symbols = [symbols_by_name[name] for name in coordinates]
    result: list[list[sp.Poly]] = []
    for row in raw_structure:
        parsed_row: list[sp.Poly] = []
        for source in row:
            normalized = normalize_expression_source(source)
            _bounded_shape(_preflight_shape(normalized, coordinates))
            expression = parse_expression(normalized, symbols=symbols_by_name)
            try:
                polynomial = sp.Poly(expression, *symbols, domain=sp.QQ)
            except (CoercionFailed, PolynomialError) as error:
                raise CalculatorError(
                    "E_DOMAIN",
                    "structure components must be polynomials over rational coefficients",
                ) from error
            parsed_row.append(_bounded_polynomial(polynomial))
        result.append(parsed_row)
    return result


def almost_complex_local_check(arguments: dict[str, Any]) -> dict[str, Any]:
    coordinates = _coordinate_names(arguments)
    symbols_by_name = make_symbols(coordinates)
    symbols = [symbols_by_name[name] for name in coordinates]
    structure = _structure_polynomials(arguments, coordinates, symbols_by_name)
    dimension = len(coordinates)

    square_nonzero_count = 0
    square_first: dict[str, str] | None = None
    for row in range(dimension):
        for column in range(dimension):
            component = _zero(symbols)
            for inner in range(dimension):
                component = _add_product(
                    component,
                    structure[row][inner],
                    structure[inner][column],
                )
            if row == column:
                component = _bounded_polynomial(component + 1)
            if not component.is_zero:
                square_nonzero_count += 1
                if square_first is None:
                    square_first = {
                        "row": coordinates[row],
                        "column": coordinates[column],
                        "exact": _polynomial_text(component),
                    }

    derivatives = [
        [
            [_bounded_polynomial(entry.diff(symbol)) for symbol in symbols]
            for entry in row
        ]
        for row in structure
    ]
    nijenhuis_nonzero_count = 0
    nijenhuis_first: dict[str, str] | None = None
    independent_components_checked = 0
    for left in range(dimension):
        for right in range(left + 1, dimension):
            for output in range(dimension):
                independent_components_checked += 1
                component = _zero(symbols)
                for inner in range(dimension):
                    component = _add_product(
                        component,
                        structure[inner][left],
                        derivatives[output][right][inner],
                    )
                    component = _add_product(
                        component,
                        structure[inner][right],
                        derivatives[output][left][inner],
                        -1,
                    )
                    component = _add_product(
                        component,
                        structure[output][inner],
                        derivatives[inner][right][left],
                        -1,
                    )
                    component = _add_product(
                        component,
                        structure[output][inner],
                        derivatives[inner][left][right],
                    )
                if not component.is_zero:
                    nijenhuis_nonzero_count += 1
                    if nijenhuis_first is None:
                        nijenhuis_first = {
                            "output": coordinates[output],
                            "left": coordinates[left],
                            "right": coordinates[right],
                            "exact": _polynomial_text(component),
                        }

    square_satisfied = square_nonzero_count == 0
    nijenhuis_vanished = nijenhuis_nonzero_count == 0
    if not square_satisfied:
        local_conclusion = "not_almost_complex"
    elif not nijenhuis_vanished:
        local_conclusion = "almost_complex_nonintegrable_on_supplied_chart"
    else:
        local_conclusion = "integrability_conditions_satisfied_on_supplied_chart"

    return {
        "status": "ok",
        "operation": "geometry.almost_complex.local_check",
        "kind": "local_almost_complex_check",
        "coordinates": coordinates,
        "dimension": dimension,
        "matrixConvention": "row_output_column_input",
        "frame": "commuting_coordinate_basis",
        "nijenhuisConvention": "standard_unscaled_bracket",
        "coefficientDomain": "rational_polynomials",
        "square": {
            "satisfied": square_satisfied,
            "nonzeroComponentCount": square_nonzero_count,
            "firstNonzero": square_first,
        },
        "nijenhuis": {
            "vanished": nijenhuis_vanished,
            "independentComponentsChecked": independent_components_checked,
            "nonzeroComponentCount": nijenhuis_nonzero_count,
            "firstNonzero": nijenhuis_first,
        },
        "localConclusion": local_conclusion,
        "uncheckedGlobalObligations": [
            "chart_domain_and_coverage",
            "overlap_compatibility",
            "global_smooth_extension",
            "global_topological_and_analytic_existence",
        ],
        "assumptions": [
            "The declared coordinates define a commuting local frame.",
            "Every supplied component is interpreted as a rational polynomial in those coordinates.",
        ],
        "warnings": [
            "This checks only the supplied local formulas and does not establish a global complex structure."
        ],
    }
