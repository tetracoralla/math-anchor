from __future__ import annotations

from decimal import Decimal, InvalidOperation
import heapq
from typing import Any

import mpmath as mp
import numpy as np
import sympy as sp

from ..errors import CalculatorError, require
from ..safe_expression import make_symbols, parse_expression
from ..validation import integer_arg, list_arg, string_arg


def integrate(arguments: dict[str, Any]) -> dict[str, Any]:
    expression_text = string_arg(arguments, "expression")
    variable_name = string_arg(arguments, "variable", max_length=64)
    lower_text = string_arg(arguments, "lower", max_length=256)
    upper_text = string_arg(arguments, "upper", max_length=256)
    absolute_tolerance_text = string_arg(arguments, "absoluteTolerance", default="1e-12", max_length=64)
    relative_tolerance_text = string_arg(arguments, "relativeTolerance", default="1e-12", max_length=64)
    precision = integer_arg(arguments, "precision", default=30, minimum=16, maximum=100)
    max_evaluations = integer_arg(arguments, "maxEvaluations", default=100_000, minimum=5, maximum=1_000_000)
    raw_breakpoints = arguments.get("breakpoints", [])
    require(isinstance(raw_breakpoints, list), "E_INPUT", "breakpoints must be an array")
    require(len(raw_breakpoints) <= 64, "E_LIMIT", "breakpoints may contain at most 64 points")
    feature_scale_text = arguments.get("featureScale")
    if feature_scale_text is not None:
        require(isinstance(feature_scale_text, str), "E_INPUT", "featureScale must be decimal text")
    symbols = make_symbols([variable_name])
    expression = parse_expression(expression_text, symbols=symbols)
    function = sp.lambdify(symbols[variable_name], expression, modules="mpmath")

    with mp.workdps(precision + 12):
        try:
            lower = mp.mpf(lower_text)
            upper = mp.mpf(upper_text)
            absolute_tolerance = mp.mpf(absolute_tolerance_text)
            relative_tolerance = mp.mpf(relative_tolerance_text)
        except (TypeError, ValueError) as error:
            raise CalculatorError("E_INPUT", "integration bounds and tolerances must be decimal text") from error
        require(mp.isfinite(lower) and mp.isfinite(upper), "E_DOMAIN", "integration bounds must be finite")
        require(lower < upper, "E_INPUT", "integration bounds must satisfy lower < upper")
        require(
            mp.isfinite(absolute_tolerance)
            and mp.isfinite(relative_tolerance)
            and absolute_tolerance >= 0
            and relative_tolerance >= 0
            and (absolute_tolerance > 0 or relative_tolerance > 0),
            "E_INPUT",
            "at least one finite integration tolerance must be positive",
        )
        breakpoints = _integration_breakpoints(raw_breakpoints, lower, upper)
        feature_scale = _optional_positive_mpf(feature_scale_text, "featureScale")
        if feature_scale is not None:
            require(
                feature_scale <= upper - lower,
                "E_INPUT",
                "featureScale must not exceed the integration interval width",
            )

        evaluations = 0

        def evaluate(point: mp.mpf) -> mp.mpf:
            nonlocal evaluations
            require(evaluations < max_evaluations, "E_CONVERGENCE", "numerical integration exhausted maxEvaluations")
            evaluations += 1
            try:
                value = function(point)
            except (ArithmeticError, TypeError, ValueError, ZeroDivisionError) as error:
                raise CalculatorError("E_DOMAIN", f"integrand is undefined inside the interval: {error}") from error
            require(mp.isfinite(value) and mp.im(value) == 0, "E_DOMAIN", "integrand must remain finite and real throughout the interval")
            return mp.re(value)

        boundaries = [lower, *breakpoints, upper]
        region_count = len(boundaries) - 1
        max_probe_segments = (max_evaluations - region_count) // 4
        require(
            max_probe_segments >= region_count,
            "E_LIMIT",
            "maxEvaluations is too small for the supplied integration breakpoints",
        )
        segment_counts = _probe_segment_counts(
            boundaries,
            maximum=max_probe_segments,
            feature_scale=feature_scale,
        )
        probe_segments = sum(segment_counts)
        initial_segments = _initial_segments_for_boundaries(boundaries, segment_counts, evaluate)
        counter = 0
        heap: list[tuple[mp.mpf, int, _IntegrationSegment]] = []
        total = mp.fsum(segment.estimate for segment in initial_segments)
        total_error = mp.fsum(segment.error for segment in initial_segments)
        for segment in initial_segments:
            heapq.heappush(heap, (-segment.error, counter, segment))
            counter += 1
        while total_error > absolute_tolerance + relative_tolerance * abs(total):
            if evaluations + 4 > max_evaluations:
                raise CalculatorError(
                    "E_CONVERGENCE",
                    "numerical integration did not reach the requested tolerances within maxEvaluations",
                    {
                        "evaluations": evaluations,
                        "errorEstimate": mp.nstr(total_error, precision),
                        "target": mp.nstr(absolute_tolerance + relative_tolerance * abs(total), precision),
                    },
                )
            _, _, segment = heapq.heappop(heap)
            left, right = _split_segment(segment, evaluate)
            total += left.estimate + right.estimate - segment.estimate
            total_error += left.error + right.error - segment.error
            total_error = max(mp.mpf("0"), total_error)
            for child in (left, right):
                counter += 1
                heapq.heappush(heap, (-child.error, counter, child))

        lower_result = total - total_error
        upper_result = total + total_error
        if total_error == 0:
            digits_from_local_error: int | None = None
        elif total == 0:
            digits_from_local_error = max(0, int(mp.floor(-mp.log10(total_error))))
        else:
            digits_from_local_error = max(0, int(mp.floor(-mp.log10(total_error / abs(total)))))
        if digits_from_local_error is not None:
            digits_from_local_error = min(precision, digits_from_local_error)
        result_digits = (
            precision
            if digits_from_local_error is None
            else max(2, min(precision, digits_from_local_error + 2))
        )
        result_text = mp.nstr(total, result_digits)
        error_text = mp.nstr(total_error, precision)
        interval = [mp.nstr(lower_result, precision), mp.nstr(upper_result, precision)]
        max_probe_spacing = max(
            (region_upper - region_lower) / segment_count
            for region_lower, region_upper, segment_count in zip(
                boundaries[:-1],
                boundaries[1:],
                segment_counts,
                strict=True,
            )
        )
        if feature_scale is not None:
            coverage_status = "caller_supplied_feature_scale"
            coverage_assumption = (
                "caller states that no material feature is narrower than featureScale; "
                "the initial Simpson segment width does not exceed that scale"
            )
        elif breakpoints:
            coverage_status = "caller_supplied_feature_points"
            coverage_assumption = (
                "caller states that breakpoints identify every material discontinuity or localized feature"
            )
        else:
            coverage_status = "unverified"
            coverage_assumption = (
                "no feature scale or feature points were supplied, so global sampling coverage cannot be established"
            )
        coverage_verified = coverage_status != "unverified"

    return {
        "status": "ok" if coverage_verified else "uncertain",
        "operation": "numeric.integrate",
        "kind": "numerical_integral",
        "exact": None,
        "approx": result_text,
        "precision": precision,
        "estimatedDigitsFromLocalError": digits_from_local_error,
        "method": "stratified_adaptive_simpson",
        "converged": coverage_verified,
        "localErrorToleranceMet": True,
        "convergenceBasis": (
            "requested tolerance met by the local Simpson estimate under the caller-supplied coverage assumption"
            if coverage_verified
            else "local Simpson tolerance met, but interval coverage is unverified"
        ),
        "coverageStatus": coverage_status,
        "coverageAssumption": coverage_assumption,
        "evaluations": evaluations,
        "probeSegments": probe_segments,
        "maxProbeSpacing": mp.nstr(max_probe_spacing, precision),
        "breakpoints": [mp.nstr(point, precision) for point in breakpoints],
        "featureScale": feature_scale_text,
        "absoluteTolerance": absolute_tolerance_text,
        "relativeTolerance": relative_tolerance_text,
        "errorEstimate": error_text,
        "resultInterval": interval,
        "errorBoundCertified": False,
        "warnings": [
            "The interval is formed from a stratified adaptive Simpson error estimate; it is not a rigorous enclosure proof.",
            (
                "Coverage depends on the caller-supplied feature information; estimatedDigitsFromLocalError is not a certified digit count."
                if coverage_verified
                else "Result status is uncertain because features materially narrower than the deterministic probe spacing can be missed."
            ),
        ],
    }


