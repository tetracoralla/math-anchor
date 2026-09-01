from __future__ import annotations

from decimal import Decimal, InvalidOperation
from fractions import Fraction
import threading
from typing import Any

from ..errors import CalculatorError, require
from ..validation import enum_arg, integer_arg, list_arg, string_arg
from . import units


# Constructing a pint registry parses the complete unit definition file
# (~150 ms each). Building them lazily keeps worker, app, and MCP cold start
# free of that cost until a unit operation actually needs a registry.
_EXACT_UNIT_REGISTRY: Any | None = None
_FLOAT_UNIT_REGISTRY: Any | None = None
_UNIT_REGISTRY_LOCK = threading.Lock()


def _exact_unit_registry() -> Any:
    import pint

    global _EXACT_UNIT_REGISTRY
    if _EXACT_UNIT_REGISTRY is None:
        with _UNIT_REGISTRY_LOCK:
            if _EXACT_UNIT_REGISTRY is None:
                _EXACT_UNIT_REGISTRY = pint.UnitRegistry(
                    autoconvert_offset_to_baseunit=True,
                    non_int_type=Fraction,
                )
    return _EXACT_UNIT_REGISTRY


def _float_unit_registry() -> Any:
    import pint

    global _FLOAT_UNIT_REGISTRY
    if _FLOAT_UNIT_REGISTRY is None:
        with _UNIT_REGISTRY_LOCK:
            if _FLOAT_UNIT_REGISTRY is None:
                _FLOAT_UNIT_REGISTRY = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)
    return _FLOAT_UNIT_REGISTRY


def warm_unit_registries() -> None:
    """Build both lazy registries outside an interactive request budget."""
    _exact_unit_registry()
    _float_unit_registry()


def statistics_describe(arguments: dict[str, Any]) -> dict[str, Any]:
    import sympy as sp

    from ..formatting import effective_precision, value_result

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
        used_backends = ["sympy"]
    else:
        import numpy as np

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
        used_backends = ["numpy", "sympy"]
        warnings.append(
            "JSON floating-point inputs are approximate; send decimal strings to preserve exact decimal provenance."
        )

    return {
        "_usedBackends": used_backends,
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
    import pint
    import sympy as sp
    from pint.util import UnitsContainer

    from ..formatting import effective_precision, value_result

    value = arguments.get("value")
    require(
        isinstance(value, (int, float, str)) and not isinstance(value, bool),
        "E_INPUT",
        "value must be a number or decimal string",
    )
    from_unit = string_arg(arguments, "fromUnit", max_length=128)
    to_unit = string_arg(arguments, "toUnit", max_length=128)
    calendar_policy = enum_arg(
        arguments,
        "calendarPolicy",
        units.CALENDAR_POLICIES,
        default="reject",
    )
    precision = integer_arg(arguments, "precision", default=16, minimum=2, maximum=200)
    warnings: list[str] = []
    exact_source = isinstance(value, (int, str))
    resolved_from = units.resolve_unit_text(from_unit)
    resolved_to = units.resolve_unit_text(to_unit)
    uses_calendar_average = False
    try:
        registry: Any
        source_value: Fraction | float
        if exact_source:
            registry = _exact_unit_registry()
            source_value = Fraction(Decimal(str(value)))
        else:
            registry = _float_unit_registry()
            source_value = float(value)
        parsed_from = registry.parse_units(resolved_from)
        parsed_to = registry.parse_units(resolved_to)
        uses_calendar_average = units.require_calendar_policy(
            units.calendar_unit_names(parsed_from) | units.calendar_unit_names(parsed_to),
            calendar_policy,
        )
        converted = registry.Quantity(source_value, parsed_from).to(parsed_to)
    except TypeError:
        exact_source = False
        warnings.append("This unit conversion uses an approximate floating-point conversion factor.")
        try:
            registry = _float_unit_registry()
            parsed_from = registry.parse_units(resolved_from)
            parsed_to = registry.parse_units(resolved_to)
            uses_calendar_average = units.require_calendar_policy(
                units.calendar_unit_names(parsed_from) | units.calendar_unit_names(parsed_to),
                calendar_policy,
            )
            converted = registry.Quantity(float(value), parsed_from).to(parsed_to)
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
    if uses_calendar_average:
        warnings.insert(0, units.CALENDAR_AVERAGE_WARNING)
    display_registry = registry if exact_conversion else _float_unit_registry()
    display_units = UnitsContainer(
        {
            name: int(exponent)
            if isinstance(exponent, Fraction) and exponent.denominator == 1
            else float(exponent)
            for name, exponent in parsed_to._units.items()
        }
    )
    display_unit = f"{display_registry.Unit(display_units):~}"
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
    registry: Any,
    units: Any,
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


def _sympy_fraction(value: Fraction) -> Any:
    import sympy as sp

    return sp.Rational(value.numerator, value.denominator)


def _linear_quartile(sorted_values: list[Fraction], numerator: int) -> Fraction:
    position = Fraction((len(sorted_values) - 1) * numerator, 4)
    lower = position.numerator // position.denominator
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * weight


def _exact_statistics(values: list[Fraction], *, ddof: int) -> dict[str, Any]:
    import sympy as sp

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
