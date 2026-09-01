from __future__ import annotations

import asyncio
import json
import threading

import pytest
from pydantic import ValidationError
from jsonschema import Draft202012Validator

from math_anchor.catalog import OPERATIONS, describe_operation
from math_anchor.contracts import (
    RUN_RESULT_SCHEMA,
    RUN_TOOL_OUTPUT_SCHEMA,
    _LIMIT_PROPERTIES,
    batch_tool_parameters,
    validate_result,
)
from math_anchor.errors import CalculatorError
from math_anchor import mcp_server
from math_anchor.mcp_server import _run_cancellable, _tool_result, mcp
from math_anchor.output_policy import (
    DEFAULT_BATCH_MAX_OUTPUT_BYTES,
    DEFAULT_MAX_OUTPUT_BYTES,
    MAX_OUTPUT_BYTES,
    MIN_OUTPUT_BYTES,
)
from math_anchor.runtime import execute_direct


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


def test_tool_discovery_survives_current_codex_host_compaction() -> None:
    payloads = [
        _tool_payload(name)
        for name in ("math.search", "math.describe", "math.run", "math.batch")
    ]
    listed_bytes = len(json.dumps(payloads, separators=(",", ":")).encode())
    run_tool = mcp._tool_manager.get_tool("math.run")
    assert run_tool is not None
    assert "one successful ordinary call is sufficient" in run_tool.description
    assert "{operation, arguments}; never flatten" in run_tool.description
    assert "Known direct shapes need no describe call" in run_tool.description
    assert "integer.machine_arithmetic" in run_tool.description
    assert "combinatorics.count" in run_tool.description
    assert "certificate.polynomial_identity" in run_tool.description
    output_bytes = len(
        json.dumps(run_tool.output_schema, separators=(",", ":")).encode()
    )

    input_bytes = len(
        json.dumps(run_tool.parameters, separators=(",", ":")).encode()
    )
    assert input_bytes < 4_800
    assert not ({"oneOf", "anyOf", "allOf", "$defs"} & set(run_tool.parameters))
    assert set(run_tool.parameters["properties"]["operation"]["enum"]) == set(OPERATIONS)
    assert run_tool.parameters["properties"]["arguments"]["type"] == "object"
    assert output_bytes < 2_000
    # Codex currently applies lossy model-facing compaction above roughly 5 KB
    # per input schema. Stay below it so math.run never degrades to an opaque
    # args object in the installed host.
    assert listed_bytes < 10_000
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
    assert set(describe_tool.parameters["properties"]["operation"]["enum"]) == set(OPERATIONS)
    for name in ("math.search", "math.describe", "math.run", "math.batch"):
        tool = mcp._tool_manager.get_tool(name)
        assert tool is not None
        assert tool.parameters["additionalProperties"] is False
        with pytest.raises(ValidationError):
            tool.fn_metadata.arg_model.model_validate({"unexpected": True})


def test_ordinary_assurance_envelope_stays_small() -> None:
    spec = OPERATIONS["expression.evaluate"]
    arguments = {"expression": "6*7"}
    raw = spec.handler(arguments)
    annotated = execute_direct(spec.id, arguments)

    def encoded(value: dict) -> int:
        return len(
            json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        )

    assert encoded(annotated) < 512
    assert encoded(annotated) - encoded(raw) <= 320


def test_compact_run_output_schema_accepts_scalar_and_matrix_lanes_only() -> None:
    run_tool = mcp._tool_manager.get_tool("math.run")
    assert run_tool is not None
    validator = Draft202012Validator(run_tool.output_schema)

    for result in (
        {"status": "ok", "exact": "sqrt(2)", "approx": "1.414"},
        {
            "status": "ok",
            "exact": [["1", "0"], ["0", "1"]],
            "approx": [["1", "0"], ["0", "1"]],
        },
    ):
        assert not list(validator.iter_errors(result))

    assert list(
        validator.iter_errors({"status": "ok", "exact": {"unexpected": True}})
    )


def test_registry_preserves_every_operation_schema_behind_the_host_safe_envelope() -> None:
    run_tool = mcp._tool_manager.get_tool("math.run")
    assert run_tool is not None
    envelope_validator = Draft202012Validator(run_tool.parameters)

    for operation, spec in OPERATIONS.items():
        for arguments in spec.examples:
            request = {"operation": operation, "arguments": arguments}
            assert not list(envelope_validator.iter_errors(request)), operation
            assert not list(Draft202012Validator(spec.input_schema).iter_errors(arguments)), operation

        # The always-listed host envelope deliberately leaves the selected
        # arguments object open; the registry remains the execution authority
        # and must still reject unknown fields before engine work.
        invalid = {
            "operation": operation,
            "arguments": {**spec.examples[0], "__unexpected": True},
        }
        assert not list(envelope_validator.iter_errors(invalid)), operation
        assert list(
            Draft202012Validator(spec.input_schema).iter_errors(invalid["arguments"])
        ), operation

        # Discovery prose and the complete expanded operation schema remain
        # available on demand even though the always-listed union is compact.
        described = describe_operation(operation)["operation"]
        assert described["description"] == spec.description
        assert described["inputSchema"] == spec.input_schema

    assert list(
        envelope_validator.iter_errors(
            {"operation": "expression.evaluate", "arguments": "1+1"}
        )
    )


