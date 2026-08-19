"""Shared launch facts for the packaged Math Anchor MCP server.

check_mcp.py and benchmark.py both start the server exactly as the plugin
configures it and measure the compact tool listing the same way; this module
keeps the two scripts from drifting apart.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp import StdioServerParameters


def plugin_server_parameters(plugin_root: Path) -> StdioServerParameters:
    config = json.loads((plugin_root / ".mcp.json").read_text())
    server = config["mcpServers"]["math-anchor"]
    server_cwd = (plugin_root / server["cwd"]).resolve()
    command = Path(server["command"])
    if not command.is_absolute():
        command = (server_cwd / command).resolve()
    return StdioServerParameters(
        command=str(command),
        args=server.get("args", []),
        cwd=str(server_cwd),
    )


def tools_listing_bytes(tools: Any) -> int:
    payload = [tool.model_dump(by_alias=True, exclude_none=True) for tool in tools]
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode())
