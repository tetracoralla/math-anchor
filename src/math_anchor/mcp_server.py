from __future__ import annotations

import asyncio
import threading
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp import server as fastmcp_server
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field, WithJsonSchema

from .catalog import (
    MAX_CATEGORY_LENGTH,
    MAX_OPERATION_ID_LENGTH,
    MAX_SEARCH_QUERY_LENGTH,
    describe_operation,
    operation_schemas,
    search_operations,
)
from .contracts import BATCH_RESULT_SCHEMA, RUN_TOOL_OUTPUT_SCHEMA, batch_item_parameters, batch_tool_parameters, run_tool_parameters
from .errors import CalculatorError
from .output_policy import DEFAULT_BATCH_MAX_OUTPUT_BYTES, DEFAULT_MAX_OUTPUT_BYTES
from .sandbox import run_batch, run_operation


_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

# PyInstaller freezes the postponed annotations used by FastMCP's Settings
# model before pydantic-settings can always resolve them itself. Rebuild with
# the owning module namespace so packaged stdio startup stays warning-free.
fastmcp_server.Settings.model_rebuild(
    force=True,
    _types_namespace=vars(fastmcp_server),
)

mcp = FastMCP(
    "Math Anchor",
    instructions=(
        "Use this runtime instead of mentally simulating arithmetic or scientific algorithms. "
        "For ordinary supported requests, call math.run directly using its operation-specific typed schema. "
        "Use search and describe only when the operation is genuinely unfamiliar or ambiguous. "
        "Preserve the distinction between exact and approximate results."
    ),
)


def _caught(callable_: Any, *arguments: Any) -> dict[str, Any]:
    try:
        return callable_(*arguments)
    except CalculatorError as error:
        return {"status": "error", "error": error.as_dict()}


@mcp.tool(
    name="math.search",
    title="Search mathematical operations",
    description="Search the compact operation catalog by task language and optional category. Use before math.describe when the operation id is not already known.",
    annotations=_READ_ONLY,
    structured_output=True,
)
def math_search(
    query: Annotated[str, Field(max_length=MAX_SEARCH_QUERY_LENGTH)] = "",
    category: Annotated[str | None, Field(max_length=MAX_CATEGORY_LENGTH)] = None,
) -> dict[str, Any]:
    return _caught(search_operations, query, category)


@mcp.tool(
    name="math.describe",
    title="Describe a mathematical operation",
    description="Return the exact input schema and examples for an unfamiliar operation selected from math.search.",
    annotations=_READ_ONLY,
    structured_output=True,
)
def math_describe(
    operation: Annotated[
        str,
        Field(min_length=1, max_length=MAX_OPERATION_ID_LENGTH),
    ],
) -> dict[str, Any]:
    return _caught(describe_operation, operation)


@mcp.tool(
    name="math.run",
    title="Run a mathematical operation",
    description="Calculate, solve, differentiate, integrate, convert units, or run another supported mathematical operation in one typed call. Each operation validates its own arguments and returns exact and approximate values separately.",
    annotations=_READ_ONLY,
    structured_output=True,
)
async def math_run(
    operation: str,
    arguments: dict[str, Any],
    timeoutMs: int = 10_000,
    memoryMb: int = 1024,
    resultMode: str = "auto",
    maxOutputBytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> CallToolResult:
    result = await _run_cancellable(
        run_operation,
        operation,
        arguments,
        timeout_ms=timeoutMs,
        memory_mb=memoryMb,
        result_mode=resultMode,
        max_output_bytes=maxOutputBytes,
    )
    return _tool_result(result)


@mcp.tool(
    name="math.batch",
    title="Run mathematical operations in a batch",
    description="Run 1 to 32 independent operations in input order. Each item has operation, arguments, and optional timeoutMs or memoryMb.",
    annotations=_READ_ONLY,
    structured_output=True,
)
async def math_batch(
    items: Annotated[list[Any], Field(min_length=1, max_length=32), WithJsonSchema({
        "type": "array",
        "minItems": 1,
        "maxItems": 32,
        "items": batch_item_parameters(),
    })],
    timeoutMs: int = 30_000,
    maxOutputBytes: int = DEFAULT_BATCH_MAX_OUTPUT_BYTES,
) -> CallToolResult:
    return _tool_result(
        await _run_cancellable(
            run_batch,
            items,
            timeout_ms=timeoutMs,
            max_output_bytes=maxOutputBytes,
        )
    )


async def _run_cancellable(callable_: Any, *arguments: Any, **keywords: Any) -> dict[str, Any]:
    cancel_event = threading.Event()
    worker = asyncio.create_task(
        asyncio.to_thread(
            callable_,
            *arguments,
            cancel_event=cancel_event,
            **keywords,
        )
    )
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        # The request was cancelled at the transport. Cleanup — killing the
        # active child and returning the pool worker — continues on the
        # executor thread once the event is set; under anyio (FastMCP's
        # runtime) every await inside this handler is immediately
        # re-cancelled, so deliberately do not wait for the drain here.
        cancel_event.set()
        raise


def _tool_result(result: dict[str, Any]) -> CallToolResult:
    if result.get("status") == "error":
        error = result.get("error", {})
        summary = f"{error.get('code', 'E_RUNTIME')}: {error.get('message', 'Calculation failed')}"
    else:
        summary = f"{result.get('status', 'ok')}: {result.get('operation', 'math.batch')}"
    return CallToolResult(
        content=[TextContent(type="text", text=summary)],
        structuredContent=result,
        isError=False,
    )


def _install_generated_tool_contracts() -> None:
    schemas = operation_schemas()
    search_tool = mcp._tool_manager.get_tool("math.search")
    describe_tool = mcp._tool_manager.get_tool("math.describe")
    run_tool = mcp._tool_manager.get_tool("math.run")
    batch_tool = mcp._tool_manager.get_tool("math.batch")
    tools = (search_tool, describe_tool, run_tool, batch_tool)
    if any(tool is None for tool in tools):
        raise RuntimeError("calculator MCP tools were not registered")
    assert search_tool is not None
    assert describe_tool is not None
    assert run_tool is not None
    assert batch_tool is not None
    search_tool.parameters["additionalProperties"] = False
    describe_tool.parameters["additionalProperties"] = False
    run_tool.parameters = run_tool_parameters(schemas)
    run_tool.__dict__["output_schema"] = RUN_TOOL_OUTPUT_SCHEMA
    batch_tool.parameters = batch_tool_parameters()
    batch_tool.__dict__["output_schema"] = BATCH_RESULT_SCHEMA
    for tool in (search_tool, describe_tool, run_tool, batch_tool):
        # FastMCP's generated pydantic models otherwise ignore unexpected
        # top-level keys even when the advertised JSON Schema is closed.
        tool.fn_metadata.arg_model.model_config["extra"] = "forbid"
        tool.fn_metadata.arg_model.model_rebuild(force=True)


_install_generated_tool_contracts()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
