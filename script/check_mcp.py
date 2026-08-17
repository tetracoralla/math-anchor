from __future__ import annotations

import asyncio
import json
import tempfile
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def schema_is_closed(schema: dict) -> bool:
    if "oneOf" in schema:
        return all(schema_is_closed(variant) for variant in schema["oneOf"])
    return schema.get("additionalProperties") is False


async def main() -> None:
    root = Path(__file__).resolve().parent.parent
    plugin_root = root / "plugins/math-anchor"
    plugin_config = json.loads((plugin_root / ".mcp.json").read_text())
    server_config = plugin_config["mcpServers"]["math-anchor"]
    server_cwd = (plugin_root / server_config["cwd"]).resolve()
    server_command = Path(server_config["command"])
    if not server_command.is_absolute():
        server_command = (server_cwd / server_command).resolve()
    parameters = StdioServerParameters(
        command=str(server_command),
        args=server_config.get("args", []),
        cwd=str(server_cwd),
    )
    server_errors = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
    async with stdio_client(parameters, errlog=server_errors) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = sorted(tool.name for tool in listed.tools)
            assert names == ["math.batch", "math.describe", "math.run", "math.search"]
            assert all(tool.annotations and tool.annotations.readOnlyHint for tool in listed.tools)
            run_tool = next(tool for tool in listed.tools if tool.name == "math.run")
            batch_tool = next(tool for tool in listed.tools if tool.name == "math.batch")
            assert len(run_tool.inputSchema["oneOf"]) == 31
            run_schema_bytes = len(
                json.dumps(run_tool.inputSchema, ensure_ascii=False, separators=(",", ":")).encode()
            )
            run_output_schema_bytes = len(
                json.dumps(run_tool.outputSchema, ensure_ascii=False, separators=(",", ":")).encode()
            )
            batch_schema_bytes = len(
                json.dumps(batch_tool.inputSchema, ensure_ascii=False, separators=(",", ":")).encode()
            )
            listed_bytes = len(
                json.dumps(
                    [tool.model_dump(by_alias=True, exclude_none=True) for tool in listed.tools],
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode()
            )
            assert "oneOf" not in batch_tool.inputSchema["properties"]["items"]["items"]
            assert batch_schema_bytes < 2_000
            assert listed_bytes < 64_000
            assert run_tool.inputSchema["additionalProperties"] is False
            assert all(
                schema_is_closed(variant["properties"]["arguments"])
                for variant in run_tool.inputSchema["oneOf"]
            )
            assert len(run_tool.outputSchema["oneOf"]) >= 6
            assert set(run_tool.outputSchema["$defs"]) >= {"textOrNull", "value", "textMatrix"}

            direct = await session.call_tool(
                "math.run",
                {"operation": "expression.evaluate", "arguments": {"expression": "6*7"}},
            )
            assert direct.structuredContent["exact"] == "42"

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
                        {"operation": "expression.evaluate", "arguments": {"expression": "3+3"}},
                    ]
                },
            )
            assert partial.structuredContent["status"] == "partial"
            assert partial.structuredContent["results"][0]["index"] == 0
            assert partial.structuredContent["results"][0]["error"]["code"] == "E_INPUT"
            assert partial.structuredContent["results"][1]["exact"] == "6"

            warm_start = time.perf_counter()
            for _ in range(5):
                warm = await session.call_tool(
                    "math.run",
                    {"operation": "expression.evaluate", "arguments": {"expression": "6*7"}},
                )
                assert warm.structuredContent["exact"] == "42"
            warm_elapsed = time.perf_counter() - warm_start
            assert warm_elapsed < 1.5, f"five warm math.run calls took {warm_elapsed:.3f}s"

            blocked = await session.call_tool(
                "math.run",
                {"operation": "expression.evaluate", "arguments": {"expression": "__import__('os').system('id')"}},
            )
            assert blocked.structuredContent["status"] == "error"
            assert blocked.structuredContent["error"]["code"] in {"E_AST_BLOCK", "E_NAME"}

    server_errors.seek(0)
    server_error_text = server_errors.read()
    server_errors.close()
    assert "Traceback" not in server_error_text, server_error_text
    assert "IncompleteFieldDefinitionWarning" not in server_error_text, server_error_text

    print(
        "MCP runtime check passed through plugin transport: one-call typed run, multilingual discovery, "
        "description, equivalence and solution verification, unit expressions, financial math, stability-aware "
        "linear solving, numerical integration, probability, inferential statistics, standard algebra, exact/high-precision results, "
        "schema rejection, domain errors, precision provenance, large integer output, ordered partial batch, "
        "and unsafe-input rejection. "
        f"math.run advertises 31 input variants in {run_schema_bytes} bytes; "
        f"its result contract is {run_output_schema_bytes} bytes; "
        f"compact math.batch input is {batch_schema_bytes} bytes and all four listed tools total {listed_bytes} bytes; "
        f"five warm expression calls completed in {warm_elapsed:.3f}s."
    )


if __name__ == "__main__":
    asyncio.run(main())
