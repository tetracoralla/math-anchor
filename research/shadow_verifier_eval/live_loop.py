"""Authorized live B0/B1 execution loop.

Counts each backend.complete() as one paid call against --confirm-model-runs N.
B1 may use several calls per cell for voluntary tool turns. Remaining cells
stay deferred when the cap is hit. Invents no quality deltas, dollars, or
savings percentages.
"""

from __future__ import annotations

import sys
from typing import Any

from math_anchor.errors import CalculatorError

from .live_grade import grade_live_task, parse_verdict
from .mcp_inprocess import (
    chat_tool_definitions,
    dispatch_mcp_tool,
    is_target_tool,
    tool_result_text,
)
from .model_interface import deferred_cell
from .protocol import ARM_B0, ARM_B1, MCP_TOOLS
from .xai_backend import add_usage, sanitize_usage


MAX_TOOL_TURNS_PER_CELL = 4

B0_SYSTEM = (
    "You are answering a mathematical yes/no question. You have no external "
    "calculator, computer-algebra system, or proof checker. Reason from the "
    "question text alone.\n\n"
    "After your reasoning, end with exactly one of these lines and nothing after it:\n"
    "VERDICT: YES\n"
    "VERDICT: NO\n"
    "VERDICT: UNSURE\n\n"
    "YES means the claimed identity or dimensional consistency holds as stated "
    "in the question. NO means it does not hold as stated. UNSURE means you "
    "cannot decide."
)

B1_SYSTEM = (
    "You are answering a mathematical yes/no question. You may voluntarily use "
    "Math Anchor tools if they help: math.search, math.describe, math.run, and "
    "math.batch. There is no fifth tool. You may also answer without calling any "
    "tool.\n\n"
    "math.run requires {operation, arguments}. If you do not know the operation "
    "id, use math.search then math.describe. Catalog ids that may be relevant "
    "include certificate.polynomial_identity, expression.equivalent, and "
    "dimension.check. Tool results are calculation/provider output, not a proof "
    "of surrounding prose, and not an obligation-set / Host shadow checkpoint.\n\n"
    "A correct final answer without a math.run or math.batch call is not adoption "
    "of the provider.\n\n"
    "After your reasoning, end with exactly one of these lines and nothing after it:\n"
    "VERDICT: YES\n"
    "VERDICT: NO\n"
    "VERDICT: UNSURE\n\n"
    "YES means the claimed identity or dimensional consistency holds as stated "
    "in the question. NO means it does not hold as stated. UNSURE means you "
    "cannot decide."
)


class LiveCallBudget:
    """Fail-closed remaining-call counter. N is the HTTP/complete() cap."""

    def __init__(self, limit: int) -> None:
        if int(limit) <= 0:
            raise CalculatorError("E_INPUT", "--confirm-model-runs N is required with N > 0")
        self.limit = int(limit)
        self.used = 0
        self.by_arm: dict[str, int] = {}

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    def consume(self, arm_id: str) -> bool:
        if self.used >= self.limit:
            return False
        self.used += 1
        self.by_arm[arm_id] = self.by_arm.get(arm_id, 0) + 1
        return True

    def snapshot(self) -> dict[str, Any]:
        return {
            "limit": self.limit,
            "used": self.used,
            "remaining": self.remaining,
            "byArm": dict(self.by_arm),
        }


def _progress(message: str) -> None:
    sys.stderr.write(message + "\n")
    sys.stderr.flush()


def _backend_complete(backend: Any, prompt: str, **kwargs: Any) -> dict[str, Any]:
    try:
        return backend.complete(prompt, **kwargs)
    except TypeError:
        return backend.complete(
            prompt,
            arm_id=kwargs["arm_id"],
            task_id=kwargs["task_id"],
            tools=kwargs.get("tools"),
        )


def _disclosure(backend: Any) -> dict[str, Any]:
    if hasattr(backend, "disclosure"):
        payload = backend.disclosure()
        if isinstance(payload, dict):
            return payload
    return {
        "provider": getattr(backend, "provider", None),
        "model": getattr(backend, "model", None),
        "authSource": getattr(backend, "auth_source", "registered-backend"),
    }


def _budget_exhausted_cell(
    arm_id: str,
    task: dict[str, Any],
    *,
    protocol: dict[str, Any] | None,
    budget: LiveCallBudget,
    reason: str,
) -> dict[str, Any]:
    cell = deferred_cell(arm_id, task, protocol=protocol)
    cell["reason"] = reason
    cell["budgetExhausted"] = True
    cell["liveQualityDelta"] = None
    cell["finalAccuracy"] = None
    cell["dollarCost"] = None
    cell["acceptedSeededError"] = None
    cell["callBudget"] = budget.snapshot()
    return cell


