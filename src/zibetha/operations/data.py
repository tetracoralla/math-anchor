from __future__ import annotations

from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Any

import numpy as np
import pint
import sympy as sp

from ..errors import CalculatorError, require
from ..formatting import effective_precision, value_result
from ..validation import enum_arg, integer_arg, list_arg, string_arg


_EXACT_UNIT_REGISTRY = pint.UnitRegistry(
    autoconvert_offset_to_baseunit=True,
    non_int_type=Fraction,
)
_FLOAT_UNIT_REGISTRY = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)


def statistics_describe(arguments: dict[str, Any]) -> dict[str, Any]:
    values = list_arg(arguments, "values", maximum=100_000)
    precision = integer_arg(arguments, "precision", default=16, minimum=2, maximum=200)
    ddof = integer_arg(arguments, "ddof", default=0, minimum=0, maximum=max(0, len(values) - 1))
    quartile_method = enum_arg(arguments, "quartileMethod", ("linear",), default="linear")
    exact_values = [_exact_fraction(value) for value in values]
    warnings: list[str] = []

    if all(value is not None for value in exact_values):
        metrics = _exact_statistics(
            [value for value in exact_values if value is not None],
            ddof=ddof,
        )
        reported_precision = precision
    else:
        array = np.asarray([float(value) for value in values], dtype=float)
        require(bool(np.all(np.isfinite(array))), "E_DOMAIN", "values must be finite")
        with np.errstate(over="ignore", invalid="ignore"):
            numeric_metrics = {
                "mean": float(np.mean(array)),
                "median": float(np.median(array)),
                "standardDeviation": float(np.std(array, ddof=ddof)),
                "minimum": float(np.min(array)),
                "maximum": float(np.max(array)),
                "range": float(np.max(array) - np.min(array)),
                "q1": float(np.percentile(array, 25, method=quartile_method)),
                "q3": float(np.percentile(array, 75, method=quartile_method)),
            }
        require(
            all(np.isfinite(value) for value in numeric_metrics.values()),
            "E_DOMAIN",
            "statistics overflowed the supported floating-point range",
        )
        metrics = {name: sp.Float(str(value), 15) for name, value in numeric_metrics.items()}
        reported_precision = effective_precision(list(metrics.values()), precision)
        warnings.append(
            "JSON floating-point inputs are approximate; send decimal strings to preserve exact decimal provenance."
        )

    return {
        "status": "ok",
        "operation": "statistics.describe",
        "kind": "statistics",
        "count": len(values),
        "mean": value_result(metrics["mean"], reported_precision),
        "median": value_result(metrics["median"], reported_precision),
        "standardDeviation": value_result(metrics["standardDeviation"], reported_precision),
        "minimum": value_result(metrics["minimum"], reported_precision),
        "maximum": value_result(metrics["maximum"], reported_precision),
        "range": value_result(metrics["range"], reported_precision),
        "quartiles": {
            "method": quartile_method,
            "q1": value_result(metrics["q1"], reported_precision),
            "q3": value_result(metrics["q3"], reported_precision),
        },
        "precision": reported_precision,
        "ddof": ddof,
        "warnings": warnings,
    }


