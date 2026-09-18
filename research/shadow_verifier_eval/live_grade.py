"""Controller-owned grading of live B0/B1 model text.

Oracle expectations stay outside the evaluated Agent prompt. Unparseable
output is recorded as unparseable — it is not treated as detection, acceptance,
or an invented accuracy score.
"""

from __future__ import annotations

import re
from typing import Any


_VERDICT_LINE = re.compile(
    r"^\s*VERDICT:\s*(YES|NO|UNSURE)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_YES_WORDS = re.compile(
    r"\b(yes|identical|equivalent|consistent|holds|true)\b",
    re.IGNORECASE,
)
_NO_WORDS = re.compile(
    r"\b(no|not identical|not equivalent|inconsistent|does not hold|false)\b",
    re.IGNORECASE,
)


def parse_verdict(text: str | None) -> str:
    """Return yes, no, unsure, or unparseable. Never invent a numeric score."""

    if not isinstance(text, str) or not text.strip():
        return "unparseable"
    matches = list(_VERDICT_LINE.finditer(text))
    if matches:
        return matches[-1].group(1).lower()
    # Conservative fallback: only if the tail has a clear yes xor no cue.
    tail = text.strip().splitlines()[-8:]
    blob = "\n".join(tail)
    has_yes = bool(_YES_WORDS.search(blob))
    has_no = bool(_NO_WORDS.search(blob))
    if has_no and not has_yes:
        return "no"
    if has_yes and not has_no:
        return "yes"
    return "unparseable"


def grade_live_task(task: dict[str, Any], verdict: str) -> dict[str, Any]:
    """Map a parsed verdict onto G1/G3 flags. Completeness cells are recorded only."""

    g1 = bool(task.get("g1SupportedSeededError"))
    g3 = bool(task.get("g3Control"))
    expected_status = task.get("expectedPrimaryStatus")
    # Seeded errors are false claims: detection is a NO verdict.
    # Controls are true claims: a NO verdict is a false reject.
    detected = g1 and verdict == "no"
    accepted_seeded = g1 and verdict == "yes"
    false_reject = g3 and verdict == "no"
    control_accepted = g3 and verdict == "yes"
    return {
        "verdict": verdict,
        "g1SupportedSeededError": g1,
        "g3Control": g3,
        "expectedPrimaryStatus": expected_status,
        "detected": detected if g1 else None,
        "acceptedSeededError": accepted_seeded if g1 else None,
        "falseReject": false_reject if g3 else None,
        "controlAccepted": control_accepted if g3 else None,
        "unparseable": verdict == "unparseable",
        "coversOriginalTaskClaim": False,
        "formalKernelChecked": False,
        "liveQualityDelta": None,
        "finalAccuracy": None,
        "dollarCost": None,
    }
