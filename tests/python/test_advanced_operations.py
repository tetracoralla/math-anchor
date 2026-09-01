from __future__ import annotations

from decimal import Decimal

import pytest

from math_anchor.errors import CalculatorError
from math_anchor.runtime import execute_direct


def test_expression_equivalence_proves_identity_and_preserves_definedness() -> None:
    identity = execute_direct(
        "expression.equivalent",
        {
            "left": "sin(x)^2 + cos(x)^2",
            "right": "1",
            "variables": ["x"],
            "domain": "real",
        },
    )
    assert identity["equivalence"] == "equivalent"
    assert identity["proven"] is True
    assert identity["definedness"] == "same"

    removable_discontinuity = execute_direct(
        "expression.equivalent",
        {
            "left": "(x^2 - 1)/(x - 1)",
            "right": "x + 1",
            "variables": ["x"],
            "domain": "real",
        },
    )
    assert removable_discontinuity["difference"]["exact"] == "0"
    assert removable_discontinuity["equivalence"] == "not_equivalent"
    assert removable_discontinuity["definedness"] == "different"

    common_domain = execute_direct(
        "expression.equivalent",
        {
            "left": "(x^2 - 1)/(x - 1)",
            "right": "x + 1",
            "variables": ["x"],
            "definednessPolicy": "common_domain",
        },
    )
    assert common_domain["equivalence"] == "equivalent"

    cancelled_identity = execute_direct(
        "expression.equivalent",
        {"left": "sin(x)/sin(x)", "right": "1", "variables": ["x"]},
    )
    assert cancelled_identity["equivalence"] == "not_equivalent"
    assert cancelled_identity["definedness"] == "different"

    common_domain_difference = execute_direct(
        "expression.equivalent",
        {
            "left": "sin(x)/sin(x)",
            "right": "0",
            "variables": ["x"],
            "definednessPolicy": "common_domain",
        },
    )
    assert common_domain_difference["counterexample"]["values"]["x"]["exact"] != "0"

    cancelled_root_domain = execute_direct(
        "expression.equivalent",
        {"left": "sqrt(x)^2", "right": "x", "variables": ["x"]},
    )
    assert cancelled_root_domain["equivalence"] == "not_equivalent"
    assert cancelled_root_domain["leftDomain"] == "Interval(0, oo)"


def test_expression_equivalence_returns_a_reproducible_counterexample() -> None:
    result = execute_direct(
        "expression.equivalent",
        {"left": "x^2", "right": "x", "variables": ["x"]},
    )
    assert result["equivalence"] == "not_equivalent"
    assert result["counterexample"] is not None
    assert result["counterexample"]["left"] != result["counterexample"]["right"]


def test_solution_verification_reports_residuals_and_omission_risk() -> None:
    complete = execute_direct(
        "solution.verify",
        {
            "constraints": "x^2 = 2",
            "variables": ["x"],
            "candidates": [{"x": "sqrt(2)"}, {"x": "-sqrt(2)"}],
            "checkCompleteness": True,
        },
    )
    assert complete["allValid"] is True
    assert complete["completeness"] == "complete"
    assert complete["omissionRisk"] == "none_proven"
    assert all(row["checks"][0]["residual"]["exact"] == "0" for row in complete["candidates"])

    incomplete = execute_direct(
        "solution.verify",
        {
            "constraints": "x^2 = 2",
            "variables": ["x"],
            "candidates": [{"x": "sqrt(2)"}],
            "checkCompleteness": True,
        },
    )
    assert incomplete["completeness"] == "incomplete"
    assert incomplete["omissionRisk"] == "known_omissions"
    assert incomplete["omittedSolutions"][0]["exact"] == "-sqrt(2)"