def units_convert(arguments: dict[str, Any]) -> dict[str, Any]:
    value = arguments.get("value")
    require(
        isinstance(value, (int, float, str)) and not isinstance(value, bool),
        "E_INPUT",
        "value must be a number or decimal string",
    )
    from_unit = string_arg(arguments, "fromUnit", max_length=128)
    to_unit = string_arg(arguments, "toUnit", max_length=128)
    precision = integer_arg(arguments, "precision", default=16, minimum=2, maximum=200)
    warnings: list[str] = []
    exact_source = isinstance(value, (int, str))
    try:
        registry: pint.UnitRegistry
        source_value: Fraction | float
        if exact_source:
            registry = _EXACT_UNIT_REGISTRY
            source_value = Fraction(Decimal(str(value)))
        else:
            registry = _FLOAT_UNIT_REGISTRY
            source_value = float(value)
        parsed_from = registry.parse_units(from_unit)
        parsed_to = registry.parse_units(to_unit)
        converted = registry.Quantity(source_value, parsed_from).to(parsed_to)
    except TypeError:
        exact_source = False
        warnings.append("This unit conversion uses an approximate floating-point conversion factor.")
        try:
            registry = _FLOAT_UNIT_REGISTRY
            converted = registry.Quantity(float(value), registry.parse_units(from_unit)).to(
                registry.parse_units(to_unit)
            )
        except (pint.PintError, TypeError, ValueError) as error:
            raise CalculatorError("E_UNIT", f"unit conversion failed: {error}") from error
    except (InvalidOperation, pint.PintError, ValueError) as error:
        raise CalculatorError("E_UNIT", f"unit conversion failed: {error}") from error

    exact_conversion = (
        exact_source
        and isinstance(converted.magnitude, Fraction)
        and _unit_path_is_rational(registry, parsed_from)
        and _unit_path_is_rational(registry, parsed_to)
    )
    if exact_conversion:
        result_value = _sympy_fraction(converted.magnitude)
        reported_precision = precision
    else:
        if isinstance(converted.magnitude, Fraction):
            result_value = sp.N(_sympy_fraction(converted.magnitude), 15)
        else:
            result_value = sp.Float(str(converted.magnitude), 15)
        reported_precision = effective_precision([result_value], precision)
        if not warnings:
            if exact_source:
                warnings.append("This unit conversion uses an irrational or approximate conversion factor.")
            else:
                warnings.append(
                    "JSON floating-point input is approximate; send the value as decimal text for exact decimal provenance."
                )
    formatted = value_result(result_value, reported_precision)
    # Pint's Fraction-backed registry also stores integral unit exponents as
    # Fractions, which its compact formatter cannot render for squared/cubed
    # units. Reparse only the already-validated target unit in a conventional
    # registry for its human-facing compact symbol.
    display_unit = f"{_FLOAT_UNIT_REGISTRY.parse_units(to_unit):~}"
    return {
        "status": "ok",
        "operation": "units.convert",
        "kind": "quantity",
        "exact": formatted["exact"],
        "approx": formatted["approx"],
        "precision": reported_precision,
        "unit": display_unit,
        "from": {"value": value, "unit": from_unit},
        "warnings": warnings,
    }


def _exact_fraction(value: Any) -> Fraction | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, str):
        try:
            return Fraction(Decimal(value))
        except InvalidOperation:
            return None
    return None


def _unit_path_is_rational(
    registry: pint.UnitRegistry,
    units: pint.Unit,
) -> bool:
    pending = list(units._units)
    visited: set[str] = set()
    while pending:
        name = pending.pop()
        if name in visited or name.startswith("["):
            continue
        visited.add(name)
        definition = registry._units.get(name)
        if definition is None:
            return False
        if name in {"π", "pi"} or "π" in (getattr(definition, "raw", "") or ""):
            return False
        if type(definition.converter).__name__ not in {"ScaleConverter", "OffsetConverter"}:
            return False
        pending.extend(str(reference) for reference in definition.reference)
    return True


def _sympy_fraction(value: Fraction) -> sp.Rational:
    return sp.Rational(value.numerator, value.denominator)


def _linear_quartile(sorted_values: list[Fraction], numerator: int) -> Fraction:
    position = Fraction((len(sorted_values) - 1) * numerator, 4)
    lower = position.numerator // position.denominator
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * weight


def _exact_statistics(values: list[Fraction], *, ddof: int) -> dict[str, sp.Expr]:
    ordered = sorted(values)
    count = len(values)
    mean = sum(values, Fraction()) / count
    if count % 2:
        median = ordered[count // 2]
    else:
        median = (ordered[count // 2 - 1] + ordered[count // 2]) / 2
    variance = sum((value - mean) ** 2 for value in values) / (count - ddof)
    return {
        "mean": _sympy_fraction(mean),
        "median": _sympy_fraction(median),
        "standardDeviation": sp.sqrt(_sympy_fraction(variance)),
        "minimum": _sympy_fraction(ordered[0]),
        "maximum": _sympy_fraction(ordered[-1]),
        "range": _sympy_fraction(ordered[-1] - ordered[0]),
        "q1": _sympy_fraction(_linear_quartile(ordered, 1)),
        "q3": _sympy_fraction(_linear_quartile(ordered, 3)),
    }
