from __future__ import annotations

from io import BytesIO

import anyio

from math_anchor.mcp_server import _BoundedMCPInput, _OVERSIZED_MCP_SENTINEL


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