def test_solution_verification_handles_system_inequalities_and_failures() -> None:
    result = execute_direct(
        "solution.verify",
        {
            "constraints": ["x + y = 7", "x > y"],
            "variables": ["x", "y"],
            "candidates": [{"x": 4, "y": 3}, {"x": 3, "y": 4}],
        },
    )
    assert result["candidates"][0]["valid"] is True
    assert result["candidates"][1]["valid"] is False
    assert result["omissionRisk"] == "not_assessed"

    with pytest.raises(CalculatorError) as missing:
        execute_direct(
            "solution.verify",
            {"constraints": "x + y = 1", "variables": ["x", "y"], "candidates": [{"x": 1}]},
        )
    assert missing.value.code == "E_INPUT"

    with pytest.raises(CalculatorError) as chained:
        execute_direct(
            "solution.verify",
            {"constraints": "0 < x < 1", "variables": ["x"], "candidates": [{"x": "0.5"}]},
        )
    assert chained.value.code == "E_SYNTAX"

    undefined = execute_direct(
        "solution.verify",
        {"constraints": "1/x = 0", "variables": ["x"], "candidates": [{"x": 0}]},
    )
    assert undefined["candidates"][0]["valid"] is False
    assert undefined["candidates"][0]["checks"][0]["defined"] is False

    with pytest.raises(CalculatorError) as complex_order:
        execute_direct(
            "solution.verify",
            {
                "constraints": "x > 0",
                "variables": ["x"],
                "candidates": [{"x": 1}],
                "domain": "complex",
            },
        )
    assert complex_order.value.code == "E_INPUT"


def test_quantity_expression_is_exact_and_dimension_checked() -> None:
    force = execute_direct(
        "quantity.evaluate",
        {"expression": "80 * kg * 9.81 * m / s^2", "toUnit": "newton"},
    )
    assert force["exact"] == "3924/5"
    assert force["unit"] == "N"
    assert "[mass]" in force["dimensionality"]

    length = execute_direct(
        "quantity.evaluate",
        {"expression": "3 * meter + 25 * centimeter", "toUnit": "meter"},
    )
    assert length["exact"] == "13/4"

    angular = execute_direct(
        "quantity.evaluate",
        {"expression": "1 * degree", "toUnit": "radian"},
    )
    assert angular["exact"] is None
    assert angular["warnings"]

    with pytest.raises(CalculatorError) as incompatible:
        execute_direct("quantity.evaluate", {"expression": "1 * meter + 1 * second"})
    assert incompatible.value.code == "E_UNIT"

    with pytest.raises(CalculatorError) as unsafe:
        execute_direct("quantity.evaluate", {"expression": "__import__(1)"})
    assert unsafe.value.code == "E_AST_BLOCK"

    with pytest.raises(CalculatorError) as exponent:
        execute_direct("quantity.evaluate", {"expression": "meter^13"})
    assert exponent.value.code == "E_LIMIT"


def test_numerical_root_carries_error_bound_and_rejects_discontinuities() -> None:
    root = execute_direct(
        "numeric.root",
        {
            "expression": "x^3 - 2*x - 5",
            "variable": "x",
            "bracket": ["2", "3"],
            "tolerance": "1e-30",
            "precision": 30,
        },
    )
    assert root["kind"] == "numerical_root"
    assert root["method"] == "brent"
    assert Decimal(root["errorBound"]) <= Decimal("1e-30")
    assert Decimal(root["residual"]) < Decimal("1e-25")

    with pytest.raises(CalculatorError) as discontinuity:
        execute_direct(
            "numeric.root",
            {"expression": "1/x", "variable": "x", "bracket": ["-1", "1"]},
        )
    assert discontinuity.value.code == "E_DOMAIN"

    with pytest.raises(CalculatorError) as convergence:
        execute_direct(
            "numeric.root",
            {
                "expression": "x^2 - 2",
                "variable": "x",
                "bracket": ["1", "2"],
                "tolerance": "1e-30",
                "maxIterations": 2,
            },
        )
    assert convergence.value.code == "E_CONVERGENCE"