def run_live_cell(
    arm_id: str,
    task: dict[str, Any],
    *,
    backend: Any,
    budget: LiveCallBudget,
    protocol: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one B0 or B1 live cell. Stops when N is exhausted. Invents no scores."""

    if arm_id not in {ARM_B0, ARM_B1}:
        raise CalculatorError("E_INPUT", f"live loop only runs B0/B1, not {arm_id}")
    prompt = task.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise CalculatorError("E_INPUT", f"task {task.get('id')!r} is missing an agent-facing prompt")

    offer_tools = arm_id == ARM_B1
    tool_names = list(MCP_TOOLS) if offer_tools else []
    tool_defs = chat_tool_definitions(tool_names) if offer_tools else None
    system = B1_SYSTEM if offer_tools else B0_SYSTEM
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    disclosure = _disclosure(backend)
    tool_trace: list[dict[str, Any]] = []
    target_calls = 0
    invoked: list[str] = []
    usage_sum: dict[str, Any] | None = None
    text = ""
    http_calls = 0
    finish_reason = None
    provider = disclosure.get("provider")
    model = disclosure.get("model")
    error_payload: dict[str, Any] | None = None

    _progress(
        f"[live] {arm_id}×{task['id']} starting (budget {budget.used}/{budget.limit})"
    )

    turns = 0
    while True:
        if not budget.consume(arm_id):
            if http_calls == 0:
                return _budget_exhausted_cell(
                    arm_id,
                    task,
                    protocol=protocol,
                    budget=budget,
                    reason="confirm-model-runs budget exhausted before this cell",
                )
            break
        try:
            result = _backend_complete(
                backend,
                prompt,
                arm_id=arm_id,
                task_id=str(task["id"]),
                tools=tool_names if offer_tools else None,
                messages=messages,
                tool_definitions=tool_defs,
            )
        except CalculatorError as error:
            error_payload = {
                "code": error.code,
                "message": error.message,
                "details": {
                    key: value
                    for key, value in (error.details or {}).items()
                    if key not in {"apiKey", "token", "refresh_token"}
                },
            }
            break
        http_calls += 1
        usage_sum = add_usage(usage_sum, result.get("usage"))
        text = result.get("text") if isinstance(result.get("text"), str) else ""
        finish_reason = result.get("finishReason")
        provider = result.get("provider") or provider
        model = result.get("model") or model
        assistant_message = result.get("assistantMessage")
        if isinstance(assistant_message, dict):
            messages.append(assistant_message)
        elif text:
            messages.append({"role": "assistant", "content": text})

        tool_calls = result.get("toolCalls") if isinstance(result.get("toolCalls"), list) else []
        if not offer_tools or not tool_calls:
            break
        if turns >= MAX_TOOL_TURNS_PER_CELL:
            tool_trace.append(
                {
                    "truncated": True,
                    "reason": f"max {MAX_TOOL_TURNS_PER_CELL} tool turns per cell",
                    "pendingToolCalls": len(tool_calls),
                }
            )
            break
        turns += 1
        for call in tool_calls:
            if not isinstance(call, dict):
                continue
            name = call.get("name")
            arguments = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
            dispatched = dispatch_mcp_tool(str(name or ""), arguments)
            invoked.append(str(dispatched.get("tool") or name))
            if dispatched.get("isTargetTool") or is_target_tool(name if isinstance(name, str) else None):
                target_calls += 1
            tool_trace.append(
                {
                    "id": call.get("id"),
                    "name": dispatched.get("tool") or name,
                    "arguments": arguments,
                    "isTargetTool": bool(dispatched.get("isTargetTool")),
                    "result": dispatched.get("result"),
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "content": tool_result_text(dispatched.get("result")),
                }
            )

    verdict = parse_verdict(text)
    graded = grade_live_task(task, verdict)
    status = "error" if error_payload is not None else "ok"
    cell = {
        "arm": arm_id,
        "task": task["id"],
        "status": status,
        "liveRan": True,
        "modelArms": "ran",
        "runnableThisSmoke": True,
        "prompt": prompt,
        "corruptionKind": task.get("corruptionKind"),
        "g1SupportedSeededError": bool(task.get("g1SupportedSeededError")),
        "g3Control": bool(task.get("g3Control")),
        "role": task.get("role"),
        "provider": provider,
        "model": model,
        "authSource": disclosure.get("authSource"),
        "reasoningEffort": disclosure.get("reasoningEffort"),
        "text": text,
        "verdict": verdict,
        "usage": usage_sum or sanitize_usage(None),
        "httpCalls": http_calls,
        "toolTurns": turns,
        "toolTrace": tool_trace,
        "mcpToolsOffered": tool_names,
        "mcpToolsInvoked": invoked,
        "targetCalls": target_calls,
        "adoption": False,
        "correctAnswerWithoutTargetCallIsNotAdoption": True,
        "targetCallMade": target_calls > 0,
        "b1ToolSurface": (
            "in-process catalog dispatch matching math.search / math.describe / "
            "math.run / math.batch; not a Host JSON-RPC MCP session; not the "
            "obligation-set envelope"
            if offer_tools
            else None
        ),
        "fifthMcpTool": False,
        "finishReason": finish_reason,
        "callBudget": budget.snapshot(),
        "coversOriginalTaskClaim": False,
        "formalKernelChecked": False,
        "liveQualityDelta": None,
        "finalAccuracy": None,
        "dollarCost": None,
        "acceptedSeededError": graded["acceptedSeededError"],
        "detected": graded["detected"],
        "falseReject": graded["falseReject"],
        "unparseable": graded["unparseable"],
        "error": error_payload,
        "honesty": {
            "oracleOutsideAgentView": True,
            "noInventedQualityDelta": True,
            "noInventedDollarCost": True,
            "noInventedSavingsPercent": True,
            "unparseableIsNotDetection": True,
            "callAloneIsNotAdoption": True,
        },
    }
    _progress(
        f"[live] {arm_id}×{task['id']} {status} verdict={verdict} "
        f"http={http_calls} budget={budget.used}/{budget.limit}"
    )
    return cell


def backend_disclosure(backend: Any) -> dict[str, Any]:
    return _disclosure(backend)
