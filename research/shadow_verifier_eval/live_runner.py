"""Live four-arm runner skeleton for Epoch 2.

Fail-closed without an explicit budget confirm and a registered backend.
Does not call models by default. Does not invent quality deltas, dollars,
or savings percentages. `--emit-live-plan` writes what B0/B1/B3-live *would*
run; it is not evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import os
from typing import Any, Protocol

from math_anchor.errors import CalculatorError

from .protocol import (
    ARM_B0,
    ARM_B1,
    ARM_B3,
    DEFERRED_ARMS,
    MCP_TOOLS,
    MODEL_ARMS_DEFERRED,
    load_protocol,
    protocol_digest,
    tasks,
)


LIVE_ENV_FLAG = "MATH_ANCHOR_SHADOW_LIVE"
LIVE_PLAN_KIND = "math-anchor.research.ai-for-math-shadow-verifier-live-plan.v0"


class ModelArmNotReadyError(CalculatorError):
    """Live arms cannot run under the current fail-closed gates."""


class LiveModelBackend(Protocol):
    """Pluggable backend for a later paid run.

    Implementations must return raw model text / tool traces / usage only.
    They must not invent finalAccuracy, acceptedSeededErrors, quality deltas,
    dollar costs, or savings percentages — those stay controller-owned after
    oracle grading.
    """

    def complete(
        self,
        prompt: str,
        *,
        arm_id: str,
        task_id: str,
        tools: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run one model call. Return text + usage; invent no scores."""


_BACKEND: LiveModelBackend | None = None


def register_live_backend(backend: LiveModelBackend | None) -> None:
    """Register or clear the pluggable live-model backend."""

    global _BACKEND
    _BACKEND = backend


def registered_live_backend() -> LiveModelBackend | None:
    return _BACKEND


def backend_is_registered() -> bool:
    return _BACKEND is not None


@dataclass
class LiveTokenCostRecordSlots:
    """Null-filled slots for later G2/G4/G5/G6 accounting. Never pre-filled."""

    schemaOrCarrierBytes: int | None = None
    routingTokens: int | None = None
    toolTurns: int | None = None
    targetCalls: int | None = None
    returnedFeedbackBytes: int | None = None
    repairTokens: int | None = None
    promptTokens: int | None = None
    completionTokens: int | None = None
    totalTokens: int | None = None
    dollarCost: float | None = None
    finalAccuracy: float | None = None
    acceptedSeededErrors: int | None = None
    liveQualityDelta: float | None = None
    contextGrowthVsB0: float | None = None
    repairReachedChecked: bool | None = None
    strongWeakPairRan: bool | None = None


@dataclass
class LiveFourArmPlan:
    """Machine-readable plan of what a later live four-arm run would execute."""

    kind: str = LIVE_PLAN_KIND
    protocolDigest: str = ""
    modelArms: str = MODEL_ARMS_DEFERRED
    armsPlanned: list[str] = field(default_factory=lambda: [ARM_B0, ARM_B1, ARM_B3])
    cells: list[dict[str, Any]] = field(default_factory=list)
    gradingOracleFields: dict[str, Any] = field(default_factory=dict)
    tokenCostRecordSlots: dict[str, Any] = field(default_factory=dict)
    prompts: list[dict[str, Any]] = field(default_factory=list)
    backendRegistered: bool = False
    liveExecutionAllowed: bool = False
    plannedModelCalls: int | None = None
    naturalTasksPack: str | None = None
    honesty: dict[str, Any] = field(default_factory=dict)
    howToPlugBackend: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _oracle_fields_for_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "taskId": task["id"],
        "corruptionKind": task.get("corruptionKind"),
        "g1SupportedSeededError": bool(task.get("g1SupportedSeededError")),
        "g3Control": bool(task.get("g3Control")),
        "expectedPrimaryStatus": task.get("expectedPrimaryStatus"),
        "role": task.get("role"),
        "controllerOnly": True,
        "outsideAgentView": True,
        "note": (
            "Oracle expectations stay with the controller. Do not ship these "
            "fields into the evaluated Agent prompt."
        ),
    }