def test_numerical_integration_exposes_an_honest_estimated_interval() -> None:
    integral = execute_direct(
        "numeric.integrate",
        {
            "expression": "sin(x)",
            "variable": "x",
            "lower": "0",
            "upper": "3.14159265358979323846",
        },
    )
    assert integral["status"] == "uncertain"
    assert integral["converged"] is False
    assert integral["localErrorToleranceMet"] is True
    assert integral["coverageStatus"] == "unverified"
    assert integral["method"] == "stratified_adaptive_clenshaw_curtis"
    assert Decimal(integral["resultInterval"][0]) < Decimal("2") < Decimal(integral["resultInterval"][1])
    assert 10 <= integral["estimatedDigitsFromLocalError"] < integral["precision"]
    assert integral["probeSegments"] == 256
    assert integral["errorBoundCertified"] is False
    assert integral["warnings"]

    narrow_peak = execute_direct(
        "numeric.integrate",
        {
            "expression": "exp(-1000000*(x-0.12345)^2)",
            "variable": "x",
            "lower": "0",
            "upper": "1",
        },
    )
    assert narrow_peak["status"] == "uncertain"
    expected_peak_area = Decimal("0.001772453850905516")
    observed_peak_area = Decimal(narrow_peak["approx"])
    assert abs(observed_peak_area - expected_peak_area) / expected_peak_area < Decimal("1e-8")
    assert narrow_peak["estimatedDigitsFromLocalError"] is not None

    missed_peak = execute_direct(
        "numeric.integrate",
        {
            "expression": "exp(-1000000000000*(x-0.123456789)^2)",
            "variable": "x",
            "lower": "0",
            "upper": "1",
        },
    )
    assert missed_peak["status"] == "uncertain"
    assert missed_peak["converged"] is False
    assert missed_peak["coverageStatus"] == "unverified"

    located_peak = execute_direct(
        "numeric.integrate",
        {
            "expression": "exp(-1000000000000*(x-0.123456789)^2)",
            "variable": "x",
            "lower": "0",
            "upper": "1",
            "breakpoints": ["0.123456789"],
            "absoluteTolerance": "1e-20",
        },
    )
    expected_located_area = Decimal("0.000001772453850905516")
    observed_located_area = Decimal(located_peak["approx"])
    assert located_peak["status"] == "ok"
    assert located_peak["converged"] is True
    assert located_peak["coverageStatus"] == "caller_supplied_feature_points"
    assert abs(observed_located_area - expected_located_area) / expected_located_area < Decimal("1e-8")

    with pytest.raises(CalculatorError) as duplicate_breakpoints:
        execute_direct(
            "numeric.integrate",
            {
                "expression": "sin(x)",
                "variable": "x",
                "lower": "0",
                "upper": "1",
                "breakpoints": ["0.5", "0.5"],
            },
        )
    assert duplicate_breakpoints.value.code == "E_INPUT"

    with pytest.raises(CalculatorError) as uncovered_feature_scale:
        execute_direct(
            "numeric.integrate",
            {
                "expression": "sin(x)",
                "variable": "x",
                "lower": "0",
                "upper": "1",
                "featureScale": "0.000001",
                "maxEvaluations": 1_000,
            },
        )
    assert uncovered_feature_scale.value.code == "E_LIMIT"

    with pytest.raises(CalculatorError) as discontinuity:
        execute_direct(
            "numeric.integrate",
            {"expression": "1/x", "variable": "x", "lower": "-1", "upper": "1"},
        )
    assert discontinuity.value.code == "E_DOMAIN"

    with pytest.raises(CalculatorError) as budget:
        execute_direct(
            "numeric.integrate",
            {
                "expression": "x^4",
                "variable": "x",
                "lower": "0",
                "upper": "1",
                "absoluteTolerance": "1e-30",
                "relativeTolerance": "0",
                "maxEvaluations": 5,
            },
        )
    assert budget.value.code == "E_CONVERGENCE"


def test_approximate_linear_system_exposes_stability_diagnostics() -> None:
    stable = execute_direct(
        "matrix.solve_approximate",
        {"matrix": [["3", "1"], ["1", "2"]], "constants": ["9", "8"]},
    )
    assert stable["classification"] == "stable_for_tolerance"
    assert [item["approx"] for item in stable["solution"]] == ["2", "3"]
    assert Decimal(stable["backwardError"]) == 0
    assert stable["diagnosticNorm"] == "infinity"

    nonzero_residual = execute_direct(
        "matrix.solve_approximate",
        {
            "matrix": [
                ["-0.9891213503478509", "-0.3677866514678832"],
                ["1.2879252612892487", "0.1939744191326132"],
            ],
            "constants": ["0.9202308996398569", "0.5771037912572513"],
        },
    )
    assert Decimal(nonzero_residual["residualNorm"]) > 0
    assert Decimal(nonzero_residual["backwardError"]) > 0

    ill_conditioned = execute_direct(
        "matrix.solve_approximate",
        {"matrix": [["1", "0"], ["0", "0.000001"]], "constants": ["1", "0.000001"]},
    )
    assert ill_conditioned["classification"] == "ill_conditioned"
    assert ill_conditioned["warnings"]

    singular = execute_direct(
        "matrix.solve_approximate",
        {"matrix": [["1", "1"], ["1", "1"]], "constants": ["2", "2"]},
    )
    assert singular["classification"] == "singular"
    assert singular["solution"] is None

    with pytest.raises(CalculatorError) as implicit_binary_float:
        execute_direct(
            "matrix.solve_approximate",
            {"matrix": [[1, "0"], ["0", "1"]], "constants": ["1", "1"]},
        )
    assert implicit_binary_float.value.code == "E_INPUT"