class _IntegrationSegment:
    __slots__ = (
        "lower",
        "middle",
        "upper",
        "f_lower",
        "f_left_middle",
        "f_middle",
        "f_right_middle",
        "f_upper",
        "coarse",
        "estimate",
        "error",
    )

    def __init__(
        self,
        lower: mp.mpf,
        middle: mp.mpf,
        upper: mp.mpf,
        f_lower: mp.mpf,
        f_left_middle: mp.mpf,
        f_middle: mp.mpf,
        f_right_middle: mp.mpf,
        f_upper: mp.mpf,
        coarse: mp.mpf,
        estimate: mp.mpf,
        error: mp.mpf,
    ) -> None:
        self.lower = lower
        self.middle = middle
        self.upper = upper
        self.f_lower = f_lower
        self.f_left_middle = f_left_middle
        self.f_middle = f_middle
        self.f_right_middle = f_right_middle
        self.f_upper = f_upper
        self.coarse = coarse
        self.estimate = estimate
        self.error = error


def _simpson(lower: mp.mpf, upper: mp.mpf, f_lower: mp.mpf, f_middle: mp.mpf, f_upper: mp.mpf) -> mp.mpf:
    return (upper - lower) * (f_lower + 4 * f_middle + f_upper) / 6


def _initial_segments(
    lower: mp.mpf,
    upper: mp.mpf,
    count: int,
    evaluate: Any,
) -> list[_IntegrationSegment]:
    spacing = (upper - lower) / (4 * count)
    points = [lower + spacing * index for index in range(4 * count + 1)]
    values = [evaluate(point) for point in points]
    return [
        _segment_from_samples(
            points[4 * index],
            points[4 * index + 2],
            points[4 * index + 4],
            values[4 * index],
            values[4 * index + 1],
            values[4 * index + 2],
            values[4 * index + 3],
            values[4 * index + 4],
        )
        for index in range(count)
    ]


