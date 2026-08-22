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

from math_anchor import __version__
from plugin_server import plugin_server_parameters, tools_listing_bytes


def schema_is_closed(schema: dict) -> bool:
    if "oneOf" in schema:
        return all(schema_is_closed(variant) for variant in schema["oneOf"])
    return schema.get("additionalProperties") is False


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
    parameters = plugin_server_parameters(selected_plugin)
    server_errors = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
    async with stdio_client(parameters, errlog=server_errors) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            initialized = await session.initialize()
            assert initialized.serverInfo.version == __version__
            listed = await session.list_tools()
            names = sorted(tool.name for tool in listed.tools)
            assert names == ["math.batch", "math.describe", "math.run", "math.search"]
            assert all(tool.annotations and tool.annotations.readOnlyHint for tool in listed.tools)
            run_tool = next(tool for tool in listed.tools if tool.name == "math.run")
            batch_tool = next(tool for tool in listed.tools if tool.name == "math.batch")
            assert len(run_tool.inputSchema["oneOf"]) == 34
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
            assert listed_bytes < 40_000
            assert run_tool.inputSchema["additionalProperties"] is False
            assert all(
                schema_is_closed(variant["properties"]["arguments"])
                for variant in run_tool.inputSchema["oneOf"]
            )
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
            await asyncio.sleep(0.3)
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
            workers_before = persistent_worker_cpu_seconds()
            await asyncio.sleep(0.5)
            workers_after = persistent_worker_cpu_seconds()
            leaked = {
                pid: round(cpu - workers_before[pid], 3)
                for pid, cpu in workers_after.items()
                if pid in workers_before and cpu - workers_before[pid] > 0.35
            }
            assert not leaked, f"workers kept computing after cancellation: {leaked}"
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
        "description, equivalence and solution verification, unit expressions, symbolic dimensional analysis and Pi groups, financial math, stability-aware "
        "linear solving, numerical integration, probability, inferential statistics, standard algebra, exact/high-precision results, "
        "schema rejection, MCP tool-error signaling, domain errors, precision provenance, large integer output, ordered partial batch, cancellation recovery, "
        "and unsafe-input rejection. "
        f"math.run advertises {len(run_tool.inputSchema['oneOf'])} input variants in {run_schema_bytes} bytes; "
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