def test_financial_operations_state_timing_rounding_and_root_accuracy() -> None:
    compound = execute_direct(
        "finance.calculate",
        {
            "action": "compound_value",
            "principal": "10000",
            "annualRate": "0.05",
            "periodsPerYear": 12,
            "numberOfPeriods": 120,
        },
    )
    assert compound["results"][0]["approx"] == "16470.09"
    assert compound["rounding"] == {"decimalPlaces": 2, "mode": "half_even"}
    assert len(compound["conventions"]) >= 3

    effective = execute_direct(
        "finance.calculate",
        {
            "action": "effective_annual_rate",
            "nominalAnnualRate": "0.12",
            "compoundsPerYear": 12,
        },
    )
    assert effective["results"][0]["approx"].startswith("0.126825")
    assert "regulatory APR" in effective["conventions"][2]

    loan = execute_direct(
        "finance.calculate",
        {
            "action": "loan_payment",
            "principal": "300000",
            "annualRate": "0.045",
            "paymentsPerYear": 12,
            "numberOfPayments": 360,
        },
    )
    assert loan["results"][0]["approx"] == "1520.06"

    irr = execute_direct(
        "finance.calculate",
        {
            "action": "irr",
            "cashFlows": ["-1000", "400", "400", "400"],
            "lowerRate": "0",
            "upperRate": "1",
            "tolerance": "1e-18",
        },
    )
    assert irr["converged"] is True
    assert Decimal(irr["errorBound"]) <= Decimal("1e-18")
    assert irr["results"][0]["approx"].startswith("0.097010")

    with pytest.raises(CalculatorError) as unbracketed:
        execute_direct(
            "finance.calculate",
            {
                "action": "irr",
                "cashFlows": ["-1000", "400", "400", "400"],
                "lowerRate": "0.5",
                "upperRate": "1",
            },
        )
    assert unbracketed.value.code == "E_DOMAIN"

    with pytest.raises(CalculatorError) as decimal_overflow:
        execute_direct(
            "finance.calculate",
            {
                "action": "compound_value",
                "principal": "1e999999",
                "annualRate": "10",
                "periodsPerYear": 1,
                "numberOfPeriods": 10_000_000,
            },
        )
    assert decimal_overflow.value.code == "E_DOMAIN"


def test_probability_distributions_cover_common_functions_and_domains() -> None:
    normal = execute_direct(
        "probability.distribution",
        {"distribution": "normal", "function": "cdf", "x": "1.96"},
    )
    assert normal["value"]["approx"].startswith("0.975002")

    binomial = execute_direct(
        "probability.distribution",
        {"distribution": "binomial", "function": "cdf", "n": 20, "k": 4, "probability": "0.1"},
    )
    assert binomial["value"]["approx"].startswith("0.956825")

    poisson = execute_direct(
        "probability.distribution",
        {"distribution": "poisson", "function": "cdf", "k": 2, "rate": "3"},
    )
    assert poisson["value"]["approx"].startswith("0.423190")

    degenerate_poisson = execute_direct(
        "probability.distribution",
        {"distribution": "poisson", "function": "cdf", "k": 5, "rate": "0"},
    )
    assert degenerate_poisson["value"]["approx"] == "1.0"

    with pytest.raises(CalculatorError) as invalid_probability:
        execute_direct(
            "probability.distribution",
            {"distribution": "binomial", "function": "pmf", "n": 10, "k": 2, "probability": "1.1"},
        )
    assert invalid_probability.value.code == "E_DOMAIN"


