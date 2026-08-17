from __future__ import annotations

import asyncio
import json
import threading

import pytest
from pydantic import ValidationError

from math_anchor.contracts import (
    RUN_RESULT_SCHEMA,
    RUN_TOOL_OUTPUT_SCHEMA,
    _LIMIT_PROPERTIES,
    batch_tool_parameters,
)
from math_anchor.mcp_server import _run_cancellable, mcp
from math_anchor.output_policy import (
    DEFAULT_BATCH_MAX_OUTPUT_BYTES,
    DEFAULT_MAX_OUTPUT_BYTES,
    MAX_OUTPUT_BYTES,
    MIN_OUTPUT_BYTES,
)


def _tool_payload(name: str) -> dict:
    tool = mcp._tool_manager.get_tool(name)
    assert tool is not None
    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": tool.parameters,
        "outputSchema": tool.output_schema,
        "annotations": (
            tool.annotations.model_dump(by_alias=True, exclude_none=True)
            if tool.annotations
            else None
        ),
    }


def test_tool_discovery_keeps_the_full_input_contract_without_republishing_every_result_kind() -> None:
    payloads = [
        _tool_payload(name)
        for name in ("math.search", "math.describe", "math.run", "math.batch")
    ]
    listed_bytes = len(json.dumps(payloads, separators=(",", ":")).encode())
    run_tool = mcp._tool_manager.get_tool("math.run")
    assert run_tool is not None
    assert "One successful ordinary call is sufficient" in run_tool.description
    output_bytes = len(
        json.dumps(run_tool.output_schema, separators=(",", ":")).encode()
    )

    assert len(run_tool.parameters["oneOf"]) == 31
    assert output_bytes < 2_000
    assert listed_bytes < 40_000
    assert run_tool.parameters["properties"]["maxOutputBytes"]["default"] == DEFAULT_MAX_OUTPUT_BYTES
    batch_tool = mcp._tool_manager.get_tool("math.batch")
    assert batch_tool is not None
    assert batch_tool.parameters["properties"]["maxOutputBytes"]["default"] == DEFAULT_BATCH_MAX_OUTPUT_BYTES
    assert len(RUN_RESULT_SCHEMA["oneOf"]) >= 6
    search_tool = mcp._tool_manager.get_tool("math.search")
    describe_tool = mcp._tool_manager.get_tool("math.describe")
    assert search_tool is not None
    assert describe_tool is not None
    assert search_tool.parameters["properties"]["query"]["maxLength"] == 256
    assert search_tool.parameters["properties"]["category"]["anyOf"][0]["maxLength"] == 64
    assert describe_tool.parameters["properties"]["operation"]["maxLength"] == 128
    for name in ("math.search", "math.describe", "math.run", "math.batch"):
        tool = mcp._tool_manager.get_tool(name)
        assert tool is not None
        assert tool.parameters["additionalProperties"] is False
        with pytest.raises(ValidationError):
            tool.fn_metadata.arg_model.model_validate({"unexpected": True})


def test_advertised_budgets_match_executed_defaults() -> None:
    # The schema a client reads must agree with what the sandbox actually
    # enforces; the defaults are defined once in output_policy.
    limits = _LIMIT_PROPERTIES["maxOutputBytes"]
    assert limits["minimum"] == MIN_OUTPUT_BYTES
    assert limits["maximum"] == MAX_OUTPUT_BYTES
    assert limits["default"] == DEFAULT_MAX_OUTPUT_BYTES
    batch_parameters = batch_tool_parameters()
    batch_limits = batch_parameters["properties"]["maxOutputBytes"]
    assert batch_limits["minimum"] == MIN_OUTPUT_BYTES
    assert batch_limits["maximum"] == MAX_OUTPUT_BYTES
    assert batch_limits["default"] == DEFAULT_BATCH_MAX_OUTPUT_BYTES
    item_limits = batch_parameters["properties"]["items"]["items"]["properties"]["maxOutputBytes"]
    assert item_limits == limits
    assert batch_parameters["properties"]["timeoutMs"]["default"] == 30_000


def test_advertised_result_envelope_stays_a_projection_of_the_result_union() -> None:
    # Clients validate every structured result against the advertised
    # envelope; if the union grows a status value or a new common field that
    # the envelope does not know, calls start failing client-side.
    union_statuses: set[str] = set()
    for variant in RUN_RESULT_SCHEMA["oneOf"]:
        status = variant["properties"]["status"]
        if "enum" in status:
            union_statuses.update(status["enum"])
        else:
            union_statuses.add(status["const"])
    advertised = RUN_TOOL_OUTPUT_SCHEMA["properties"]["status"]["enum"]
    assert set(advertised) == union_statuses
    common_required = set.intersection(
        *(set(variant["required"]) for variant in RUN_RESULT_SCHEMA["oneOf"])
    )
    missing = common_required - set(RUN_TOOL_OUTPUT_SCHEMA["properties"])
    assert not missing, f"envelope dropped common result fields: {sorted(missing)}"


def test_async_mcp_boundary_signals_cancellation_to_blocking_execution() -> None:
    execution_stopped = threading.Event()

    def blocking(*, cancel_event: threading.Event) -> dict:
        cancel_event.wait(timeout=2)
        execution_stopped.set()
        return {"status": "error", "error": {"code": "E_CANCELLED", "message": "cancelled"}}

    async def scenario() -> None:
        task = asyncio.create_task(_run_cancellable(blocking))
        await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert await asyncio.to_thread(execution_stopped.wait, 1)

    asyncio.run(scenario())
