"""Pre-registered reuse-benefit protocol. Loaded from protocol.json; not inferred from results.

Unsupported execution-field overrides are rejected (pinned plan, same contract as A4 R3).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PROTOCOL_PATH = Path(__file__).with_name("protocol.json")
PROTOCOL_KIND = "math-anchor.research.ai-for-math-reuse-benefit-protocol.v0"
REPORT_KIND = "math-anchor.research.ai-for-math-reuse-benefit-report.v0"

ARM_B0 = "B0"
ARM_B1 = "B1"
ARM_B_TEMPLATE = "B_template"
ARM_B_CODEGEN = "B_codegen"
ARM_P_PACK = "P-pack"
PRIMARY_ARMS = (ARM_B0, ARM_B1, ARM_B_TEMPLATE, ARM_B_CODEGEN, ARM_P_PACK)
FAMILY_REUSE_ARMS = (ARM_B_TEMPLATE, ARM_B_CODEGEN, ARM_P_PACK)
KARR_ARMS = (ARM_B0, ARM_B_TEMPLATE, ARM_B_CODEGEN)

TASK_P0 = "P0-replay"
TASK_P1 = "P1-held-out"
TASK_P2 = "P2-rational"
TASK_P3 = "P3-held-out-negative-c"
TASK_P4 = "P4-empty"
TASK_NEGATIVE = "negative-harmonic"
TASK_REVERSED = "negative-reversed"
IN_FAMILY_TASKS = (TASK_P0, TASK_P1, TASK_P2, TASK_P3, TASK_P4)
HELD_OUT_TASKS = (TASK_P1, TASK_P2, TASK_P3)
NEVER_SOLVED_TASKS = (TASK_NEGATIVE, TASK_REVERSED)

LIFECYCLE_CROSS_TASK = "cross-task-use-evidence"
LIFECYCLE_VERIFIED = "verified-in-declared-scope"

CACHED_G_SOURCE = "k*(k - 1)*(2*k - 1)/6 + c*k*(k - 1) + (c**2)*k"

B0_HARMONIC_EXACT = "11/6"
KARR_REVERSED_EXACT = "-50"

MANDATORY_CLAIM_LATENCY_NOT_FASTER_ZH = "本机耗时并不更低"
MANDATORY_CLAIM_LATENCY_FASTER_THAN_TEMPLATE_ZH = "本机重复路径相对 B_template 更快"
MANDATORY_CLAIM_LATENCY_UNMEASURED_ZH = "本机相对 B_template 的重复耗时未经测量"
KNOWN_MANDATORY_CLAIM_LATENCY_CLAUSES_ZH = (
    MANDATORY_CLAIM_LATENCY_NOT_FASTER_ZH,
    MANDATORY_CLAIM_LATENCY_FASTER_THAN_TEMPLATE_ZH,
    MANDATORY_CLAIM_LATENCY_UNMEASURED_ZH,
)


def _supported_protocol_document() -> dict[str, Any]:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def validate_protocol(document: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ValueError("reuse-benefit protocol must be an object")
    if document.get("kind") != PROTOCOL_KIND:
        raise ValueError(f"unexpected protocol kind: {document.get('kind')!r}")
    if document.get("preRegistered") is not True:
        raise ValueError("protocol must be marked preRegistered")
    if document.get("promotionForbiddenInThisSmoke") is not True:
        raise ValueError("protocol must forbid promotion in this smoke")
    if document.get("judgmentsAreSeparate") is not True:
        raise ValueError("protocol must keep the three judgments separate")
    if document.get("model", {}).get("callsAllowed") is not False:
        raise ValueError("protocol must forbid model calls")
    if document.get("budget", {}).get("dollarCosts") is not None:
        raise ValueError("protocol must not invent dollar costs")
    if not isinstance(document.get("tasks"), list) or not document["tasks"]:
        raise ValueError("protocol must declare tasks")
    if not isinstance(document.get("arms"), list) or not document["arms"]:
        raise ValueError("protocol must declare arms")
    supported = _supported_protocol_document()
    if document.get("arms") != supported.get("arms"):
        raise ValueError(
            "reuse-benefit smoke only supports the pre-registered "
            "B0/B1/B_template/B_codegen/P-pack arm plan"
        )
    if document.get("tasks") != supported.get("tasks"):
        raise ValueError("reuse-benefit smoke only supports the pre-registered task plan")
    if document.get("latency") != supported.get("latency"):
        raise ValueError(
            "reuse-benefit smoke only supports the pre-registered two-trial first/repeat latency plan"
        )
    if document.get("mandatoryClaimZh") != supported.get("mandatoryClaimZh"):
        raise ValueError("reuse-benefit smoke only supports the pre-registered mandatory Chinese claim")
    if document.get("mandatoryClaimAnswerZh") != supported.get("mandatoryClaimAnswerZh"):
        raise ValueError("reuse-benefit smoke only supports the pre-registered mandatory Chinese answer")
    pinned_answer = supported.get("mandatoryClaimAnswerZh")
    if not isinstance(pinned_answer, str) or not any(
        clause in pinned_answer for clause in KNOWN_MANDATORY_CLAIM_LATENCY_CLAUSES_ZH
    ):
        raise ValueError("pinned Chinese answer must include a known latency clause")
    arm_ids_present = [
        str(arm.get("id")) for arm in document["arms"] if isinstance(arm, dict)
    ]
    if tuple(arm_ids_present) != PRIMARY_ARMS:
        raise ValueError("reuse-benefit protocol arms must be B0, B1, B_template, B_codegen, P-pack")
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


def expected_exact_if_computed(task: dict[str, Any], arm_id: str) -> str | None:
    by_arm = task.get("expectedByArm")
    if not isinstance(by_arm, dict):
        return None
    spec = by_arm.get(arm_id)
    if not isinstance(spec, dict):
        return None
    value = spec.get("expectedExactIfComputed")
    if isinstance(value, str) and value:
        return value
    return None


def latency_clause_zh(observed_pack_faster_than_template: bool | None) -> str:
    """Latency clause for the mandatory Chinese answer, from measured flags."""

    if observed_pack_faster_than_template is True:
        return MANDATORY_CLAIM_LATENCY_FASTER_THAN_TEMPLATE_ZH
    if observed_pack_faster_than_template is False:
        return MANDATORY_CLAIM_LATENCY_NOT_FASTER_ZH
    return MANDATORY_CLAIM_LATENCY_UNMEASURED_ZH


def reconcile_mandatory_claim_answer_zh(
    frozen: str,
    *,
    observed_pack_faster_than_template: bool | None,
) -> dict[str, Any]:
    """Bind the frozen Chinese answer to live latency flags.

    The protocol string is pinned (mutated slogans are refused). The latency
    clause is still generated from `observedPackRepeatFasterThanTemplate` so a
    frozen “并不更低” cannot be emitted when the pack repeat path was faster.
    """

    live_clause = latency_clause_zh(observed_pack_faster_than_template)
    updated = frozen
    found: str | None = None
    for clause in KNOWN_MANDATORY_CLAIM_LATENCY_CLAUSES_ZH:
        if clause in updated:
            found = clause
            updated = updated.replace(clause, live_clause)
            break
    if found is None:
        suffix = "。" if not frozen.endswith("。") else ""
        updated = f"{frozen}{suffix}{live_clause}。"
    overwritten = updated != frozen
    return {
        "answerZh": updated,
        "latencyClauseZh": live_clause,
        "frozenLatencyClauseZh": found,
        "overwrittenBecauseLatencyFlagsDisagreed": overwritten,
        "consistentWithLatencyFlags": not overwritten,
    }
