"""In-process four-tool Math Anchor catalog surface for live B1.

Dispatches the same functions the MCP server uses (search / describe / run /
batch). This is not a JSON-RPC MCP session with a Host, not a fifth tool, and
not the obligation-set envelope (B2/B3). Voluntary: the model may ignore tools.
A correct answer without math.run / math.batch is not adoption.
"""

from __future__ import annotations

import json
from typing import Any

from math_anchor.catalog import describe_operation, search_operations
from math_anchor.errors import CalculatorError
from math_anchor.sandbox import run_batch, run_operation

from .protocol import MCP_TOOLS


TARGET_TOOL_NAMES = frozenset({"math.run", "math.batch"})
TOOL_NAME_ALIASES = {
    "math_search": "math.search",
    "math_describe": "math.describe",
    "math_run": "math.run",
    "math_batch": "math.batch",
    "math.search": "math.search",
    "math.describe": "math.describe",
    "math.run": "math.run",
    "math.batch": "math.batch",
}

MAX_TOOL_RESULT_CHARS = 12_000

_SEARCH_PARAMETERS = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "query": {
            "type": "string",
            "description": "Search text. Empty lists the catalog (optionally filtered by category).",
        },
        "category": {
            "type": "string",
            "description": "Optional catalog category filter.",
        },
    },
}

_DESCRIBE_PARAMETERS = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "operation": {
            "type": "string",
            "description": "Stable operation id from math.search (for example certificate.polynomial_identity).",
        }
    },
    "required": ["operation"],
}

_RUN_PARAMETERS = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "operation": {
            "type": "string",
            "description": "Stable operation id. Nest operation-specific fields under arguments.",
        },
        "arguments": {
            "type": "object",
            "description": (
                "Operation-specific object. certificate.polynomial_identity uses "
                "left, right, variables. expression.equivalent uses left, right, "
                "variables, optional domain and definednessPolicy. dimension.check "
                "uses left, right, and symbols mapping names to unit expressions."
            ),
        },
        "timeoutMs": {"type": "integer"},
        "memoryMb": {"type": "integer"},
        "resultMode": {"type": "string"},
        "maxOutputBytes": {"type": "integer"},
    },
    "required": ["operation", "arguments"],
}

_BATCH_PARAMETERS = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "items": {
            "type": "array",
            "minItems": 1,
            "maxItems": 32,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "operation": {"type": "string"},
                    "arguments": {"type": "object"},
                    "timeoutMs": {"type": "integer"},
                    "memoryMb": {"type": "integer"},
                    "resultMode": {"type": "string"},
                    "maxOutputBytes": {"type": "integer"},
                },
                "required": ["operation", "arguments"],
            },
        },
        "timeoutMs": {"type": "integer"},
        "maxOutputBytes": {"type": "integer"},
    },
    "required": ["items"],
}

_TOOL_DESCRIPTIONS = {
    "math.search": (
        "Search registered mathematical operations. Use when the operation id is "
        "unknown. matchStatus=no_registered_operation means the catalog does not "
        "support the requested domain; do not substitute a lexical near-match."
    ),
    "math.describe": (
        "Get schema and argument examples for one operation selected by math.search."
    ),
    "math.run": (
        "Run one registered mathematical operation. Always pass "
        "{operation, arguments}; never flatten arguments. Not an obligation-set "
        "checker and not a Host shadow checkpoint."
    ),
    "math.batch": (
        "Run 1 to 32 independent operations in order with per-item limits."
    ),
}


def normalize_tool_name(name: str | None) -> str | None:
    if not isinstance(name, str) or not name.strip():
        return None
    return TOOL_NAME_ALIASES.get(name.strip(), name.strip())


def is_target_tool(name: str | None) -> bool:
    normalized = normalize_tool_name(name)
    return normalized in TARGET_TOOL_NAMES


def chat_tool_definitions(tool_names: list[str] | None = None) -> list[dict[str, Any]]:
    """OpenAI-compatible tool schemas for the four MCP catalog tools."""

    wanted = list(tool_names) if tool_names else list(MCP_TOOLS)
    schemas = {
        "math.search": _SEARCH_PARAMETERS,
        "math.describe": _DESCRIBE_PARAMETERS,
        "math.run": _RUN_PARAMETERS,
        "math.batch": _BATCH_PARAMETERS,
    }
    tools: list[dict[str, Any]] = []
    for raw in wanted:
        name = normalize_tool_name(raw)
        if name not in schemas:
            continue
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": _TOOL_DESCRIPTIONS[name],
                    "parameters": schemas[name],
                },
            }
        )
    return tools


def _truncate_result(value: Any) -> Any:
    encoded = json.dumps(value, ensure_ascii=False, default=str)
    if len(encoded) <= MAX_TOOL_RESULT_CHARS:
        return value
    return {
        "truncated": True,
        "note": (
            "Tool result truncated for the live B1 context window. Full catalog "
            "output is not copied into the model context."
        ),
        "preview": encoded[: MAX_TOOL_RESULT_CHARS - 80],
    }


def dispatch_mcp_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    """Execute one four-tool catalog call in-process. Never invent scores."""

    normalized = normalize_tool_name(name)
    args = arguments if isinstance(arguments, dict) else {}
    try:
        if normalized == "math.search":
            result = search_operations(
                str(args.get("query") or ""),
                args.get("category"),
            )
        elif normalized == "math.describe":
            result = describe_operation(str(args.get("operation") or ""))
        elif normalized == "math.run":
            operation = str(args.get("operation") or "")
            op_args = args.get("arguments")
            if not isinstance(op_args, dict):
                raise CalculatorError("E_INPUT", "math.run requires an arguments object")
            keywords: dict[str, Any] = {}
            if "timeoutMs" in args:
                keywords["timeout_ms"] = int(args["timeoutMs"])
            if "memoryMb" in args:
                keywords["memory_mb"] = int(args["memoryMb"])
            if "resultMode" in args:
                keywords["result_mode"] = str(args["resultMode"])
            if "maxOutputBytes" in args:
                keywords["max_output_bytes"] = int(args["maxOutputBytes"])
            result = run_operation(operation, op_args, **keywords)
        elif normalized == "math.batch":
            items = args.get("items")
            if not isinstance(items, list):
                raise CalculatorError("E_INPUT", "math.batch requires an items array")
            keywords = {}
            if "timeoutMs" in args:
                keywords["timeout_ms"] = int(args["timeoutMs"])
            if "maxOutputBytes" in args:
                keywords["max_output_bytes"] = int(args["maxOutputBytes"])
            result = run_batch(items, **keywords)
        else:
            result = {
                "status": "error",
                "error": {
                    "code": "E_INPUT",
                    "message": f"unknown or disallowed tool {name!r}; only the four MCP tools are offered",
                },
            }
    except CalculatorError as error:
        result = {"status": "error", "error": error.as_dict()}
    except Exception as error:  # noqa: BLE001 — live B1 must not crash the cell
        result = {
            "status": "error",
            "error": {
                "code": "E_RUNTIME",
                "message": f"in-process tool dispatch failed: {error}",
            },
        }
    return {
        "tool": normalized or name,
        "isTargetTool": is_target_tool(normalized),
        "result": _truncate_result(result),
        "inProcessCatalogDispatch": True,
        "notHostMcpJsonRpc": True,
        "notObligationSetEnvelope": True,
    }


def tool_result_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)