def build_live_four_arm_plan(
    *,
    protocol: dict[str, Any] | None = None,
    confirm_model_runs: int | None = None,
    natural_tasks_pack: str | None = None,
) -> LiveFourArmPlan:
    document = protocol if protocol is not None else load_protocol()
    registered = list(tasks(document))
    cells: list[dict[str, Any]] = []
    prompts: list[dict[str, Any]] = []
    oracle: dict[str, Any] = {"byTask": {}, "note": "Controller-owned; outside agent view."}
    for task in registered:
        oracle["byTask"][task["id"]] = _oracle_fields_for_task(task)
        for arm_id in (ARM_B0, ARM_B1, ARM_B3):
            record = LiveTokenCostRecordSlots()
            cell = {
                "arm": arm_id,
                "task": task["id"],
                "prompt": task.get("prompt"),
                "corruptionKind": task.get("corruptionKind"),
                "g1SupportedSeededError": bool(task.get("g1SupportedSeededError")),
                "runnableWhenAuthorized": arm_id in DEFERRED_ARMS or arm_id == ARM_B3,
                "mathProvider": (
                    None
                    if arm_id == ARM_B0
                    else ("mcp-voluntary" if arm_id == ARM_B1 else "obligation-runtime-shadow")
                ),
                "mcpTools": list(MCP_TOOLS) if arm_id == ARM_B1 else [],
                "gradingOracleRef": f"byTask.{task['id']}",
                "recordSlots": asdict(record),
                "status": "planned",
                "liveQualityDelta": None,
                "finalAccuracy": None,
                "acceptedSeededError": None,
                "dollarCost": None,
            }
            if arm_id == ARM_B3:
                cell["note"] = (
                    "B3-live would combine Host shadow checkpoint with a live "
                    "model repair loop. This plan does not execute it."
                )
            cells.append(cell)
        prompts.append(
            {
                "task": task["id"],
                "prompt": task.get("prompt"),
                "arms": [ARM_B0, ARM_B1, ARM_B3],
            }
        )

    return LiveFourArmPlan(
        protocolDigest=protocol_digest(document),
        cells=cells,
        gradingOracleFields=oracle,
        tokenCostRecordSlots=asdict(LiveTokenCostRecordSlots()),
        prompts=prompts,
        backendRegistered=backend_is_registered(),
        liveExecutionAllowed=False,
        plannedModelCalls=confirm_model_runs,
        naturalTasksPack=natural_tasks_pack,
        honesty={
            "noModelCallsMade": True,
            "noLiveNumbersInvented": True,
            "noDollarCostsInvented": True,
            "noSavingsPercentInvented": True,
            "planIsNotEvidence": True,
            "epoch2StillIncomplete": True,
            "modelArms": MODEL_ARMS_DEFERRED,
        },
        howToPlugBackend={
            "interface": "research.shadow_verifier_eval.live_runner.LiveModelBackend",
            "register": "register_live_backend(backend)",
            "completeSignature": (
                "complete(prompt, *, arm_id, task_id, tools=None) -> "
                "{text, usage, toolTrace?}"
            ),
            "mustNotInvent": [
                "finalAccuracy",
                "acceptedSeededErrors",
                "liveQualityDelta",
                "dollarCost",
                "savingsPercent",
            ],
            "authorization": [
                f"set {LIVE_ENV_FLAG}=1 or pass --confirm-live-budget",
                "pass --confirm-model-runs N with N > 0",
                "register a LiveModelBackend",
            ],
            "note": (
                "Until a backend is registered and budget is confirmed, "
                "--include-model-arms stays rejected. Emitting this plan does "
                "not authorize paid calls."
            ),
        },
    )


def live_budget_confirmed(*, confirm_live_budget: bool = False) -> bool:
    if confirm_live_budget:
        return True
    return os.environ.get(LIVE_ENV_FLAG, "").strip() in {"1", "true", "TRUE", "yes", "YES"}


def assert_live_execution_allowed(
    *,
    confirm_live_budget: bool = False,
    confirm_model_runs: int | None = None,
    protocol: dict[str, Any] | None = None,
) -> None:
    """Fail closed unless budget confirm + N>0 + registered backend."""

    document = protocol if protocol is not None else load_protocol()
    commands = document.get("liveModelCommands") or {}
    reasons: list[str] = []
    if not live_budget_confirmed(confirm_live_budget=confirm_live_budget):
        reasons.append(
            f"missing budget confirm (--confirm-live-budget or {LIVE_ENV_FLAG}=1)"
        )
    if confirm_model_runs is None or int(confirm_model_runs) <= 0:
        reasons.append("--confirm-model-runs N is required with N > 0")
    if not backend_is_registered():
        reasons.append("no LiveModelBackend registered via register_live_backend")
    if reasons:
        raise ModelArmNotReadyError(
            "E_INPUT",
            commands.get("includeModelArmsRejectedBecause")
            or (
                "live B0/B1 execution is fail-closed; model_arms=deferred; "
                + "; ".join(reasons)
            ),
            {
                "modelArms": MODEL_ARMS_DEFERRED,
                "backendRegistered": backend_is_registered(),
                "budgetConfirmed": live_budget_confirmed(
                    confirm_live_budget=confirm_live_budget
                ),
                "confirmModelRuns": confirm_model_runs,
                "reasons": reasons,
                "plannedCommand": commands.get("plannedLiveFourArm"),
                "emitLivePlan": commands.get("emitLivePlan"),
                "liveQualityDelta": None,
                "finalAccuracy": None,
                "dollarCost": None,
            },
        )


def reject_or_require_live_arms(
    *,
    include_model_arms: bool,
    confirm_live_budget: bool = False,
    confirm_model_runs: int | None = None,
    protocol: dict[str, Any] | None = None,
) -> None:
    if not include_model_arms:
        return
    assert_live_execution_allowed(
        confirm_live_budget=confirm_live_budget,
        confirm_model_runs=confirm_model_runs,
        protocol=protocol,
    )
    # Even when authorized, this scaffold does not yet drive a backend loop.
    # Keep fail-closed on execution so we never invent numbers here.
    raise ModelArmNotReadyError(
        "E_INPUT",
        "live backend gate passed, but the paid execution loop is not wired "
        "in this PR; model_arms=deferred; numbers are not invented. Use "
        "--emit-live-plan for the JSON plan.",
        {
            "modelArms": MODEL_ARMS_DEFERRED,
            "backendRegistered": backend_is_registered(),
            "budgetConfirmed": True,
            "confirmModelRuns": confirm_model_runs,
            "liveQualityDelta": None,
            "finalAccuracy": None,
            "dollarCost": None,
        },
    )