def test_math_run_envelope_keeps_operation_arguments_nested() -> None:
    run_tool = mcp._tool_manager.get_tool("math.run")
    assert run_tool is not None
    valid = {
        "operation": "integer.machine_arithmetic",
        "arguments": {
            "action": "add",
            "left": "250",
            "right": "20",
            "bitWidth": 8,
            "overflowBehavior": "wrapping",
        },
    }
    assert run_tool.fn_metadata.arg_model.model_validate(valid).operation == valid["operation"]
    with pytest.raises(ValidationError):
        run_tool.fn_metadata.arg_model.model_validate(valid["arguments"])


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


def test_result_validation_dispatch_keeps_the_complete_variant_contract() -> None:
    valid = execute_direct(
        "integer.machine_arithmetic",
        {
            "action": "add",
            "left": "250",
            "right": "20",
            "bitWidth": 8,
            "overflowBehavior": "wrapping",
        },
    )
    invalid = dict(valid)
    invalid.pop("overflow")

    with pytest.raises(CalculatorError, match="outside the public contract"):
        validate_result(invalid)

    # Kinds with multiple action-discriminated variants must not accept the
    # fields of a sibling action after fast dispatch.
    vector = execute_direct(
        "linear_algebra.exact",
        {"action": "dot", "left": [1, 2], "right": [3, 4]},
    )
    vector["action"] = "cross"
    with pytest.raises(CalculatorError, match="outside the public contract"):
        validate_result(vector)


def test_tool_results_signal_error_envelopes_through_is_error() -> None:
    # Negative regression: MCP reports tool execution errors (including
    # domain and input errors) through isError; host frameworks that branch
    # on it previously received every in-band error as a successful call.
    failure = _tool_result(
        {"status": "error", "error": {"code": "E_DOMAIN", "message": "division by zero"}}
    )
    assert failure.isError is True

    success = _tool_result(
        {"status": "ok", "operation": "expression.evaluate", "kind": "scalar", "exact": "42"}
    )
    assert success.isError is False

    # A partial batch is a valid batch result; per-item envelopes carry
    # their own statuses.
    partial = _tool_result({"status": "partial", "count": 1, "results": []})
    assert partial.isError is False


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


def test_mcp_ingress_fails_fast_before_the_executor_queue_can_grow(monkeypatch) -> None:
    monkeypatch.setattr(mcp_server, "_MCP_INGRESS_LIMIT", 4)
    monkeypatch.setattr(mcp_server, "_MCP_INGRESS", threading.BoundedSemaphore(4))
    release = threading.Event()
    entered = 0
    entered_lock = threading.Lock()

    def blocking(*, cancel_event: threading.Event) -> dict:
        nonlocal entered
        with entered_lock:
            entered += 1
        release.wait(timeout=2)
        return {"status": "ok"}

    async def scenario() -> None:
        tasks = [asyncio.create_task(_run_cancellable(blocking)) for _ in range(4)]
        deadline = asyncio.get_running_loop().time() + 1
        while entered < 4 and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.005)
        assert entered == 4
        overloaded = await _run_cancellable(blocking)
        assert overloaded["error"]["code"] == "E_OVERLOADED"
        assert overloaded["error"]["retryable"] is True
        assert overloaded["error"]["phase"] == "admission"
        release.set()
        assert all(result["status"] == "ok" for result in await asyncio.gather(*tasks))

    asyncio.run(scenario())


def test_cancelled_mcp_call_holds_ingress_until_its_thread_drains(monkeypatch) -> None:
    monkeypatch.setattr(mcp_server, "_MCP_INGRESS_LIMIT", 1)
    monkeypatch.setattr(mcp_server, "_MCP_INGRESS", threading.BoundedSemaphore(1))
    allow_drain = threading.Event()
    drained = threading.Event()

    def slow_cancel(*, cancel_event: threading.Event) -> dict:
        cancel_event.wait(timeout=1)
        allow_drain.wait(timeout=1)
        drained.set()
        return {"status": "error"}

    def immediate(*, cancel_event: threading.Event) -> dict:
        return {"status": "ok"}

    async def scenario() -> None:
        task = asyncio.create_task(_run_cancellable(slow_cancel))
        await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        still_full = await _run_cancellable(immediate)
        assert still_full["error"]["code"] == "E_OVERLOADED"
        allow_drain.set()
        assert await asyncio.to_thread(drained.wait, 1)
        await asyncio.sleep(0)
        assert await _run_cancellable(immediate) == {"status": "ok"}

    asyncio.run(scenario())
