"""Pre-registered A4 smoke protocol. Loaded from protocol.json; not inferred from results."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PROTOCOL_PATH = Path(__file__).with_name("protocol.json")
PROTOCOL_KIND = "math-anchor.research.ai-for-math-a4-smoke-protocol.v0"
REPORT_KIND = "math-anchor.research.ai-for-math-a4-smoke-report.v0"

ARM_B0 = "B0"
ARM_B1 = "B1"
ARM_B2 = "B2"
ARM_B2_MINUS = "B2-minus"
PRIMARY_ARMS = (ARM_B0, ARM_B1, ARM_B2)

TASK_T1 = "T1"
TASK_CUBES = "held-out-cubes"
TASK_NEGATIVE = "negative-harmonic"

LIFECYCLE_CROSS_TASK = "cross-task-use-evidence"
LIFECYCLE_VERIFIED = "verified-in-declared-scope"


def load_protocol() -> dict[str, Any]:
    document = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    if document.get("kind") != PROTOCOL_KIND:
        raise ValueError(f"unexpected A4 protocol kind: {document.get('kind')!r}")
    if document.get("preRegistered") is not True:
        raise ValueError("A4 protocol must be marked preRegistered")
    if document.get("promotionForbiddenInThisSmoke") is not True:
        raise ValueError("A4 protocol must forbid promotion in this smoke")
    if document.get("model", {}).get("callsAllowed") is not False:
        raise ValueError("A4 protocol must forbid model calls")
    if document.get("budget", {}).get("dollarCosts") is not None:
        raise ValueError("A4 protocol must not invent dollar costs")
    return document


def protocol_digest() -> str:
    payload = PROTOCOL_PATH.read_bytes()
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