def test_inferential_statistics_report_methods_and_sample_constraints() -> None:
    interval = execute_direct(
        "statistics.infer",
        {"action": "mean_confidence_interval", "sample": ["10", "12", "9", "11", "13"]},
    )
    assert interval["interval"]["lower"]["approx"].startswith("9.0367")
    assert interval["interval"]["degreesOfFreedom"] == 4
    assert interval["method"] == "two_sided_student_t_interval"
    assert interval["assumptions"]

    test = execute_direct(
        "statistics.infer",
        {"action": "one_sample_t_test", "sample": ["10", "12", "9", "11", "13"], "nullMean": "10"},
    )
    assert test["test"]["degreesOfFreedom"] == 4
    assert test["test"]["pValue"]["approx"].startswith("0.230199")

    regression = execute_direct(
        "statistics.infer",
        {"action": "linear_regression", "x": ["1", "2", "3"], "y": ["2", "4.1", "5.9"]},
    )
    estimates = {item["name"]: item["value"]["approx"] for item in regression["estimates"]}
    assert estimates["slope"] == "1.95"
    assert estimates["r_squared"].startswith("0.998031")

    with pytest.raises(CalculatorError) as zero_variation:
        execute_direct(
            "statistics.infer",
            {"action": "one_sample_t_test", "sample": ["1", "1", "1"], "nullMean": "1"},
        )
    assert zero_variation.value.code == "E_DOMAIN"

    with pytest.raises(CalculatorError) as mismatched:
        execute_direct(
            "statistics.infer",
            {"action": "linear_regression", "x": ["1", "2", "3"], "y": ["1", "2", "3", "4"]},
        )
    assert mismatched.value.code == "E_INPUT"


def test_clenshaw_curtis_quadrature_is_self_verified() -> None:
    import mpmath as mp

    from math_anchor.operations.numerical import _clenshaw_curtis

    with mp.workdps(40):
        for degree in (8, 16):
            nodes, weights = _clenshaw_curtis(degree, 30)
            assert abs(mp.fsum(weights) - 2) < mp.mpf("1e-25")
            for power in range(degree + 1):
                observed = mp.fsum(w * x**power for x, w in zip(nodes, weights))
                expected = mp.mpf(2) / (power + 1) if power % 2 == 0 else mp.mpf(0)
                assert abs(observed - expected) < mp.mpf("1e-25")
            assert nodes[0] == 1 and nodes[-1] == -1
        fine_nodes, _ = _clenshaw_curtis(16, 30)
        coarse_nodes, _ = _clenshaw_curtis(8, 30)
        for index in range(9):
            assert abs(fine_nodes[2 * index] - coarse_nodes[index]) < mp.mpf("1e-25")


def test_integration_refinement_keeps_features_that_live_on_a_breakpoint() -> None:
    # Negative regression for the refinement rule: an open-node rule such as
    # Gauss-Legendre is blind to a spike exactly at a caller-supplied
    # breakpoint (both embedded estimates miss the mass and report zero
    # local error), so refinement must use endpoint-including nodes.
    located = execute_direct(
        "numeric.integrate",
        {
            "expression": "exp(-1000000000000*(x-0.123456789)^2)",
            "variable": "x",
            "lower": "0",
            "upper": "1",
            "breakpoints": ["0.123456789"],
            "absoluteTolerance": "1e-20",
        },
    )
    expected = Decimal("0.000001772453850905516")
    observed = Decimal(located["approx"])
    assert abs(observed - expected) / expected < Decimal("1e-8")


