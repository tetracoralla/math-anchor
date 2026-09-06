from __future__ import annotations

from io import BytesIO

import anyio

from math_anchor.mcp_server import _BoundedMCPInput, _OVERSIZED_MCP_SENTINEL
from math_anchor.mcp_server import _tool_result


def test_partial_batch_reports_item_failures_without_discarding_results() -> None:
    payload = {"status": "partial", "count": 3, "results": [
        {"status": "ok", "exact": "private calculation value"},
        {"status": "error", "error": {"code": "E_TIMEOUT", "message": "private input"}},
        {"status": "error", "error": {"code": "E_CANCELLED", "message": "private input"}},
    ]}
    response = _tool_result(payload, batch=True).model_dump(by_alias=True)
    assert response["isError"] is False
    assert response["structuredContent"] == payload
    outcome = response["_meta"]["io.openadam.executionOutcome.v1"]
    assert outcome == {
        "status": "partial",
        "items": {"total": 3, "completed": 1, "errors": 1, "cancelled": 1, "unknown": 0},
        "errorCodes": [{"code": "E_CANCELLED", "count": 1}, {"code": "E_TIMEOUT", "count": 1}],
    }
    assert "private" not in str(outcome)


def test_single_error_and_discovery_outcomes_remain_distinct() -> None:
    error = _tool_result({"status": "error", "error": {"code": "E_INPUT", "message": "private"}})
    assert error.isError
    assert error.meta["io.openadam.executionOutcome.v1"]["status"] == "error"
    discovery = _tool_result({"operations": []})
    assert discovery.meta["io.openadam.executionOutcome.v1"] == {
        "status": "completed", "items": None, "errorCodes": [],
    }


def test_mcp_input_discards_oversized_line_and_recovers_alignment() -> None:
    async def scenario() -> None:
        source = BytesIO(b"x" * 33 + b"\n" + b'{"jsonrpc":"2.0"}\n')
        bounded = _BoundedMCPInput(source, max_bytes=32)

        assert await anext(bounded) == _OVERSIZED_MCP_SENTINEL
        assert await anext(bounded) == '{"jsonrpc":"2.0"}\n'

    anyio.run(scenario)


def test_bounded_stdio_depends_on_a_pinned_sdk_surface() -> None:
    # _run_bounded_stdio plugs into mcp SDK internals. If an SDK upgrade moves
    # them, fail here with the moved name instead of opaque server startup.
    from math_anchor import mcp_server

    low_level_server = mcp_server.mcp._mcp_server
    assert callable(getattr(low_level_server, "run", None))
    assert callable(getattr(low_level_server, "create_initialization_options", None))


def test_non_batch_results_and_unknown_status_are_not_reinterpreted() -> None:
    # Finance scenario comparison owns a results list of its own.
    response = _tool_result({"status": "ok", "operation": "finance.compare", "results": [{"payment": "private"}]})
    assert response.meta["io.openadam.executionOutcome.v1"] == {
        "status": "completed", "items": None, "errorCodes": [],
    }
    unknown = _tool_result({"status": "future-status"})
    assert unknown.meta["io.openadam.executionOutcome.v1"]["status"] == "unknown"
