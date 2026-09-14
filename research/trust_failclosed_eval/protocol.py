"""Pre-registered trust/fail-closed protocol. Loaded from protocol.json; not inferred.

Unsupported execution-field overrides are rejected (pinned plan, same contract as A4 R3).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from research.reuse_benefit_eval.protocol import CACHED_G_SOURCE


PROTOCOL_PATH = Path(__file__).with_name("protocol.json")
PROTOCOL_KIND = "math-anchor.research.ai-for-math-trust-failclosed-protocol.v0"
REPORT_KIND = "math-anchor.research.ai-for-math-trust-failclosed-report.v0"

ARM_B_TEMPLATE = "B_template"
ARM_P_PACK = "P-pack"
PRIMARY_ARMS = (ARM_B_TEMPLATE, ARM_P_PACK)
CONSTRUCTION_TRACE_KEYS = (
    "gosper_sum",
    "construct_antidifference",
    "summation",
    "Sum.doit",
)

TASK_CONTROL = "control-P1"
TASK_WRONG_G = "wrong-saved-G"
TASK_SWAPPED_G = "swapped-saved-G"
TASK_CUBES = "out-of-family-cubes"
TASK_HARMONIC = "out-of-family-harmonic"
TASK_REVERSED = "reversed-bounds"
TASK_PARAMETER = "parameter-mismatch"
TASK_OVER_LIMIT = "over-limit"

CONTROL_TASKS = (TASK_CONTROL,)
ADVERSARIAL_SAVED_G_TASKS = (TASK_WRONG_G, TASK_SWAPPED_G)
OUT_OF_FAMILY_TASKS = (TASK_CUBES, TASK_HARMONIC)
OUT_OF_DOMAIN_TASKS = (TASK_REVERSED, TASK_OVER_LIMIT)
BOTH_FAIL_CLOSED_TASKS = (TASK_CUBES, TASK_HARMONIC, TASK_PARAMETER)
DIFFERENTIATION_TASKS = (TASK_WRONG_G, TASK_SWAPPED_G, TASK_REVERSED, TASK_OVER_LIMIT)

SAVED_G_CANONICAL = "canonical"
SAVED_G_LINEAR = "linear-k"
SAVED_G_CUBES = "swapped-cubes-antidifference"

TRUST_HOLDS = "holds"
TRUST_FAIL_CLOSED = "fail-closed"
TRUST_SILENT_WRONG = "silent-wrong"
TRUST_SCALE = (TRUST_HOLDS, TRUST_FAIL_CLOSED, TRUST_SILENT_WRONG)

WRONG_G_TEMPLATE_EXACT = "6"
SWAPPED_G_TEMPLATE_EXACT = "783"
KARR_REVERSED_EXACT = "-50"
OVER_LIMIT_EXACT = "2000018000041"
CONTROL_EXACT = "355"

MANDATORY_CLAIM_DIFFERENTIATION_ZH = (
    "包路径在错误保存的 G、交换载荷、反转边界与越界上 fail-closed，而模板给出错误值或静默接受"
)
MANDATORY_CLAIM_NO_SAVED_G_DIFF_ZH = "错误保存的 G 上未见 fail-closed 对 silent-wrong 的分化"
MANDATORY_CLAIM_NO_DOMAIN_DIFF_ZH = "反转边界或越界上未见 fail-closed 对 silent-wrong 的分化"
MANDATORY_CLAIM_LATENCY_NOT_PRIMARY_ZH = "本实验不以时延为主要结论"
KNOWN_MANDATORY_CLAIM_DIFF_CLAUSES_ZH = (
    MANDATORY_CLAIM_DIFFERENTIATION_ZH,
    MANDATORY_CLAIM_NO_SAVED_G_DIFF_ZH,
    MANDATORY_CLAIM_NO_DOMAIN_DIFF_ZH,
)


def _supported_protocol_document() -> dict[str, Any]:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def validate_protocol(document: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ValueError("trust/fail-closed protocol must be an object")
    if document.get("kind") != PROTOCOL_KIND:
        raise ValueError(f"unexpected protocol kind: {document.get('kind')!r}")
    if document.get("preRegistered") is not True:
        raise ValueError("protocol must be marked preRegistered")
    if document.get("promotionForbiddenInThisSmoke") is not True:
        raise ValueError("protocol must forbid promotion in this smoke")
    if document.get("judgmentsAreSeparate") is not True:
        raise ValueError("protocol must keep the three judgments separate")
    if document.get("notALatencyBakeOff") is not True:
        raise ValueError("protocol must mark this smoke as not a latency bake-off")
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
            "trust/fail-closed smoke only supports the pre-registered "
            "B_template/P-pack arm plan"
        )
    if document.get("tasks") != supported.get("tasks"):
        raise ValueError("trust/fail-closed smoke only supports the pre-registered task plan")
    if document.get("latency") != supported.get("latency"):
        raise ValueError(
            "trust/fail-closed smoke only supports the pre-registered informational latency plan"
        )
    if document.get("mandatoryClaimZh") != supported.get("mandatoryClaimZh"):
        raise ValueError("trust/fail-closed smoke only supports the pre-registered mandatory Chinese claim")
    if document.get("mandatoryClaimAnswerZh") != supported.get("mandatoryClaimAnswerZh"):
        raise ValueError("trust/fail-closed smoke only supports the pre-registered mandatory Chinese answer")
    if document.get("savedG") != supported.get("savedG"):
        raise ValueError("trust/fail-closed smoke only supports the pre-registered saved-G mutations")
    if document.get("trustworthinessScale") != supported.get("trustworthinessScale"):
        raise ValueError("trust/fail-closed smoke only supports the pre-registered trustworthiness scale")
    pinned_answer = supported.get("mandatoryClaimAnswerZh")
    if not isinstance(pinned_answer, str) or MANDATORY_CLAIM_LATENCY_NOT_PRIMARY_ZH not in pinned_answer:
        raise ValueError("pinned Chinese answer must state that latency is not the primary claim")
    canonical_source = (supported.get("savedG") or {}).get("canonical", {}).get("source")
    if canonical_source != CACHED_G_SOURCE:
        raise ValueError("canonical saved G must match the reuse-benefit cached formula")
    arm_ids_present = [
        str(arm.get("id")) for arm in document["arms"] if isinstance(arm, dict)
    ]
    if tuple(arm_ids_present) != PRIMARY_ARMS:
        raise ValueError("trust/fail-closed protocol arms must be B_template, P-pack")
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


def expected_exact_if_computed(task: dict[str, Any], arm_id: str) -> str | None:
    spec = expected_by_arm(task, arm_id)
    for key in ("expectedExact", "expectedExactIfComputed"):
        value = spec.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def saved_g_source(saved_g_id: str, protocol: dict[str, Any] | None = None) -> str:
    document = protocol if protocol is not None else load_protocol()
    catalog = document.get("savedG") if isinstance(document.get("savedG"), dict) else {}
    entry = catalog.get(saved_g_id)
    if not isinstance(entry, dict) or not isinstance(entry.get("source"), str):
        raise KeyError(saved_g_id)
    return entry["source"]


def differentiation_clause_zh(
    *,
    saved_g_differentiated: bool | None,
    domain_differentiated: bool | None,
) -> str:
    if saved_g_differentiated is True and domain_differentiated is True:
        return MANDATORY_CLAIM_DIFFERENTIATION_ZH
    if saved_g_differentiated is False:
        return MANDATORY_CLAIM_NO_SAVED_G_DIFF_ZH
    if domain_differentiated is False:
        return MANDATORY_CLAIM_NO_DOMAIN_DIFF_ZH
    return MANDATORY_CLAIM_DIFFERENTIATION_ZH


def reconcile_mandatory_claim_answer_zh(
    frozen: str,
    *,
    saved_g_differentiated: bool | None,
    domain_differentiated: bool | None,
) -> dict[str, Any]:
    """Bind the frozen Chinese answer to live differentiation flags."""

    live_clause = differentiation_clause_zh(
        saved_g_differentiated=saved_g_differentiated,
        domain_differentiated=domain_differentiated,
    )
    updated = frozen
    found: str | None = None
    for clause in KNOWN_MANDATORY_CLAIM_DIFF_CLAUSES_ZH:
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
        "differentiationClauseZh": live_clause,
        "frozenDifferentiationClauseZh": found,
        "overwrittenBecauseDifferentiationFlagsDisagreed": overwritten,
        "consistentWithDifferentiationFlags": not overwritten,
        "latencyIsNotPrimary": MANDATORY_CLAIM_LATENCY_NOT_PRIMARY_ZH in updated,
    }
