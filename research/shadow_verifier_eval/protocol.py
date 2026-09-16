"""Pre-registered shadow-verifier protocol. Loaded from protocol.json; not inferred.

Unsupported execution-field overrides are rejected (pinned plan, same contract
as A4 R3 / trust-failclosed). `budget` is pinned like honesty / scoring.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PROTOCOL_PATH = Path(__file__).with_name("protocol.json")
PROTOCOL_KIND = "math-anchor.research.ai-for-math-shadow-verifier-protocol.v0"
REPORT_KIND = "math-anchor.research.ai-for-math-shadow-verifier-report.v0"

ARM_B0 = "B0"
ARM_B1 = "B1"
ARM_B2 = "B2"
ARM_B3 = "B3"
PRIMARY_ARMS = (ARM_B0, ARM_B1, ARM_B2, ARM_B3)
RUNNABLE_ARMS = (ARM_B2, ARM_B3)
DEFERRED_ARMS = (ARM_B0, ARM_B1)
MCP_TOOLS = ("math.search", "math.describe", "math.run", "math.batch")

TASK_CONTROL_POLY = "control-polynomial-identity"
TASK_CONTROL_DIM = "control-dimension-consistency"
TASK_SIGN_FLIP = "sign-flip"
TASK_DOMAIN_OVERSHOOT = "domain-overshoot-definedness"
TASK_DIMENSION_MISMATCH = "dimension-mismatch"
TASK_ROUNDING = "rounding-in-exact-chain"
TASK_UNIT_SCALE = "unit-scale-mismatch"
TASK_ASSUMPTION_SWAP = "assumption-swapped"
TASK_STEP_N_LEGAL_WRONG = "step-n-legal-wrong-value"
TASK_UNSUPPORTED = "unsupported-kind"
TASK_DEPENDENCY = "dependency-blocked"
TASK_SI_PREFIX_BLIND = "si-prefix-scale-blind-spot"

CONTROL_TASKS = (TASK_CONTROL_POLY, TASK_CONTROL_DIM)
SUPPORTED_ERROR_TASKS = (
    TASK_SIGN_FLIP,
    TASK_DOMAIN_OVERSHOOT,
    TASK_DIMENSION_MISMATCH,
    TASK_ROUNDING,
    TASK_UNIT_SCALE,
    TASK_ASSUMPTION_SWAP,
    TASK_STEP_N_LEGAL_WRONG,
)
SAME_CLAIM_REPAIR_TASKS = (TASK_SIGN_FLIP,)
UNRELATED_RESUBMIT_TASKS = (TASK_DIMENSION_MISMATCH,)
COMPLETENESS_TASKS = (TASK_UNSUPPORTED, TASK_DEPENDENCY, TASK_SI_PREFIX_BLIND)
ALL_TASKS = (
    TASK_CONTROL_POLY,
    TASK_CONTROL_DIM,
    TASK_SIGN_FLIP,
    TASK_DOMAIN_OVERSHOOT,
    TASK_DIMENSION_MISMATCH,
    TASK_ROUNDING,
    TASK_UNIT_SCALE,
    TASK_ASSUMPTION_SWAP,
    TASK_STEP_N_LEGAL_WRONG,
    TASK_UNSUPPORTED,
    TASK_DEPENDENCY,
    TASK_SI_PREFIX_BLIND,
)

GATE_IDS = ("G1", "G2", "G3", "G4", "G5", "G6")
CORRUPTION_KIND_IDS = (
    "none",
    "sign_flip",
    "stale_swapped_result",
    "wrong_witness",
    "wrong_claim_binding",
    "domain_overshoot",
    "dimension_mismatch",
    "unsupported_kind",
    "dependency_blocked",
    "rounding_sneak",
    "unit_scale_mismatch",
    "assumption_swap",
    "step_n_legal_wrong_value",
    "si_prefix_scale_blind_spot",
)

MODEL_ARMS_DEFERRED = "deferred"

_PINNED_FIELDS = (
    "arms",
    "tasks",
    "gates",
    "corruptionKinds",
    "honesty",
    "scoring",
    "decisionRule",
    "model",
    "budget",
    "liveModelCommands",
    "independence",
    "outOfScopeThisSmoke",
    "structuralProbes",
    "progressiveAssurance",
    "workload",
)


def _supported_protocol_document() -> dict[str, Any]:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def validate_protocol(document: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ValueError("shadow-verifier protocol must be an object")
    if document.get("kind") != PROTOCOL_KIND:
        raise ValueError(f"unexpected protocol kind: {document.get('kind')!r}")
    if document.get("preRegistered") is not True:
        raise ValueError("protocol must be marked preRegistered")
    if document.get("promotionForbiddenInThisSmoke") is not True:
        raise ValueError("protocol must forbid promotion in this smoke")
    if document.get("epoch2NotCompleteUntilLiveFourArmEvidence") is not True:
        raise ValueError("protocol must mark Epoch 2 incomplete until live four-arm evidence")
    if document.get("doNotStartH1") is not True:
        raise ValueError("protocol must forbid starting H1")
    if document.get("doNotPromoteMethodPacks") is not True:
        raise ValueError("protocol must forbid method-pack promotion")
    if document.get("model", {}).get("callsAllowed") is not False:
        raise ValueError("protocol must forbid model calls")
    if document.get("model", {}).get("modelArms") != MODEL_ARMS_DEFERRED:
        raise ValueError("protocol must mark model_arms=deferred")
    if document.get("budget", {}).get("dollarCosts") is not None:
        raise ValueError("protocol must not invent dollar costs")
    if not isinstance(document.get("tasks"), list) or not document["tasks"]:
        raise ValueError("protocol must declare tasks")
    if not isinstance(document.get("arms"), list) or not document["arms"]:
        raise ValueError("protocol must declare arms")
    supported = _supported_protocol_document()
    for field in _PINNED_FIELDS:
        if document.get(field) != supported.get(field):
            raise ValueError(
                f"shadow-verifier smoke only supports the pre-registered {field} plan"
            )
    arm_ids_present = [
        str(arm.get("id")) for arm in document["arms"] if isinstance(arm, dict)
    ]
    if tuple(arm_ids_present) != PRIMARY_ARMS:
        raise ValueError("shadow-verifier protocol arms must be B0, B1, B2, B3")
    task_ids = [str(task.get("id")) for task in document["tasks"] if isinstance(task, dict)]
    if tuple(task_ids) != ALL_TASKS:
        raise ValueError("shadow-verifier protocol tasks drifted from the pinned plan")
    gates = document.get("gates")
    if not isinstance(gates, dict) or tuple(gates) != GATE_IDS:
        raise ValueError("shadow-verifier protocol must declare gates G1–G6")
    kinds = document.get("corruptionKinds")
    if not isinstance(kinds, dict) or tuple(kinds) != CORRUPTION_KIND_IDS:
        raise ValueError("shadow-verifier protocol corruption kinds drifted")
    return document


def load_protocol() -> dict[str, Any]:
    document = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    return validate_protocol(document)


def protocol_digest(protocol: dict[str, Any] | None = None) -> str:
    document = validate_protocol(protocol) if protocol is not None else load_protocol()
    payload = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def tasks(protocol: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    document = protocol if protocol is not None else load_protocol()
    return list(document["tasks"])


def task_by_id(task_id: str, protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    for item in tasks(protocol):
        if item["id"] == task_id:
            return item
    raise KeyError(task_id)


def arm_ids(protocol: dict[str, Any] | None = None) -> list[str]:
    document = protocol if protocol is not None else load_protocol()
    return [str(arm["id"]) for arm in document["arms"]]


def expected_by_arm(task: dict[str, Any], arm_id: str) -> dict[str, Any]:
    by_arm = task.get("expectedByArm")
    if not isinstance(by_arm, dict):
        return {}
    spec = by_arm.get(arm_id)
    return spec if isinstance(spec, dict) else {}


def arm_spec(arm_id: str, protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    document = protocol if protocol is not None else load_protocol()
    for arm in document["arms"]:
        if arm.get("id") == arm_id:
            return arm
    raise KeyError(arm_id)


def live_model_commands(protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    document = protocol if protocol is not None else load_protocol()
    commands = document.get("liveModelCommands")
    return commands if isinstance(commands, dict) else {}
