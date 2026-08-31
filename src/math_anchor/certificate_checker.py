from __future__ import annotations

import ast
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
import re
from typing import Any


CERTIFICATE_FORMAT = "math-anchor.polynomial-identity.v1"
CHECKER_SYSTEM = "math-anchor-stdlib-polynomial-checker"
CHECKER_VERSION = "1.0.0"
MAX_CERTIFICATE_TERMS = 512
MAX_POLYNOMIAL_DEGREE = 64
MAX_AST_NODES = 1_024
MAX_COEFFICIENT_BITS = 16_384
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_VARIABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
Polynomial = dict[tuple[int, ...], Fraction]


class CertificateValidationError(ValueError):
    pass


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return f"sha256:{sha256(_canonical_json(value)).hexdigest()}"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CertificateValidationError(message)


def _bounded_fraction(value: Fraction) -> Fraction:
    _require(
        value.numerator.bit_length() <= MAX_COEFFICIENT_BITS
        and value.denominator.bit_length() <= MAX_COEFFICIENT_BITS,
        "certificate coefficient exceeds the checker limit",
    )
    return value


def _normalize(polynomial: Polynomial) -> Polynomial:
    normalized = {
        powers: _bounded_fraction(coefficient)
        for powers, coefficient in polynomial.items()
        if coefficient
    }
    _require(len(normalized) <= MAX_CERTIFICATE_TERMS, "polynomial exceeds the checker term limit")
    if normalized:
        _require(
            max(sum(powers) for powers in normalized) <= MAX_POLYNOMIAL_DEGREE,
            "polynomial exceeds the checker degree limit",
        )
    return normalized


def _add(left: Polynomial, right: Polynomial, scale: int = 1) -> Polynomial:
    result = dict(left)
    for powers, coefficient in right.items():
        result[powers] = result.get(powers, Fraction(0)) + scale * coefficient
    return _normalize(result)


def _multiply(left: Polynomial, right: Polynomial) -> Polynomial:
    result: Polynomial = {}
    for left_powers, left_coefficient in left.items():
        for right_powers, right_coefficient in right.items():
            powers = tuple(a + b for a, b in zip(left_powers, right_powers, strict=True))
            result[powers] = result.get(powers, Fraction(0)) + left_coefficient * right_coefficient
    return _normalize(result)


def _power(base: Polynomial, exponent: int, variable_count: int) -> Polynomial:
    _require(0 <= exponent <= MAX_POLYNOMIAL_DEGREE, "polynomial exponent is outside the checker limit")
    result: Polynomial = {(0,) * variable_count: Fraction(1)}
    factor = base
    remaining = exponent
    while remaining:
        if remaining & 1:
            result = _multiply(result, factor)
        remaining >>= 1
        if remaining:
            factor = _multiply(factor, factor)
    return result


