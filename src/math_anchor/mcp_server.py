from __future__ import annotations

import asyncio
import sys
import threading
from typing import Annotated, Any

import anyio
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp import server as fastmcp_server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field, WithJsonSchema

from . import __version__
from .catalog import (
    MAX_CATEGORY_LENGTH,
    MAX_OPERATION_ID_LENGTH,
    MAX_SEARCH_QUERY_LENGTH,
    describe_operation,
    operation_schemas,
    search_operations,
)
from .contracts import (
    BATCH_RESULT_SCHEMA,
    RUN_TOOL_OUTPUT_SCHEMA,
    batch_item_parameters,
    batch_tool_parameters,
    describe_tool_parameters,
    run_tool_parameters,
)
from .errors import CalculatorError, error_payload
from .output_policy import DEFAULT_BATCH_MAX_OUTPUT_BYTES, DEFAULT_MAX_OUTPUT_BYTES
from .runtime_control import MAX_ACTIVE_REQUESTS, MAX_QUEUED_REQUESTS
from .runtime_telemetry import RUNTIME_TELEMETRY
from .sandbox import run_batch, run_operation, warm_worker_pool
from .transport_budget import MAX_BATCH_REQUEST_BYTES


_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
_MCP_INGRESS_LIMIT = MAX_ACTIVE_REQUESTS + MAX_QUEUED_REQUESTS
_MCP_INGRESS = threading.BoundedSemaphore(_MCP_INGRESS_LIMIT)
MAX_MCP_MESSAGE_BYTES = MAX_BATCH_REQUEST_BYTES + 1024 * 1024
_OVERSIZED_MCP_SENTINEL = "<math-anchor-mcp-message-limit>\n"


class _BoundedMCPInput:
    def __init__(self, binary_stream: Any, max_bytes: int = MAX_MCP_MESSAGE_BYTES) -> None:
        self.stream = binary_stream
        self.max_bytes = max_bytes

    def __aiter__(self) -> "_BoundedMCPInput":
        return self

    async def __anext__(self) -> str:
        line = await self._readline()
        if not line:
            raise StopAsyncIteration
        if len(line) > self.max_bytes:
            while line and not line.endswith(b"\n"):
                line = await self._readline()
            # The SDK turns this bounded invalid line into its normal JSON-RPC
            # parse error. The original oversized body never reaches its JSON
            # parser, and draining it keeps the next message aligned.
            return _OVERSIZED_MCP_SENTINEL
        return line.decode("utf-8", "replace")

    async def _readline(self) -> bytes:
        return await anyio.to_thread.run_sync(
            self.stream.readline,
            self.max_bytes + 1,
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
        "Use for reliability-sensitive mathematics, not trivial arithmetic. "
        "Call math.run directly when the operation is known; search and describe only when needed. "
        "Keep exact and approximate results distinct and stop after one successful ordinary call."
    ),
)
# FastMCP 1.x otherwise reports the MCP SDK version as the server version.
# Bind the initialized server identity to this provider release instead.
mcp._mcp_server.version = __version__


def _caught(callable_: Any, *arguments: Any) -> dict[str, Any]:
    try:
        return callable_(*arguments)
    except CalculatorError as error:
        return {"status": "error", "error": error.as_dict()}