def test_numeric_root_brent_keeps_the_rigorous_bound_and_beats_bisection() -> None:
    from math_anchor.operations.calculus import _bracketed_root
    from math_anchor.safe_expression import make_symbols, parse_expression
    import mpmath as mp
    import sympy as sp

    cases = (
        ("x^3 - 2*x - 5", "2", "3", 30, None),
        ("x^5 - x - 1", "1", "2", 45, None),
        ("cos(x) - x", "0", "1", 40, None),
    )
    with mp.workdps(55):
        for expression_text, lower, upper, precision, known in cases:
            symbols = make_symbols(["x"])
            expression = parse_expression(expression_text, symbols=symbols)
            function = sp.lambdify(symbols["x"], expression, modules="mpmath")

            def evaluate(point):
                return function(point)

            if known is not None:
                truth = mp.mpf(str(known))
            else:
                # mpmath's default findroot tolerance is far looser than the
                # solver under test; compute the oracle at guard precision.
                with mp.workdps(90):
                    truth = mp.mpf(mp.findroot(function, ((mp.mpf(lower) + mp.mpf(upper)) / 2, mp.mpf(upper))))
            with mp.workdps(precision + 10):
                result, residual, error_bound, bracket, iterations, _ = _bracketed_root(
                    evaluate, mp.mpf(lower), mp.mpf(upper), mp.mpf(10) ** (-precision), 2000, precision
                )
            assert abs(result - truth) <= error_bound, (expression_text, result, truth, error_bound)
            assert min(bracket) <= truth <= max(bracket)
            # An exact working-precision zero exits with the current honest
            # bracket; every width-converged exit must meet the tolerance.
            if residual != 0:
                assert error_bound <= mp.mpf(10) ** (-precision)

    # The safeguarded interpolation must actually fire: bisection needs
    # ~100 iterations here, a regression to pure bisection exceeds this pin.
    root = execute_direct(
        "numeric.root",
        {
            "expression": "x^3 - 2*x - 5",
            "variable": "x",
            "bracket": ["2", "3"],
            "tolerance": "1e-30",
            "precision": 30,
        },
    )
    assert root["method"] == "brent"
    assert root["iterations"] < 60
    assert Decimal(root["errorBound"]) <= Decimal("1e-30")


def test_numeric_root_find_all_enumerates_sign_changes_honestly() -> None:
    import mpmath as mp

    all_roots = execute_direct(
        "numeric.root",
        {
            "expression": "sin(x)",
            "variable": "x",
            "bracket": ["-10", "10"],
            "findAll": True,
            "resolution": 256,
            "tolerance": "1e-25",
            "precision": 25,
        },
    )
    assert all_roots["findAll"] is True
    assert all_roots["count"] == 7
    assert all_roots["method"] == "brent"
    for entry, multiple in zip(all_roots["roots"], (n for n in range(-3, 4))):
        assert abs(mp.mpf(entry["approx"]) - multiple * mp.pi) < mp.mpf("1e-24")
        assert Decimal(entry["errorBound"]) <= Decimal("1e-25")

    # Even multiplicity has no sign change: it is only found when a grid
    # point lands exactly on the root, never between grid points.
    between_grid = execute_direct(
        "numeric.root",
        {
            "expression": "(x-1)^2",
            "variable": "x",
            "bracket": ["0", "3"],
            "findAll": True,
            "resolution": 64,
        },
    )
    assert between_grid["count"] == 0
    assert between_grid["approx"] is None
    assert any("sign change" in warning for warning in between_grid["warnings"])

    on_grid = execute_direct(
        "numeric.root",
        {
            "expression": "(x-1)^2",
            "variable": "x",
            "bracket": ["0", "2"],
            "findAll": True,
            "resolution": 64,
        },
    )
    assert on_grid["count"] == 1
    assert Decimal(on_grid["roots"][0]["approx"]) == Decimal(1)

    grid_point = execute_direct(
        "numeric.root",
        {
            "expression": "x",
            "variable": "x",
            "bracket": ["-1", "1"],
            "findAll": True,
            "resolution": 64,
        },
    )
    assert grid_point["count"] == 1
    assert Decimal(grid_point["roots"][0]["approx"]) == Decimal(0)

    with pytest.raises(CalculatorError) as jump:
        execute_direct(
            "numeric.root",
            {
                "expression": "1/(x-0.5)",
                "variable": "x",
                "bracket": ["0", "1"],
                "findAll": True,
            },
        )
    assert jump.value.code == "E_DOMAIN"