def _initial_segments_for_boundaries(
    boundaries: list[mp.mpf],
    segment_counts: list[int],
    evaluate: Any,
) -> list[_IntegrationSegment]:
    return [
        segment
        for lower, upper, count in zip(boundaries[:-1], boundaries[1:], segment_counts, strict=True)
        for segment in _initial_segments(lower, upper, count, evaluate)
    ]


def _probe_segment_counts(
    boundaries: list[mp.mpf],
    *,
    maximum: int,
    feature_scale: mp.mpf | None,
) -> list[int]:
    widths = [upper - lower for lower, upper in zip(boundaries[:-1], boundaries[1:], strict=True)]
    if feature_scale is not None:
        counts = [max(1, int(mp.ceil(width / feature_scale))) for width in widths]
        require(
            sum(counts) <= maximum,
            "E_LIMIT",
            "maxEvaluations cannot cover the supplied featureScale across the interval",
        )
        return counts

    total = min(256, maximum)
    require(total >= len(widths), "E_LIMIT", "maxEvaluations is too small for the supplied breakpoints")
    total_width = mp.fsum(widths)
    counts = [1 for _ in widths]
    remaining = total - len(widths)
    if remaining == 0:
        return counts
    exact_additions = [remaining * width / total_width for width in widths]
    additions = [int(mp.floor(value)) for value in exact_additions]
    for index, addition in enumerate(additions):
        counts[index] += addition
    undistributed = remaining - sum(additions)
    priorities = sorted(
        range(len(widths)),
        key=lambda index: exact_additions[index] - additions[index],
        reverse=True,
    )
    for index in priorities[:undistributed]:
        counts[index] += 1
    return counts


def _integration_breakpoints(
    raw_breakpoints: list[Any],
    lower: mp.mpf,
    upper: mp.mpf,
) -> list[mp.mpf]:
    parsed: list[mp.mpf] = []
    for index, raw in enumerate(raw_breakpoints):
        require(isinstance(raw, str), "E_INPUT", f"breakpoints[{index}] must be decimal text")
        try:
            point = mp.mpf(raw)
        except (TypeError, ValueError) as error:
            raise CalculatorError("E_INPUT", f"breakpoints[{index}] must be decimal text") from error
        require(mp.isfinite(point), "E_INPUT", f"breakpoints[{index}] must be finite")
        require(lower < point < upper, "E_INPUT", f"breakpoints[{index}] must lie strictly inside the interval")
        parsed.append(point)
    require(len(set(parsed)) == len(parsed), "E_INPUT", "breakpoints must not contain duplicates")
    return sorted(parsed)