@dataclass
class _PolynomialParser:
    variables: tuple[str, ...]
    nodes: int = 0

    def parse(self, source: str) -> Polynomial:
        _require(isinstance(source, str) and len(source) <= 4096, "invalid certificate expression")
        try:
            tree = ast.parse(source, mode="eval")
        except SyntaxError as error:
            raise CertificateValidationError("certificate expression has invalid syntax") from error
        return self._visit(tree.body)

    def _visit(self, node: ast.AST) -> Polynomial:
        self.nodes += 1
        _require(self.nodes <= MAX_AST_NODES, "certificate expression exceeds the AST limit")
        zero = (0,) * len(self.variables)
        if isinstance(node, ast.Constant):
            _require(isinstance(node.value, int) and not isinstance(node.value, bool), "only integer literals are allowed")
            return {zero: Fraction(node.value)} if node.value else {}
        if isinstance(node, ast.Name):
            _require(node.id in self.variables, f"unknown certificate variable: {node.id}")
            powers = [0] * len(self.variables)
            powers[self.variables.index(node.id)] = 1
            return {tuple(powers): Fraction(1)}
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = self._visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else {powers: -coefficient for powers, coefficient in value.items()}
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.Add):
                return _add(self._visit(node.left), self._visit(node.right))
            if isinstance(node.op, ast.Sub):
                return _add(self._visit(node.left), self._visit(node.right), -1)
            if isinstance(node.op, ast.Mult):
                return _multiply(self._visit(node.left), self._visit(node.right))
            if isinstance(node.op, ast.Div):
                numerator = self._visit(node.left)
                denominator = self._visit(node.right)
                _require(set(denominator) == {zero}, "polynomial division requires a nonzero rational constant")
                divisor = denominator[zero]
                _require(divisor != 0, "polynomial division by zero")
                return _normalize({powers: coefficient / divisor for powers, coefficient in numerator.items()})
            if isinstance(node.op, ast.Pow):
                _require(
                    isinstance(node.right, ast.Constant)
                    and isinstance(node.right.value, int)
                    and not isinstance(node.right.value, bool),
                    "polynomial exponents must be nonnegative integers",
                )
                return _power(self._visit(node.left), node.right.value, len(self.variables))
        raise CertificateValidationError(f"unsupported certificate syntax: {type(node).__name__}")


def _fraction_text(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def _canonical_terms(polynomial: Polynomial) -> list[dict[str, Any]]:
    return [
        {"powers": list(powers), "coefficient": _fraction_text(coefficient)}
        for powers, coefficient in sorted(polynomial.items(), reverse=True)
    ]


def verify_polynomial_identity_certificate(certificate: dict[str, Any]) -> dict[str, Any]:
    _require(isinstance(certificate, dict), "certificate must be an object")
    _require(
        set(certificate)
        == {
            "format",
            "statement",
            "statementDigest",
            "identity",
            "normalizedDifference",
            "certificateDigest",
        },
        "certificate fields do not match the v1 format",
    )
    _require(certificate["format"] == CERTIFICATE_FORMAT, "unsupported certificate format")
    statement = certificate["statement"]
    _require(isinstance(statement, dict), "certificate statement must be an object")
    _require(set(statement) == {"left", "right", "variables"}, "certificate statement fields are invalid")
    variables = statement["variables"]
    _require(
        isinstance(variables, list)
        and 1 <= len(variables) <= 8
        and all(isinstance(item, str) and _VARIABLE.fullmatch(item) for item in variables)
        and len(set(variables)) == len(variables),
        "certificate variables are invalid",
    )
    _require(
        isinstance(certificate["statementDigest"], str)
        and _DIGEST.fullmatch(certificate["statementDigest"]) is not None
        and certificate["statementDigest"] == _digest(statement),
        "certificate statement digest mismatch",
    )
    digest_payload = dict(certificate)
    certificate_digest = digest_payload.pop("certificateDigest")
    _require(
        isinstance(certificate_digest, str)
        and _DIGEST.fullmatch(certificate_digest) is not None
        and certificate_digest == _digest(digest_payload),
        "certificate digest mismatch",
    )
    _require(isinstance(certificate["identity"], bool), "certificate identity must be a boolean")
    claimed_terms = certificate["normalizedDifference"]
    _require(
        isinstance(claimed_terms, list) and len(claimed_terms) <= MAX_CERTIFICATE_TERMS,
        "certificate term list is invalid",
    )

    parser = _PolynomialParser(tuple(variables))
    left = parser.parse(statement["left"])
    right = parser.parse(statement["right"])
    difference = _add(left, right, -1)
    expected_terms = _canonical_terms(difference)
    _require(claimed_terms == expected_terms, "certificate coefficients do not match the statement")
    identity = not difference
    _require(certificate["identity"] is identity, "certificate identity classification is wrong")
    return {
        "valid": True,
        "identity": identity,
        "certificateDigest": certificate_digest,
        "checker": {"system": CHECKER_SYSTEM, "version": CHECKER_VERSION},
    }