def test_numeric_minimize_certifies_global_extrema() -> None:
    import mpmath as mp

    parabola = execute_direct(
        "numeric.minimize", {"expression": "x^2 - 2", "variable": "x", "bracket": ["-2", "2"]}
    )
    assert parabola["certified"] is True
    assert parabola["kind"] == "global_extremum"
    assert parabola["method"] == "interval_branch_and_bound"
    low, high = (mp.mpf(parabola["valueEnclosure"][0]), mp.mpf(parabola["valueEnclosure"][1]))
    assert low <= -2 <= high and high - low < mp.mpf("1e-11")

    twin_minima = execute_direct(
        "numeric.minimize",
        {"expression": "(x^2 - 2)^2", "variable": "x", "bracket": ["-3", "3"]},
    )
    covered = [(mp.mpf(a), mp.mpf(b)) for a, b in twin_minima["extremumIntervals"]]
    assert any(a <= -mp.sqrt(2) <= b for a, b in covered)
    assert any(a <= mp.sqrt(2) <= b for a, b in covered)
    low, high = (mp.mpf(twin_minima["valueEnclosure"][0]), mp.mpf(twin_minima["valueEnclosure"][1]))
    assert low <= 0 <= high

    maximum = execute_direct(
        "numeric.minimize",
        {"expression": "-x^2", "variable": "x", "bracket": ["-1", "1"], "objective": "maximum"},
    )
    assert maximum["certified"] is True
    low, high = (mp.mpf(maximum["valueEnclosure"][0]), mp.mpf(maximum["valueEnclosure"][1]))
    assert low <= 0 <= high
    assert mp.mpf(maximum["extremumIntervals"][0][0]) <= 0 <= mp.mpf(maximum["extremumIntervals"][0][1])

    # The value of x^2 certifies instantly, so budget exhaustion must
    # degrade only the argmin refinement: status stays ok, intervals widen,
    # and the cover still contains the minimizer.
    coarse_argmin = execute_direct(
        "numeric.minimize",
        {
            "expression": "x^2",
            "variable": "x",
            "bracket": ["-2", "2"],
            "maxEvaluations": 60,
            "tolerance": "1e-30",
        },
    )
    assert coarse_argmin["certified"] is True
    low, high = (mp.mpf(coarse_argmin["valueEnclosure"][0]), mp.mpf(coarse_argmin["valueEnclosure"][1]))
    assert low <= 0 <= high
    covered = [(mp.mpf(a), mp.mpf(b)) for a, b in coarse_argmin["extremumIntervals"]]
    assert any(a <= 0 <= b for a, b in covered)

    # A value the budget cannot certify degrades the whole result honestly.
    exhausted = execute_direct(
        "numeric.minimize",
        {
            "expression": "x*sin(x)",
            "variable": "x",
            "bracket": ["0", "10"],
            "maxEvaluations": 48,
            "tolerance": "1e-30",
        },
    )
    assert exhausted["status"] == "uncertain"
    assert exhausted["certified"] is False
    # The global minimum of x*sin(x) on [0, 10] sits at the right endpoint,
    # below every interior stationary point; the best-known enclosure must
    # still cover it.
    endpoint_minimum = mp.mpf(10) * mp.sin(10)
    low, high = (mp.mpf(exhausted["valueEnclosure"][0]), mp.mpf(exhausted["valueEnclosure"][1]))
    assert low <= endpoint_minimum <= high

    cases = (
        ("sqrt(x)", ["-1", "1"]),
        ("1/x", ["-1", "1"]),
        ("log(x)", ["-1", "1"]),
        ("tan(x)", ["1", "2"]),
    )
    for expression_text, bracket in cases:
        with pytest.raises(CalculatorError) as undefined:
            execute_direct(
                "numeric.minimize",
                {"expression": expression_text, "variable": "x", "bracket": bracket},
            )
        assert undefined.value.code == "E_DOMAIN"