def _optional_positive_mpf(value: str | None, label: str) -> mp.mpf | None:
    if value is None:
        return None
    try:
        parsed = mp.mpf(value)
    except (TypeError, ValueError) as error:
        raise CalculatorError("E_INPUT", f"{label} must be positive decimal text") from error
    require(mp.isfinite(parsed) and parsed > 0, "E_INPUT", f"{label} must be positive decimal text")
    return parsed


def _split_segment(segment: _IntegrationSegment, evaluate: Any) -> tuple[_IntegrationSegment, _IntegrationSegment]:
    left_middle = (segment.lower + segment.middle) / 2
    right_middle = (segment.middle + segment.upper) / 2
    return (
        _make_segment(
            segment.lower,
            left_middle,
            segment.middle,
            segment.f_lower,
            segment.f_left_middle,
            segment.f_middle,
            evaluate,
        ),
        _make_segment(
            segment.middle,
            right_middle,
            segment.upper,
            segment.f_middle,
            segment.f_right_middle,
            segment.f_upper,
            evaluate,
        ),
    )


def _make_segment(
    lower: mp.mpf,
    middle: mp.mpf,
    upper: mp.mpf,
    f_lower: mp.mpf,
    f_middle: mp.mpf,
    f_upper: mp.mpf,
    evaluate: Any,
) -> _IntegrationSegment:
    left_middle = (lower + middle) / 2
    right_middle = (middle + upper) / 2
    f_left_middle = evaluate(left_middle)
    f_right_middle = evaluate(right_middle)
    return _segment_from_samples(
        lower,
        middle,
        upper,
        f_lower,
        f_left_middle,
        f_middle,
        f_right_middle,
        f_upper,
    )


def _segment_from_samples(
    lower: mp.mpf,
    middle: mp.mpf,
    upper: mp.mpf,
    f_lower: mp.mpf,
    f_left_middle: mp.mpf,
    f_middle: mp.mpf,
    f_right_middle: mp.mpf,
    f_upper: mp.mpf,
) -> _IntegrationSegment:
    coarse = _simpson(lower, upper, f_lower, f_middle, f_upper)
    combined = _simpson(lower, middle, f_lower, f_left_middle, f_middle) + _simpson(
        middle,
        upper,
        f_middle,
        f_right_middle,
        f_upper,
    )
    delta = combined - coarse
    return _IntegrationSegment(
        lower,
        middle,
        upper,
        f_lower,
        f_left_middle,
        f_middle,
        f_right_middle,
        f_upper,
        coarse,
        combined + delta / 15,
        abs(delta) / 15,
    )


