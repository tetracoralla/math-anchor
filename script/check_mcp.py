from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
import time
from pathlib import Path

import psutil
from mcp import ClientSession
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError
from mcp.types import (
    CancelledNotification,
    CancelledNotificationParams,
    ClientNotification,
)

from math_anchor.catalog import OPERATIONS
from plugin_server import plugin_server_parameters, tools_listing_bytes


def persistent_worker_cpu_seconds() -> dict[int, float]:
    snapshot: dict[int, float] = {}
    for process in psutil.Process().children(recursive=True):
        try:
            if "--persistent" in process.cmdline():
                snapshot[process.pid] = sum(process.cpu_times()[:2])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return snapshot


async def main(plugin_root: Path | None = None) -> None:
    root = Path(__file__).resolve().parent.parent
    selected_plugin = plugin_root or root / "plugins/math-anchor"
    expected_version = json.loads(
        (selected_plugin / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )["version"]
    parameters = plugin_server_parameters(selected_plugin)
    server_errors = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
    async with stdio_client(parameters, errlog=server_errors) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            initialized = await session.initialize()
            assert initialized.serverInfo.version == expected_version
            listed = await session.list_tools()
            names = sorted(tool.name for tool in listed.tools)
            assert names == ["math.batch", "math.describe", "math.run", "math.search"]
            assert all(tool.annotations and tool.annotations.readOnlyHint for tool in listed.tools)
            run_tool = next(tool for tool in listed.tools if tool.name == "math.run")
            batch_tool = next(tool for tool in listed.tools if tool.name == "math.batch")
            assert "fixed-width overflow" in run_tool.description
            assert "Do not use for trivial low-risk arithmetic" in run_tool.description
            assert "{operation, arguments}; never flatten" in run_tool.description
            describe_tool = next(tool for tool in listed.tools if tool.name == "math.describe")
            assert "nest one under math.run.arguments" in describe_tool.description
            assert set(run_tool.inputSchema["properties"]["operation"]["enum"]) == set(OPERATIONS)
            run_schema_bytes = len(
                json.dumps(run_tool.inputSchema, ensure_ascii=False, separators=(",", ":")).encode()
            )
            run_output_schema_bytes = len(
                json.dumps(run_tool.outputSchema, ensure_ascii=False, separators=(",", ":")).encode()
            )
            batch_schema_bytes = len(
                json.dumps(batch_tool.inputSchema, ensure_ascii=False, separators=(",", ":")).encode()
            )
            listed_bytes = tools_listing_bytes(listed.tools)
            assert all(tool.inputSchema["additionalProperties"] is False for tool in listed.tools)
            assert "oneOf" not in batch_tool.inputSchema["properties"]["items"]["items"]
            assert batch_schema_bytes < 2_000
            assert run_schema_bytes < 4_800
            assert not ({"oneOf", "anyOf", "allOf", "$defs"} & set(run_tool.inputSchema))
            assert listed_bytes < 10_000
            assert run_tool.inputSchema["additionalProperties"] is False
            assert run_tool.inputSchema["properties"]["arguments"]["type"] == "object"
            assert set(describe_tool.inputSchema["properties"]["operation"]["enum"]) == set(OPERATIONS)
            assert run_output_schema_bytes < 2_000
            assert run_tool.outputSchema["required"] == ["status"]
            assert {"exact", "approx", "warnings", "error"} <= set(
                run_tool.outputSchema["properties"]
            )

            direct = await session.call_tool(
                "math.run",
                {"operation": "expression.evaluate", "arguments": {"expression": "6*7"}},
            )
            assert direct.isError is False
            assert direct.structuredContent["exact"] == "42"

            represented = await session.call_tool(
                "math.run",
                {
                    "operation": "integer.represent",
                    "arguments": {
                        "value": "0xFF",
                        "bitWidth": 8,
                        "signedness": "twos_complement",
                        "inputMode": "bits",
                    },
                },
            )
            assert represented.structuredContent["result"]["decimal"] == "-1"
            rotated = await session.call_tool(
                "math.run",
                {
                    "operation": "integer.bitwise",
                    "arguments": {
                        "action": "rotate_left",
                        "value": "0x81",
                        "count": 1,
                        "bitWidth": 8,
                        "inputMode": "bits",
                    },
                },
            )
            assert rotated.structuredContent["result"]["hexadecimal"] == "03"
            machine = await session.call_tool(
                "math.run",
                {
                    "operation": "integer.machine_arithmetic",
                    "arguments": {
                        "action": "add",
                        "left": "127",
                        "right": "1",
                        "bitWidth": 8,
                        "signedness": "twos_complement",
                        "overflowBehavior": "wrapping",
                    },
                },
            )
            assert machine.structuredContent["mathematicalResult"] == "128"
            assert machine.structuredContent["result"]["decimal"] == "-128"
            assert machine.structuredContent["wrapped"] is True
            ieee = await session.call_tool(
                "math.run",
                {
                    "operation": "float.ieee754",
                    "arguments": {
                        "action": "inspect",
                        "value": "0.1",
                        "format": "binary64",
                    },
                },
            )
            assert ieee.structuredContent["value"]["rawHex"] == "3FB999999999999A"
            assert ieee.structuredContent["value"]["roundTripDecimal"] == "0.1"
            assert ieee.structuredContent["value"]["inputRounded"] is True
            quantized = await session.call_tool(
                "math.run",
                {
                    "operation": "decimal.quantize",
                    "arguments": {
                        "action": "increment",
                        "value": "1.23",
                        "increment": "0.05",
                        "roundingMode": "half_up",
                    },
                },
            )
            assert quantized.structuredContent["result"] == "1.25"
            divided = await session.call_tool(
                "math.run",
                {
                    "operation": "integer.divide",
                    "arguments": {
                        "dividend": "-7",
                        "divisor": "3",
                        "divisionMode": "euclidean",
                    },
                },
            )
            assert divided.structuredContent["quotient"] == "-3"
            assert divided.structuredContent["remainder"] == "2"

            rejected_outer = await session.call_tool(
                "math.search",
                {"query": "integrate", "unexpected": True},
            )
            assert rejected_outer.isError is True
            oversized_discovery = await session.call_tool(
                "math.search",
                {"query": "x" * 200_000},
            )
            assert oversized_discovery.isError is True
            assert len(
                json.dumps(
                    oversized_discovery.model_dump(by_alias=True, exclude_none=True),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode()
            ) < 1_024

            equivalent = await session.call_tool(
                "math.run",
                {
                    "operation": "expression.equivalent",
                    "arguments": {
                        "left": "sin(x)^2 + cos(x)^2",
                        "right": "1",
                        "variables": ["x"],
                    },
                },
            )
            assert equivalent.structuredContent["equivalence"] == "equivalent"
            assert equivalent.structuredContent["proven"] is True

            factored = await session.call_tool(
                "math.run",
                {
                    "operation": "algebra.transform",
                    "arguments": {"action": "factor", "expression": "x^2-1", "variables": ["x"]},
                },
            )
            assert factored.structuredContent["exact"] == "(x - 1)*(x + 1)"

            linear_system = await session.call_tool(
                "math.run",
                {
                    "operation": "matrix.solve",
                    "arguments": {"matrix": [[1, 1], [1, -1]], "constants": [7, 1]},
                },
            )
            assert linear_system.structuredContent["classification"] == "unique"
            assert [item["exact"] for item in linear_system.structuredContent["particular"]] == ["4", "3"]

            vector_calculus = await session.call_tool(
                "math.run",
                {
                    "operation": "calculus.multivariate",
                    "arguments": {
                        "action": "curl",
                        "expressions": ["y*z", "x*z", "x*y"],
                        "variables": ["x", "y", "z"],
                    },
                },
            )
            assert vector_calculus.structuredContent["exact"] == [["0"], ["0"], ["0"]]
            invalid_direction = await session.call_tool(
                "math.run",
                {
                    "operation": "calculus.multivariate",
                    "arguments": {
                        "action": "directional_derivative",
                        "expression": "x^2 + y^2",
                        "variables": ["x", "y"],
                        "direction": [1],
                    },
                },
            )
            assert invalid_direction.isError is True
            assert invalid_direction.structuredContent["error"]["code"] == "E_INPUT"

            eigenspaces = await session.call_tool(
                "math.run",
                {
                    "operation": "matrix.reduce",
                    "arguments": {"action": "eigenspaces", "matrix": [[2, 1], [0, 2]]},
                },
            )
            assert eigenspaces.structuredContent["diagonalizable"] is False
            assert eigenspaces.structuredContent["eigenspaces"][0]["geometricMultiplicity"] == 1
            cholesky = await session.call_tool(
                "math.run",
                {
                    "operation": "matrix.reduce",
                    "arguments": {"action": "cholesky", "matrix": [[4, 2], [2, 3]]},
                },
            )
            assert cholesky.structuredContent["factors"][0]["exact"] == [
                ["2", "0"],
                ["1", "sqrt(2)"],
            ]

            searched = await session.call_tool("math.search", {"query": "integrate"})
            assert searched.structuredContent["operations"][0]["id"] == "calculus.integrate"

            searched_chinese = await session.call_tool("math.search", {"query": "帮我求导"})
            assert searched_chinese.structuredContent["operations"][0]["id"] == "calculus.derivative"

            described = await session.call_tool("math.describe", {"operation": "calculus.integrate"})
            assert described.structuredContent["operation"]["inputSchema"]["required"] == ["expression", "variable"]

            searched_dimension = await session.call_tool(
                "math.search", {"query": "检查物理公式的量纲一致性"}
            )
            assert searched_dimension.structuredContent["operations"][0]["id"] == "dimension.check"
            described_dimension = await session.call_tool(
                "math.describe", {"operation": "dimension.infer"}
            )
            assert described_dimension.structuredContent["operation"]["inputSchema"]["required"] == [
                "equations",
                "unknown",
            ]
            searched_pi_groups = await session.call_tool(
                "math.search", {"query": "生成无量纲组合"}
            )
            assert searched_pi_groups.structuredContent["operations"][0]["id"] == "dimension.pi_groups"
            described_pi_groups = await session.call_tool(
                "math.describe", {"operation": "dimension.pi_groups"}
            )
            assert described_pi_groups.structuredContent["operation"]["inputSchema"]["required"] == [
                "variables"
            ]

            dimension_check = await session.call_tool(
                "math.run",
                {
                    "operation": "dimension.check",
                    "arguments": {
                        "left": "F",
                        "right": "m * a",
                        "symbols": {
                            "F": "newton",
                            "m": "kilogram",
                            "a": "meter / second^2",
                        },
                    },
                },
            )
            assert dimension_check.structuredContent["dimensionallyConsistent"] is True
            assert dimension_check.structuredContent["scope"] == "dimensional_consistency_only"

            dimension_inference = await session.call_tool(
                "math.run",
                {
                    "operation": "dimension.infer",
                    "arguments": {
                        "equations": [{"left": "F", "right": "m * a"}],
                        "known": {"F": "newton", "m": "kilogram"},
                        "unknown": ["a"],
                    },
                },
            )
            assert dimension_inference.structuredContent["classification"] == "unique"
            assert dimension_inference.structuredContent["inferred"]["a"]["dimension"] == {
                "length": "1",
                "time": "-2",
            }

            pi_groups = await session.call_tool(
                "math.run",
                {
                    "operation": "dimension.pi_groups",
                    "arguments": {
                        "variables": {
                            "rho": "kilogram / meter^3",
                            "v": "meter / second",
                            "L": "meter",
                            "mu": "pascal * second",
                        }
                    },
                },
            )
            assert pi_groups.structuredContent["scope"] == "dimensionless_basis_only"
            assert pi_groups.structuredContent["groups"][0]["exponents"] == {
                "L": "1",
                "mu": "-1",
                "rho": "1",
                "v": "1",
            }
            invalid_pi_groups = await session.call_tool(
                "math.run",
                {
                    "operation": "dimension.pi_groups",
                    "arguments": {"variables": {"x": {"length": 1}}},
                },
            )
            assert invalid_pi_groups.isError is True
            assert invalid_pi_groups.structuredContent["status"] == "error"
            assert invalid_pi_groups.structuredContent["error"]["code"] == "E_INPUT"
            assert invalid_pi_groups.structuredContent["error"]["retryable"] is False
            assert invalid_pi_groups.structuredContent["error"]["phase"] == "input"
            assert invalid_pi_groups.structuredContent["error"]["suggestedAction"] == "correct_input"

            derived_dimension = await session.call_tool(
                "math.run",
                {
                    "operation": "dimension.check",
                    "arguments": {
                        "left": "x^12",
                        "right": "x^12",
                        "symbols": {"x": {"length": 999_983}},
                    },
                },
            )
            assert derived_dimension.structuredContent["leftDimension"] == {
                "length": "11999796"
            }

            invalid_dimension_exponent = await session.call_tool(
                "math.run",
                {
                    "operation": "dimension.check",
                    "arguments": {
                        "left": "x",
                        "right": "x",
                        "symbols": {"x": {"length": "0.5"}},
                    },
                },
            )
            assert invalid_dimension_exponent.structuredContent["status"] == "error"
            assert invalid_dimension_exponent.structuredContent["error"]["code"] == "E_INPUT"

            evaluated = await session.call_tool(
                "math.run",
                {"operation": "expression.evaluate", "arguments": {"expression": "sqrt(2)", "precision": 50}},
            )
            assert evaluated.structuredContent["exact"] == "sqrt(2)"
            special_function = await session.call_tool(
                "math.run",
                {
                    "operation": "expression.evaluate",
                    "arguments": {"expression": "beta(2, 3) + polygamma(1, 1)"},
                },
            )
            assert special_function.structuredContent["exact"] == "1/12 + pi**2/6"

            misspelled = await session.call_tool(
                "math.run",
                {"operation": "expression.evaluate", "arguments": {"expression": "sqrt(2)", "precison": 50}},
            )
            assert misspelled.structuredContent["status"] == "error"
            assert misspelled.structuredContent["error"]["code"] == "E_INPUT"

            high_precision_root = await session.call_tool(
                "math.run",
                {
                    "operation": "numeric.root",
                    "arguments": {
                        "expression": "x^3 - 2*x - 5",
                        "variable": "x",
                        "bracket": [2, 3],
                        "precision": 50,
                    },
                },
            )
            assert high_precision_root.structuredContent["precision"] == 50
            assert high_precision_root.structuredContent["approx"].startswith(
                "2.094551481542326591482386540579302963857306105628"
            )

            undefined = await session.call_tool(
                "math.run",
                {"operation": "expression.evaluate", "arguments": {"expression": "1/0"}},
            )
            assert undefined.isError is True
            assert undefined.structuredContent["status"] == "error"
            assert undefined.structuredContent["error"]["code"] == "E_DOMAIN"

            syntax_error = await session.call_tool(
                "math.run",
                {"operation": "expression.evaluate", "arguments": {"expression": "1+"}},
            )
            assert syntax_error.isError is True
            assert syntax_error.structuredContent["status"] == "error"
            assert syntax_error.structuredContent["error"]["code"] == "E_SYNTAX"
            assert syntax_error.structuredContent["error"]["phase"] == "input"
            assert syntax_error.structuredContent["error"]["suggestedAction"] == "correct_input"

            float_eigenvalues = await session.call_tool(
                "math.run",
                {
                    "operation": "matrix.eigenvalues",
                    "arguments": {"matrix": [[1.0, 2.0], [3.0, 4.0]], "precision": 50},
                },
            )
            assert float_eigenvalues.structuredContent["precision"] <= 15
            assert all(value["exact"] is None for value in float_eigenvalues.structuredContent["values"])

            factorial = await session.call_tool(
                "math.run",
                {"operation": "expression.evaluate", "arguments": {"expression": "factorial(5000)"}},
            )
            assert factorial.structuredContent["status"] == "ok"
            assert len(factorial.structuredContent["exact"]) == 16_326
            assert len(factorial.content[0].text) < 128

            batched = await session.call_tool(
                "math.batch",
                {
                    "items": [
                        {"operation": "matrix.determinant", "arguments": {"matrix": [[1, 2], [3, 4]]}},
                        {"operation": "units.convert", "arguments": {"value": 1, "fromUnit": "hour", "toUnit": "second"}},
                    ]
                },
            )
            assert batched.structuredContent["status"] == "ok"
            assert batched.structuredContent["results"][0]["exact"] == "-2"
            assert batched.structuredContent["results"][1]["exact"] == "3600"

            unit_catalog = await session.call_tool(
                "math.run",
                {
                    "operation": "units.search",
                    "arguments": {"query": "Mbps"},
                },
            )
            assert unit_catalog.structuredContent["count"] == 1
            assert unit_catalog.structuredContent["units"][0]["id"] == "megabit-per-second"

            stable_unit_conversion = await session.call_tool(
                "math.run",
                {
                    "operation": "units.convert",
                    "arguments": {
                        "value": "100",
                        "fromUnit": "megabit-per-second",
                        "toUnit": "megabyte-per-second",
                    },
                },
            )
            assert stable_unit_conversion.structuredContent["exact"] == "25/2"

            implicit_calendar_average = await session.call_tool(
                "math.run",
                {
                    "operation": "units.convert",
                    "arguments": {"value": 1, "fromUnit": "month", "toUnit": "day"},
                },
            )
            assert implicit_calendar_average.isError is True
            assert implicit_calendar_average.structuredContent["error"]["code"] == "E_UNIT"

            explicit_calendar_average = await session.call_tool(
                "math.run",
                {
                    "operation": "units.convert",
                    "arguments": {
                        "value": 1,
                        "fromUnit": "month",
                        "toUnit": "day",
                        "calendarPolicy": "average_duration",
                    },
                },
            )
            assert explicit_calendar_average.structuredContent["exact"] == "487/16"
            assert "not date or time-zone arithmetic" in explicit_calendar_average.structuredContent["warnings"][0]

            exact_vector = await session.call_tool(
                "math.run",
                {
                    "operation": "linear_algebra.exact",
                    "arguments": {
                        "action": "projection",
                        "left": [2, 2],
                        "onto": [1, 0],
                    },
                },
            )
            assert [value["exact"] for value in exact_vector.structuredContent["result"]] == ["2", "0"]

            numerical_svd = await session.call_tool(
                "math.run",
                {
                    "operation": "linear_algebra.numeric",
                    "arguments": {
                        "action": "svd",
                        "matrix": [["3", "0"], ["0", "2"]],
                    },
                },
            )
            assert numerical_svd.structuredContent["singularValues"] == ["3", "2"]
            assert numerical_svd.structuredContent["numericFormat"] == "binary64"
            assert numerical_svd.structuredContent["warnings"]

            extended_probability = await session.call_tool(
                "math.run",
                {
                    "operation": "probability.distribution",
                    "arguments": {
                        "distribution": "beta",
                        "function": "quantile",
                        "probability": "0.5",
                        "alpha": "2",
                        "beta": "2",
                    },
                },
            )
            assert extended_probability.structuredContent["value"]["approx"] == "0.5"

            two_sample_inference = await session.call_tool(
                "math.run",
                {
                    "operation": "statistics.infer",
                    "arguments": {
                        "action": "two_sample_t_test",
                        "sampleA": ["10", "12", "9", "11", "13"],
                        "sampleB": ["7", "8", "9", "8", "10"],
                    },
                },
            )
            assert two_sample_inference.structuredContent["method"] == "welch_two_sample_t_test"
            assert isinstance(two_sample_inference.structuredContent["test"]["degreesOfFreedom"], str)

            uncertainty = await session.call_tool(
                "math.run",
                {
                    "operation": "measurement.propagate",
                    "arguments": {
                        "expression": "x * y",
                        "inputs": {
                            "x": {"value": "2", "standardUncertainty": "0.1"},
                            "y": {"value": "3", "standardUncertainty": "0.2"},
                        },
                        "correlations": [
                            {"left": "x", "right": "y", "coefficient": "0.5"}
                        ],
                    },
                },
            )
            assert uncertainty.structuredContent["nominal"]["exact"] == "6"
            assert uncertainty.structuredContent["combinedStandardUncertainty"]["exact"] == "sqrt(37)/10"
            assert uncertainty.structuredContent["linearModel"] is False

            advanced_batch = await session.call_tool(
                "math.batch",
                {
                    "items": [
                        {
                            "operation": "solution.verify",
                            "arguments": {
                                "constraints": "x^2 = 2",
                                "variables": ["x"],
                                "candidates": [{"x": "sqrt(2)"}, {"x": "-sqrt(2)"}],
                                "checkCompleteness": True,
                            },
                        },
                        {
                            "operation": "quantity.evaluate",
                            "arguments": {
                                "expression": "80 * kg * 9.81 * m / s^2",
                                "toUnit": "newton",
                            },
                        },
                        {
                            "operation": "finance.calculate",
                            "arguments": {
                                "action": "npv",
                                "cashFlows": ["-1000", "400", "400", "400"],
                                "ratePerPeriod": "0.1",
                            },
                        },
                        {
                            "operation": "matrix.solve_approximate",
                            "arguments": {
                                "matrix": [["3", "1"], ["1", "2"]],
                                "constants": ["9", "8"],
                            },
                        },
                        {
                            "operation": "numeric.integrate",
                            "arguments": {
                                "expression": "sin(x)",
                                "variable": "x",
                                "lower": "0",
                                "upper": "3.14159265358979323846",
                                "featureScale": "0.01",
                            },
                        },
                        {
                            "operation": "probability.distribution",
                            "arguments": {
                                "distribution": "normal",
                                "function": "cdf",
                                "x": "1.96",
                            },
                        },
                        {
                            "operation": "statistics.infer",
                            "arguments": {
                                "action": "mean_confidence_interval",
                                "sample": ["10", "12", "9", "11", "13"],
                            },
                        },
                        {
                            "operation": "dimension.check",
                            "arguments": {
                                "left": "d",
                                "right": "v + 0.5 * a * t^2",
                                "symbols": {
                                    "d": "meter",
                                    "v": "meter / second",
                                    "a": "meter / second^2",
                                    "t": "second",
                                },
                            },
                        },
                        {
                            "operation": "dimension.infer",
                            "arguments": {
                                "equations": [{"left": "z", "right": "x * y"}],
                                "known": {"z": "meter"},
                                "unknown": ["x", "y"],
                            },
                        },
                        {
                            "operation": "dimension.pi_groups",
                            "arguments": {
                                "variables": {
                                    "rho": "kilogram / meter^3",
                                    "v": "meter / second",
                                    "L": "meter",
                                    "mu": "pascal * second",
                                }
                            },
                        },
                    ]
                },
            )
            assert advanced_batch.structuredContent["status"] == "ok"
            advanced_results = advanced_batch.structuredContent["results"]
            assert advanced_results[0]["omissionRisk"] == "none_proven"
            assert advanced_results[1]["exact"] == "3924/5"
            assert advanced_results[2]["results"][0]["approx"] == "-5.26"
            assert advanced_results[3]["classification"] == "stable_for_tolerance"
            assert advanced_results[4]["errorBoundCertified"] is False
            assert advanced_results[4]["approx"] == "2.0"
            assert advanced_results[5]["value"]["approx"].startswith("0.975002")
            assert advanced_results[6]["interval"]["lower"]["approx"].startswith("9.0367")
            assert advanced_results[7]["dimensionallyConsistent"] is False
            assert advanced_results[7]["issues"][0]["code"] == "DIMENSION_ADD_MISMATCH"
            assert advanced_results[8]["classification"] == "underdetermined"
            assert advanced_results[9]["nullity"] == 1

            narrow_peak = await session.call_tool(
                "math.run",
                {
                    "operation": "numeric.integrate",
                    "arguments": {
                        "expression": "exp(-1000000*(x-0.12345)^2)",
                        "variable": "x",
                        "lower": "0",
                        "upper": "1",
                    },
                },
            )
            assert narrow_peak.structuredContent["status"] == "uncertain"
            assert narrow_peak.structuredContent["converged"] is False
            assert abs(float(narrow_peak.structuredContent["approx"]) - 0.001772453850905516) < 1e-12

            partial = await session.call_tool(
                "math.batch",
                {
                    "items": [
                        {
                            "operation": "expression.evaluate",
                            "arguments": {"expression": "2+2", "unexpected": True},
                        },
                        {
                            "operation": "expression.evaluate",
                            "arguments": {"expression": "4+4"},
                            "unexpected": True,
                        },
                        {"operation": "expression.evaluate", "arguments": {"expression": "3+3"}},
                    ]
                },
            )
            assert partial.isError is False
            assert partial.structuredContent["status"] == "partial"
            assert partial.structuredContent["results"][0]["index"] == 0
            assert partial.structuredContent["results"][0]["error"]["code"] == "E_INPUT"
            assert partial.structuredContent["results"][1]["error"]["code"] == "E_INPUT"
            assert partial.structuredContent["results"][2]["exact"] == "6"

            warm_start = time.perf_counter()
            for _ in range(5):
                warm = await session.call_tool(
                    "math.run",
                    {"operation": "expression.evaluate", "arguments": {"expression": "6*7"}},
                )
                assert warm.structuredContent["exact"] == "42"
            warm_elapsed = time.perf_counter() - warm_start
            # Generous ceiling: shared CI runners can stretch five warm
            # round trips past a tight budget, while a real warm-pool
            # regression pays a fresh worker startup per call and lands
            # several times above this bound.
            assert warm_elapsed < 5.0, f"five warm math.run calls took {warm_elapsed:.3f}s"

            # Drive real protocol cancellation: the bundled client SDK only
            # cleans up its local stream when a task is cancelled and never
            # sends notifications/cancelled, so cancelling the task below
            # would leave the server-side worker computing to its 30 s
            # timeout. Send the notification explicitly, then verify the
            # active worker was killed instead of merely freed a pool slot.
            # The SDK assigns sequential integer request ids, so the in-flight
            # call consumes the current counter value; if this private field
            # disappears in a future SDK, fail here rather than silently
            # testing nothing.
            cancelled_request_id = session._request_id
            cancelled_call = asyncio.create_task(
                session.call_tool(
                    "math.run",
                    {
                        "operation": "expression.evaluate",
                        "arguments": {
                            "expression": "floor(gamma(exp(7)))",
                            "precision": 16,
                        },
                        "timeoutMs": 30_000,
                    },
                )
            )
            # Identify the worker that is actually consuming CPU for this
            # request. The pool may also contain idle workers, and after
            # cancellation it deliberately starts a replacement prewarm; PID
            # identity keeps both from being mistaken for the cancelled job.
            active_workers: set[int] = set()
            previous_workers = persistent_worker_cpu_seconds()
            active_deadline = time.monotonic() + 2
            while not active_workers and time.monotonic() < active_deadline:
                await asyncio.sleep(0.1)
                current_workers = persistent_worker_cpu_seconds()
                active_workers = {
                    pid
                    for pid, cpu in current_workers.items()
                    if pid in previous_workers and cpu - previous_workers[pid] > 0.04
                }
                previous_workers = current_workers
            assert active_workers, "no active persistent worker observed during cancellable call"
            await session.send_notification(
                ClientNotification(
                    CancelledNotification(
                        method="notifications/cancelled",
                        params=CancelledNotificationParams(
                            requestId=cancelled_request_id,
                            reason="check cancellation",
                        ),
                    )
                )
            )
            try:
                await cancelled_call
            except McpError:
                pass
            else:  # pragma: no cover - the server must reject the cancelled request
                raise AssertionError("cancelled MCP request unexpectedly completed")
            cleanup_deadline = time.monotonic() + 2
            remaining_active = active_workers
            while remaining_active and time.monotonic() < cleanup_deadline:
                await asyncio.sleep(0.05)
                remaining_active &= set(persistent_worker_cpu_seconds())
            assert not remaining_active, (
                f"cancelled active workers remained alive after cleanup: {sorted(remaining_active)}"
            )
            recovered_after_cancel = await asyncio.wait_for(
                session.call_tool(
                    "math.run",
                    {
                        "operation": "expression.evaluate",
                        "arguments": {"expression": "6*7"},
                    },
                ),
                timeout=3,
            )
            assert recovered_after_cancel.structuredContent["exact"] == "42"

            blocked = await session.call_tool(
                "math.run",
                {"operation": "expression.evaluate", "arguments": {"expression": "__import__('os').system('id')"}},
            )
            assert blocked.isError is True
            assert blocked.structuredContent["status"] == "error"
            assert blocked.structuredContent["error"]["code"] in {"E_AST_BLOCK", "E_NAME"}

    server_errors.seek(0)
    server_error_text = server_errors.read()
    server_errors.close()
    assert "Traceback" not in server_error_text, server_error_text
    assert "IncompleteFieldDefinitionWarning" not in server_error_text, server_error_text

    print(
        "MCP runtime check passed through plugin transport: one-call typed run, multilingual discovery, "
        "description, equivalence and solution verification, stable unit discovery, calendar-safe conversions, unit expressions, symbolic dimensional analysis and Pi groups, financial math, stability-aware "
        "linear solving, vector calculus, exact eigenspaces and decompositions, exact vector algebra, diagnostic SVD, numerical integration, extended probability distributions, comparative inference, covariance uncertainty propagation, registered special functions, standard algebra, exact/high-precision results, "
        "schema rejection, MCP tool-error signaling, domain errors, precision provenance, large integer output, ordered partial batch, cancellation recovery, "
        "and unsafe-input rejection. "
        f"math.run advertises {len(run_tool.inputSchema['properties']['operation']['enum'])} operation ids in a Codex-host-safe {run_schema_bytes}-byte envelope; "
        f"its result contract is {run_output_schema_bytes} bytes; "
        f"compact math.batch input is {batch_schema_bytes} bytes and all four listed tools total {listed_bytes} bytes; "
        f"five warm expression calls completed in {warm_elapsed:.3f}s."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Exercise a packaged Math Anchor Plugin")
    parser.add_argument(
        "--plugin-root",
        type=Path,
        help="installed or source Plugin directory (defaults to plugins/math-anchor)",
    )
    arguments = parser.parse_args()
    asyncio.run(main(arguments.plugin_root))