def test_numeric_minimize_handles_supported_transcendentals_without_raw_runtime_errors() -> None:
    import mpmath as mp

    cosh_result = execute_direct(
        "numeric.minimize",
        {"expression": "cosh(x)", "variable": "x", "bracket": ["-1", "1"]},
    )
    low, high = (mp.mpf(value) for value in cosh_result["valueEnclosure"])
    assert cosh_result["status"] == "ok"
    assert low <= 1 <= high
    covered = [(mp.mpf(a), mp.mpf(b)) for a, b in cosh_result["extremumIntervals"]]
    assert any(a <= 0 <= b for a, b in covered)

    cases = (
        ("acos(x)", ["-1", "1"]),
        ("atan(x)", ["-1", "1"]),
        ("gamma(x)", ["1", "3"]),
        ("sinh(x)", ["-1", "1"]),
        ("tanh(x)", ["-1", "1"]),
    )
    for expression_text, bracket in cases:
        result = execute_direct(
            "numeric.minimize",
            {"expression": expression_text, "variable": "x", "bracket": bracket},
        )
        assert result["status"] in {"ok", "uncertain"}
        assert mp.mpf(result["valueEnclosure"][0]) <= mp.mpf(result["valueEnclosure"][1])


def test_equivalence_probe_skips_negligible_numeric_differences() -> None:
    # A true-but-negligible difference must not mint a counterexample from
    # rounding noise: the probe threshold keeps tiny deltas at "unknown".
    result = execute_direct(
        "expression.equivalent",
        {"left": "x", "right": "x + 1e-40", "variables": ["x"], "precision": 30},
    )
    assert result["equivalence"] == "unknown"
    assert result["counterexample"] is None

    reproducible = execute_direct(
        "expression.equivalent",
        {"left": "x^2", "right": "x", "variables": ["x"]},
    )
    assert reproducible["equivalence"] == "not_equivalent"
    assert reproducible["counterexample"]["left"] != reproducible["counterexample"]["right"]


def test_numeric_fuzz_root_minimize_and_integrate_never_escape() -> None:
    # Bounded deterministic fuzz over the three numerically reworked
    # operations: every grammatical input returns a structured result or a
    # typed CalculatorError; raw exceptions and E_RUNTIME are failures.
    import random

    generator = random.Random(20260817)
    builders = (
        lambda: f"{generator.randint(-9, 9)}*x^2 + {generator.randint(-9, 9)}*x + {generator.randint(-9, 9)}",
        lambda: f"x^3 - {generator.randint(1, 9)}*x - {generator.randint(1, 9)}",
        lambda: f"sin({generator.randint(1, 5)}*x) + {generator.randint(-3, 3)}",
        lambda: f"exp(-x^2/{generator.randint(1, 4)}) - {generator.randint(0, 3)}/10",
        lambda: f"cos(x)*x + {generator.randint(-5, 5)}",
        lambda: f"(x - {generator.randint(-3, 3)})^2 - {generator.randint(0, 4)}",
    )
    tolerated = {
        "E_INPUT",
        "E_DOMAIN",
        "E_LIMIT",
        "E_SYNTAX",
        "E_CONVERGENCE",
        "E_TIMEOUT",
    }
    for _ in range(40):
        expression = generator.choice(builders)()
        lower = generator.randint(-8, 4)
        upper = lower + generator.randint(1, 12)
        bracket = [str(lower), str(upper)]
        for operation, arguments in (
            (
                "numeric.root",
                {
                    "expression": expression,
                    "variable": "x",
                    "bracket": bracket,
                    "findAll": generator.random() < 0.5,
                    "resolution": 64,
                    "precision": 20,
                    "maxIterations": 256,
                },
            ),
            (
                "numeric.minimize",
                {
                    "expression": expression,
                    "variable": "x",
                    "bracket": bracket,
                    "maxEvaluations": 400,
                    "precision": 20,
                },
            ),
            (
                "numeric.integrate",
                {
                    "expression": expression,
                    "variable": "x",
                    "lower": bracket[0],
                    "upper": bracket[1],
                    "maxEvaluations": 2000,
                    "precision": 20,
                },
            ),
        ):
            try:
                result = execute_direct(operation, arguments)
            except CalculatorError as error:
                assert error.code in tolerated, (operation, expression, error.code, error.message)
                continue
            if operation == "numeric.root" and result.get("findAll"):
                assert result["count"] == len(result["roots"])
            if operation == "numeric.minimize":
                assert result["status"] in {"ok", "uncertain"}
            if operation == "numeric.integrate":
                assert result["evaluations"] <= arguments["maxEvaluations"]
                if result["approx"] is not None:
                    assert Decimal(result["resultInterval"][0]) <= Decimal(result["approx"])
                    assert Decimal(result["approx"]) <= Decimal(result["resultInterval"][1])
