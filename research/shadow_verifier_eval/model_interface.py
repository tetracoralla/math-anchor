"""B0/B1 live-model interfaces. Not executed without budget + backend.

Default smoke keeps B0/B1 deferred. Authorized `--include-model-arms`
executes live cells via a registered LiveModelBackend. This module still
invents no quality deltas, dollars, or savings percentages.
"""

from __future__ import annotations

from typing import Any

from math_anchor.errors import CalculatorError

from .live_runner import (
    ModelArmNotReadyError,
    reject_or_require_live_arms,
)
from .protocol import (
    ARM_B0,
    ARM_B1,
    DEFERRED_ARMS,
    MCP_TOOLS,
    MODEL_ARMS_DEFERRED,
    live_model_commands,
)


class ModelArmDeferredError(CalculatorError):
    """Live B0/B1 arms are deferred / fail-closed in this scaffold."""


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
        "emitLivePlanCommand": commands.get("emitLivePlan"),
        "liveQualityDelta": None,
        "acceptedSeededError": None,
        "finalAccuracy": None,
        "dollarCost": None,
    }


def reject_include_model_arms(
    *,
    protocol: dict[str, Any] | None = None,
    confirm_live_budget: bool = False,
    confirm_model_runs: int | None = None,
) -> None:
    """Fail-closed gate for --include-model-arms.

    Raises unless budget confirm, N>0, and a LiveModelBackend are present.
    When those hold, returns so the live loop can run. Does not invent numbers.
    """

    try:
        reject_or_require_live_arms(
            include_model_arms=True,
            confirm_live_budget=confirm_live_budget,
            confirm_model_runs=confirm_model_runs,
            protocol=protocol,
        )
    except ModelArmNotReadyError as error:
        # Surface as ModelArmDeferredError for existing callers/tests.
        raise ModelArmDeferredError(error.code, error.message, error.details) from error