@mcp.tool(
    name="math.run",
    title="Run a mathematical operation",
    description=(
        "Use for exact or reliability-sensitive mathematics, especially fixed-width overflow and bits, "
        "IEEE-754, named rounding or division conventions, large integers, matrices, units and dimensions, "
        "uncertainty, probability, numerical methods, or finance. Do not use for trivial low-risk arithmetic. "
        "Always pass operation-specific fields inside the arguments object: {operation, arguments}; never flatten them. "
        "Known direct shapes: integer.machine_arithmetic arguments include action, left, right, "
        "bitWidth, signedness, inputMode (value or bits), and overflowBehavior (checked, wrapping, or saturating); left and right "
        "must be exact integer text strings (for example \"65535\", not 65535); "
        "do not substitute decimal or wrap. combinatorics.count arguments use action, n, and k; "
        "certificate.polynomial_identity arguments use left, right, and variables. "
        "The typed operation keeps exact and approximate results separate; one successful ordinary call is sufficient."
    ),
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
    description="Run 1 to 32 independent operations in order with per-item limits.",
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


@mcp.tool(
    name="math.search",
    title="Search mathematical operations",
    description=(
        "Search operations only when the id is unknown; otherwise use math.run. "
        "matchStatus=no_registered_operation means the catalog does not support the requested domain; "
        "do not substitute a lexical near-match."
    ),
    annotations=_READ_ONLY,
    structured_output=True,
)
def math_search(
    query: Annotated[str, Field(max_length=MAX_SEARCH_QUERY_LENGTH)] = "",
    category: Annotated[str | None, Field(max_length=MAX_CATEGORY_LENGTH)] = None,
) -> CallToolResult:
    return _tool_result(
        _caught(search_operations, query, category),
        operation_label="math.search",
    )


@mcp.tool(
    name="math.describe",
    title="Describe a mathematical operation",
    description=(
        "Get schema and argument examples only for one unfamiliar operation selected by math.search. "
        "Do not call this for known integer.machine_arithmetic or combinatorics.count shapes. "
        "Examples are arguments objects; nest one under math.run.arguments and pass its id as math.run.operation."
    ),
    annotations=_READ_ONLY,
    structured_output=True,
)
def math_describe(
    operation: Annotated[
        str,
        Field(min_length=1, max_length=MAX_OPERATION_ID_LENGTH),
    ],
) -> CallToolResult:
    return _tool_result(
        _caught(describe_operation, operation),
        operation_label="math.describe",
    )


async def _run_cancellable(callable_: Any, *arguments: Any, **keywords: Any) -> dict[str, Any]:
    if not _MCP_INGRESS.acquire(blocking=False):
        RUNTIME_TELEMETRY.increment("mcp.ingressOverloaded")
        return {
            "status": "error",
            "error": error_payload(
                "E_OVERLOADED",
                "MCP calculation ingress is full; retry after the current burst",
                {"inflightLimit": _MCP_INGRESS_LIMIT},
                phase="admission",
                retry_after_ms=100,
            ),
        }
    cancel_event = threading.Event()
    released = False

    def release_ingress(_completed: asyncio.Task[dict[str, Any]] | None = None) -> None:
        nonlocal released
        if not released:
            released = True
            _MCP_INGRESS.release()

    try:
        worker = asyncio.create_task(
            asyncio.to_thread(
                callable_,
                *arguments,
                cancel_event=cancel_event,
                **keywords,
            )
        )
    except BaseException:
        release_ingress()
        raise
    try:
        result = await asyncio.shield(worker)
        release_ingress()
        return result
    except asyncio.CancelledError:
        # The request was cancelled at the transport. Cleanup — killing the
        # active child and returning the pool worker — continues on the
        # executor thread once the event is set; under anyio (FastMCP's
        # runtime) every await inside this handler is immediately
        # re-cancelled, so deliberately do not wait for the drain here.
        cancel_event.set()
        # Do not free ingress while the executor thread still owns its worker;
        # otherwise a cancellation storm can exceed the advertised in-flight
        # bound even though every request appears cancelled to its caller.
        worker.add_done_callback(release_ingress)
        raise
    except BaseException:
        release_ingress()
        raise


def _tool_result(
    result: dict[str, Any],
    *,
    operation_label: str | None = None,
) -> CallToolResult:
    failed = result.get("status") == "error"
    if failed:
        error = result.get("error", {})
        summary = f"{error.get('code', 'E_RUNTIME')}: {error.get('message', 'Calculation failed')}"
    else:
        summary = (
            f"{result.get('status', 'ok')}: "
            f"{operation_label or result.get('operation', 'math.batch')}"
        )
    return CallToolResult(
        content=[TextContent(type="text", text=summary)],
        structuredContent=result,
        # MCP reports tool execution errors — including domain and input
        # errors — through isError so host frameworks cannot mistake a failed
        # call for a successful one. A partial batch is a valid batch result;
        # its per-item envelopes carry their own statuses.
        isError=failed,
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
    describe_tool.parameters = describe_tool_parameters(schemas)
    run_tool.__dict__["output_schema"] = RUN_TOOL_OUTPUT_SCHEMA
    batch_tool.parameters = batch_tool_parameters()
    batch_tool.__dict__["output_schema"] = BATCH_RESULT_SCHEMA
    # CallToolResult keeps protocol-level isError aligned with every tool's
    # structured status. Discovery payloads intentionally retain their compact,
    # open result shape rather than advertising the MCP envelope itself.
    discovery_output_schema = {"type": "object", "additionalProperties": True}
    search_tool.__dict__["output_schema"] = discovery_output_schema
    describe_tool.__dict__["output_schema"] = discovery_output_schema
    for tool in (search_tool, describe_tool, run_tool, batch_tool):
        # FastMCP's generated pydantic models otherwise ignore unexpected
        # top-level keys even when the advertised JSON Schema is closed.
        tool.fn_metadata.arg_model.model_config["extra"] = "forbid"
        tool.fn_metadata.arg_model.model_rebuild(force=True)


_install_generated_tool_contracts()


def main() -> None:
    # Overlap one worker's startup with client initialization so the first
    # calculation does not pay it once the session is already interactive.
    warm_worker_pool()
    anyio.run(_run_bounded_stdio)


async def _run_bounded_stdio() -> None:
    bounded_stdin = _BoundedMCPInput(sys.stdin.buffer)
    async with stdio_server(stdin=bounded_stdin) as (read_stream, write_stream):
        await mcp._mcp_server.run(
            read_stream,
            write_stream,
            mcp._mcp_server.create_initialization_options(),
        )


if __name__ == "__main__":
    main()
