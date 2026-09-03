#!/usr/bin/env python3
from __future__ import annotations

import json

from math_anchor import __version__
from math_anchor.mcp_server import mcp
from math_anchor.obligations import (
    OBLIGATION_SET_SCHEMA_VERSION,
    check_obligation_set,
    obligation_request_schema,
)
from math_anchor.sandbox import run_operation


def _bytes(value: object) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def _tool_payload(name: str) -> dict[str, object]:
    tool = mcp._tool_manager.get_tool(name)
    if tool is None:
        raise SystemExit(f"missing MCP tool: {name}")
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


def main() -> None:
    claims = [
        {
            "id": "identity",
            "kind": "polynomial_identity",
            "claim": {
                "left": "(x + 1)^2",
                "right": "x^2 + 2*x + 1",
                "variables": ["x"],
            },
        },
        {
            "id": "dimension",
            "kind": "dimension_consistency",
            "claim": {
                "left": "force",
                "right": "mass * acceleration",
                "symbols": {
                    "force": "newton",
                    "mass": "kilogram",
                    "acceleration": "meter / second^2",
                },
            },
        },
    ]
    obligation_request = {
        "schemaVersion": OBLIGATION_SET_SCHEMA_VERSION,
        "obligations": claims,
    }
    feedback, receipt = check_obligation_set(obligation_request)
    direct_requests = [
        {
            "tool": "math.run",
            "arguments": {
                "operation": "certificate.polynomial_identity",
                "arguments": claims[0]["claim"],
            },
        },
        {
            "tool": "math.run",
            "arguments": {
                "operation": "dimension.check",
                "arguments": claims[1]["claim"],
            },
        },
    ]
    direct_results = [
        run_operation(request["arguments"]["operation"], request["arguments"]["arguments"])
        for request in direct_requests
    ]
    falsified_request = {
        "schemaVersion": OBLIGATION_SET_SCHEMA_VERSION,
        "obligations": [
            {
                "id": "sign-error",
                "kind": "polynomial_identity",
                "claim": {
                    "left": "(x + 1)^2",
                    "right": "x^2 - 2*x + 1",
                    "variables": ["x"],
                },
            }
        ],
    }
    falsified_feedback, _falsified_receipt = check_obligation_set(falsified_request)
    tool_envelope = [
        _tool_payload(name)
        for name in ("math.search", "math.describe", "math.run", "math.batch")
    ]
    report = {
        "schemaVersion": "math-anchor.obligation-cost-measurement.v0.1",
        "runtime": {"name": "math-anchor", "version": __version__},
        "status": "measured",
        "schema": {
            "mcpFourToolEnvelopeBytes": _bytes(tool_envelope),
            "localObligationRequestSchemaBytes": _bytes(obligation_request_schema()),
            "modelContextInterpretation": (
                "The local obligation schema is a harness contract and need not be placed in the model context."
            ),
        },
        "routing": {
            "tokens": None,
            "reason": "No Agent or authoritative Host routing event is part of this deterministic measurement.",
        },
        "request": {
            "directTwoMathRunBytes": _bytes(direct_requests),
            "obligationSetBytes": _bytes(obligation_request),
        },
        "result": {
            "directTwoResultBytes": _bytes(direct_results),
            "fullReceiptBytes": _bytes(receipt),
            "failuresOnlySuccessFeedbackBytes": _bytes(feedback),
            "quietSuccessStdoutBytes": 0,
            "oneFalsifiedFeedbackBytes": _bytes(falsified_feedback),
        },
        "repair": {
            "tokens": None,
            "reason": "Repair cost requires a matched Agent workflow after actionable feedback.",
        },
        "claimBoundary": (
            "These are current encoded-byte observations for one fixed two-claim case, not token, adoption, "
            "latency, throughput, or utility measurements."
        ),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
