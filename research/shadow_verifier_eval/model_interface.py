"""B0/B1 live-model interfaces. Not executed in this smoke.

This module records the matched four-arm contract for a later paid run.
It does not call a model, does not invent quality deltas, and rejects
`--include-model-arms` until a real runner exists.
"""

from __future__ import annotations

from typing import Any

from math_anchor.errors import CalculatorError

from .protocol import (
    ARM_B0,
    ARM_B1,
    DEFERRED_ARMS,
    MCP_TOOLS,
    MODEL_ARMS_DEFERRED,
    live_model_commands,
)


class ModelArmDeferredError(CalculatorError):
    """Live B0/B1 arms are not implemented in this scaffold."""


def model_arm_contract(arm_id: str) -> dict[str, Any]:
    if arm_id == ARM_B0:
        return {
            "id": ARM_B0,
            "mathProvider": None,
            "mcpTools": [],
            "hostShadowCheckpoint": False,
            "obligationRuntime": False,
            "grading": (
                "Controller-owned oracle; expected answers stay outside the "
                "evaluated Agent. Final accept/reject or scalar answer only."
            ),
            "records": [
                "schemaOrCarrierBytes",
                "routingTokens",
                "toolTurns",
                "returnedFeedbackBytes",
                "repairTokens",
                "finalAccuracy",
                "acceptedSeededErrors",
            ],
            "note": "No mathematical provider. A correct guess is not verification.",
        }
    if arm_id == ARM_B1:
        return {
            "id": ARM_B1,
            "mathProvider": "mcp-voluntary",
            "mcpTools": list(MCP_TOOLS),
            "fifthMcpTool": False,
            "hostShadowCheckpoint": False,
            "obligationRuntime": False,
            "correctAnswerWithoutTargetCallIsNotAdoption": True,
            "grading": (
                "Same oracle as B0. Record whether a target MCP tool was actually "
                "invoked. Voluntary use: the model may ignore the tools."
            ),
            "records": [
                "schemaOrCarrierBytes",
                "routingTokens",
                "toolTurns",
                "targetCalls",
                "returnedFeedbackBytes",
                "repairTokens",
                "finalAccuracy",
                "acceptedSeededErrors",
            ],
            "note": (
                "Current four-tool MCP compatibility surface only. A correct "
                "final answer without a target call is not adoption."
            ),
        }
    raise ModelArmDeferredError("E_INPUT", f"unknown deferred model arm: {arm_id}")


def deferred_cell(arm_id: str, task: dict[str, Any], *, protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    if arm_id not in DEFERRED_ARMS:
        raise ModelArmDeferredError("E_INPUT", f"{arm_id} is not a deferred model arm")
    commands = live_model_commands(protocol)
    return {
        "arm": arm_id,
        "task": task["id"],
        "status": MODEL_ARMS_DEFERRED,
        "modelArms": MODEL_ARMS_DEFERRED,
        "runnableThisSmoke": False,
        "prompt": task.get("prompt"),
        "corruptionKind": task.get("corruptionKind"),
        "g1SupportedSeededError": bool(task.get("g1SupportedSeededError")),
        "reason": (
            "no paid model calls in this environment; live four-arm evidence "
            "is not invented"
        ),
        "interface": model_arm_contract(arm_id),
        "laterCommand": commands.get("plannedLiveFourArm"),
        "laterCommandNote": commands.get("plannedLiveFourArmNote"),
        "liveQualityDelta": None,
        "acceptedSeededError": None,
        "finalAccuracy": None,
    }


def reject_include_model_arms(*, protocol: dict[str, Any] | None = None) -> None:
    commands = live_model_commands(protocol)
    raise ModelArmDeferredError(
        "E_INPUT",
        commands.get("includeModelArmsRejectedBecause")
        or "live B0/B1 runner is not implemented; model_arms=deferred",
        {
            "modelArms": MODEL_ARMS_DEFERRED,
            "plannedCommand": commands.get("plannedLiveFourArm"),
            "note": commands.get("plannedLiveFourArmNote"),
        },
    )