def solve_approximate_linear_system(arguments: dict[str, Any]) -> dict[str, Any]:
    raw_matrix = list_arg(arguments, "matrix", maximum=100)
    raw_constants = list_arg(arguments, "constants", maximum=100)
    require(all(isinstance(row, list) and row for row in raw_matrix), "E_INPUT", "matrix rows must be non-empty arrays")
    width = len(raw_matrix[0])
    require(width <= 100, "E_LIMIT", "matrix may contain at most 100 columns")
    require(all(len(row) == width for row in raw_matrix), "E_INPUT", "matrix rows must have equal length")
    require(len(raw_matrix) == width, "E_INPUT", "approximate solve currently requires a square matrix")
    require(len(raw_constants) == len(raw_matrix), "E_INPUT", "constants length must match matrix row count")
    tolerance_text = string_arg(arguments, "tolerance", default="1e-12", max_length=64)
    tolerance = _positive_float(tolerance_text, "tolerance")
    precision = integer_arg(arguments, "precision", default=15, minimum=2, maximum=15)

    matrix = np.asarray(
        [[_binary64(value, f"matrix[{row_index}][{column_index}]") for column_index, value in enumerate(row)] for row_index, row in enumerate(raw_matrix)],
        dtype=np.float64,
    )
    constants = np.asarray(
        [_binary64(value, f"constants[{index}]") for index, value in enumerate(raw_constants)],
        dtype=np.float64,
    )
    require(bool(np.all(np.isfinite(matrix))) and bool(np.all(np.isfinite(constants))), "E_DOMAIN", "matrix and constants must be finite")

    norm_a = float(np.linalg.norm(matrix, ord=np.inf))
    rank_tolerance = tolerance * max(1.0, norm_a)
    try:
        rank = int(np.linalg.matrix_rank(matrix, tol=rank_tolerance))
        condition = float(np.linalg.cond(matrix, p=np.inf))
    except np.linalg.LinAlgError as error:
        raise CalculatorError("E_DOMAIN", f"matrix stability analysis failed: {error}") from error
    warnings = [
        "Decimal text is converted to IEEE 754 binary64 for this approximate solve; no exact solution is claimed."
    ]
    if rank < width or not np.isfinite(condition):
        warnings.append("The matrix is singular at the supplied tolerance; a unique solution is not available.")
        return {
            "status": "ok",
            "operation": "matrix.solve_approximate",
            "kind": "approximate_linear_system",
            "classification": "singular",
            "solution": None,
            "rank": rank,
            "conditionNumber": "inf" if not np.isfinite(condition) else _format_diagnostic_float(condition, precision),
            "residualNorm": None,
            "backwardError": None,
            "relativeForwardErrorBound": None,
            "tolerance": tolerance_text,
            "precision": precision,
            "numericFormat": "binary64",
            "diagnosticNorm": "infinity",
            "warnings": warnings,
        }

    try:
        solution = np.linalg.solve(matrix, constants)
    except np.linalg.LinAlgError as error:
        raise CalculatorError("E_DOMAIN", f"approximate linear solve failed: {error}") from error
    require(bool(np.all(np.isfinite(solution))), "E_DOMAIN", "approximate solution overflowed binary64")
    with np.errstate(over="ignore", invalid="ignore"):
        residual_vector = matrix @ solution - constants
    require(bool(np.all(np.isfinite(residual_vector))), "E_DOMAIN", "residual overflowed binary64")
    residual_norm = float(np.linalg.norm(residual_vector, ord=np.inf))
    norm_x = float(np.linalg.norm(solution, ord=np.inf))
    norm_b = float(np.linalg.norm(constants, ord=np.inf))
    denominator = norm_a * norm_x + norm_b
    backward_error = residual_norm / denominator if denominator else residual_norm
    condition_product = condition * backward_error
    relative_forward_bound = (
        condition_product / (1.0 - condition_product)
        if condition_product < 1.0
        else None
    )
    epsilon_amplification = condition * np.finfo(np.float64).eps
    if epsilon_amplification > tolerance:
        classification = "ill_conditioned"
        warnings.append("The estimated amplification of binary64 rounding exceeds the requested tolerance.")
    else:
        classification = "stable_for_tolerance"
    if relative_forward_bound is None:
        warnings.append("The residual does not yield a finite relative forward-error bound at this condition number.")

    return {
        "status": "ok",
        "operation": "matrix.solve_approximate",
        "kind": "approximate_linear_system",
        "classification": classification,
        "solution": [{"exact": None, "approx": _format_float(value, precision)} for value in solution],
        "rank": rank,
        "conditionNumber": _format_diagnostic_float(condition, precision),
        "residualNorm": _format_diagnostic_float(residual_norm, precision),
        "backwardError": _format_diagnostic_float(backward_error, precision),
        "relativeForwardErrorBound": (
            _format_diagnostic_float(relative_forward_bound, precision)
            if relative_forward_bound is not None
            else None
        ),
        "tolerance": tolerance_text,
        "precision": precision,
        "numericFormat": "binary64",
        "diagnosticNorm": "infinity",
        "warnings": warnings,
    }


def _binary64(value: Any, label: str) -> float:
    require(isinstance(value, str), "E_INPUT", f"{label} must be decimal text")
    try:
        decimal = Decimal(value)
    except InvalidOperation as error:
        raise CalculatorError("E_INPUT", f"{label} must be decimal text") from error
    require(decimal.is_finite(), "E_DOMAIN", f"{label} must be finite")
    try:
        converted = float(decimal)
    except (OverflowError, ValueError) as error:
        raise CalculatorError("E_DOMAIN", f"{label} is outside binary64 range") from error
    require(np.isfinite(converted), "E_DOMAIN", f"{label} is outside binary64 range")
    return converted


def _positive_float(text: str, label: str) -> float:
    try:
        value = float(Decimal(text))
    except (InvalidOperation, OverflowError, ValueError) as error:
        raise CalculatorError("E_INPUT", f"{label} must be positive decimal text") from error
    require(np.isfinite(value) and value > 0, "E_INPUT", f"{label} must be positive and finite")
    return value


def _format_float(value: float, precision: int) -> str:
    return np.format_float_positional(float(value), precision=precision, unique=False, trim="-")


def _format_diagnostic_float(value: float, precision: int) -> str:
    if value == 0:
        return "0"
    return format(float(value), f".{precision}g")
