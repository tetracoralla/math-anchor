#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from math_anchor.obligations import (
    check_obligation_set,
    obligation_feedback_schema,
    obligation_receipt_schema,
)


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "evals" / "obligations" / "core.v0.1.json"
SUITE_VERSION = "math-anchor.obligation-conformance-suite.v0.1"


def main() -> None:
    suite = json.loads(SUITE.read_text(encoding="utf-8"))
    if set(suite) != {"schemaVersion", "request", "expected"}:
        raise SystemExit("obligation conformance suite has unexpected fields")
    if suite["schemaVersion"] != SUITE_VERSION:
        raise SystemExit("obligation conformance suite version mismatch")

    feedback, receipt = check_obligation_set(suite["request"])
    Draft202012Validator(obligation_feedback_schema()).validate(feedback)
    Draft202012Validator(obligation_receipt_schema()).validate(receipt)
    observed = [
        {
            key: entry[key]
            for key in ("id", "status", "assuranceLevel", "scope")
        }
        for entry in receipt["obligations"]
    ]
    if observed != suite["expected"]:
        raise SystemExit(
            "obligation conformance mismatch:\n"
            + json.dumps({"expected": suite["expected"], "observed": observed}, indent=2)
        )

    failures_request = deepcopy(suite["request"])
    failures_request["responseMode"] = "failures_only"
    failures_feedback, failures_receipt = check_obligation_set(failures_request)
    checked_ids = {
        entry["id"]
        for entry in failures_receipt["obligations"]
        if entry["status"] == "checked"
    }
    returned_ids = {entry["id"] for entry in failures_feedback["obligations"]}
    if checked_ids & returned_ids:
        raise SystemExit("failures_only feedback leaked checked obligation details")

    print(
        json.dumps(
            {
                "schemaVersion": SUITE_VERSION,
                "status": "ok",
                "suite": str(SUITE.relative_to(ROOT)),
                "summary": receipt["summary"],
                "receiptDigest": receipt["receiptDigest"],
                "failuresOnlyBytes": len(
                    json.dumps(
                        failures_feedback,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
