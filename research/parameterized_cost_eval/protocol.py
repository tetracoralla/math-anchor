"""Pre-registered parameterized cost-smoke protocol. Loaded from protocol.json; not inferred from results."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PROTOCOL_PATH = Path(__file__).with_name("protocol.json")
PROTOCOL_KIND = "math-anchor.research.ai-for-math-parameterized-cost-smoke-protocol.v0"
REPORT_KIND = "math-anchor.research.ai-for-math-parameterized-cost-smoke-report.v0"

ARM_B0 = "B0"
ARM_B1 = "B1"
ARM_P_PACK = "P-pack"
PRIMARY_ARMS = (ARM_B0, ARM_B1, ARM_P_PACK)

TASK_P0 = "P0-replay"
TASK_P1 = "P1-held-out"
TASK_P2 = "P2-rational"
TASK_NEGATIVE = "negative-harmonic"
IN_FAMILY_TASKS = (TASK_P0, TASK_P1, TASK_P2)

LIFECYCLE_CROSS_TASK = "cross-task-use-evidence"
LIFECYCLE_VERIFIED = "verified-in-declared-scope"


def validate_protocol(document: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ValueError("parameterized cost-smoke protocol must be an object")
    if document.get("kind") != PROTOCOL_KIND:
        raise ValueError(f"unexpected protocol kind: {document.get('kind')!r}")
    if document.get("preRegistered") is not True:
        raise ValueError("protocol must be marked preRegistered")
    if document.get("promotionForbiddenInThisSmoke") is not True:
        raise ValueError("protocol must forbid promotion in this smoke")
    if document.get("model", {}).get("callsAllowed") is not False:
        raise ValueError("protocol must forbid model calls")
    if document.get("budget", {}).get("dollarCosts") is not None:
        raise ValueError("protocol must not invent dollar costs")
    if not isinstance(document.get("tasks"), list) or not document["tasks"]:
        raise ValueError("protocol must declare tasks")
    if not isinstance(document.get("arms"), list) or not document["arms"]:
        raise ValueError("protocol must declare arms")
    arm_ids_present = [str(arm.get("id")) for arm in document["arms"]]
    for required in PRIMARY_ARMS:
        if required not in arm_ids_present:
            raise ValueError(f"protocol must declare arm {required}")
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
