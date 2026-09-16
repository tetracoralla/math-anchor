#!/usr/bin/env python3
"""One-command shadow-verifier scaffold. B2/B3 deterministic. B0/B1 deferred.

Supports --emit-live-plan (no model calls). --include-model-arms stays
fail-closed without budget confirm + registered backend.
Not a benefit percentage, not a pack promotion, not Epoch 2 completion.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from math_anchor.errors import CalculatorError, error_payload

from research.shadow_verifier_eval.live_runner import build_live_four_arm_plan
from research.shadow_verifier_eval.smoke import run_smoke, write_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the pre-registered shadow-verifier scaffold (B2/B3 deterministic "
            "obligation runtime; B0/B1 model_arms=deferred). Writes a "
            "machine-readable report or a live-arm JSON plan. Not a benefit "
            "percentage, not a pack promotion, and not Epoch 2 completion."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the smoke report or live plan JSON to a new file (refuses to overwrite)",
    )
    parser.add_argument(
        "--receipt-dir",
        type=Path,
        help="Write B2/B3 full receipts to this directory (refuses to overwrite files)",
    )
    parser.add_argument(
        "--emit-live-plan",
        action="store_true",
        help=(
            "Write a LiveFourArmPlan JSON of what B0/B1/B3-live would run. "
            "Makes no model calls and invents no quality/cost numbers."
        ),
    )
    parser.add_argument(
        "--include-model-arms",
        action="store_true",
        help=(
            "Fail-closed unless --confirm-live-budget (or MATH_ANCHOR_SHADOW_LIVE=1), "
            "--confirm-model-runs N>0, and a LiveModelBackend is registered. "
            "This PR still does not wire the paid loop; numbers are not invented."
        ),
    )
    parser.add_argument(
        "--confirm-model-runs",
        type=int,
        default=None,
        help="Written planned-call count N for a later live four-arm run.",
    )
    parser.add_argument(
        "--confirm-live-budget",
        action="store_true",
        help=(
            "Explicit budget confirm for --include-model-arms. Alternative: "
            "MATH_ANCHOR_SHADOW_LIVE=1. Does not by itself authorize inventing numbers."
        ),
    )
    parser.add_argument(
        "--natural-tasks-pack",
        type=str,
        default=None,
        help="Optional path recorded on an emitted live plan (natural_tasks pack).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.emit_live_plan and arguments.include_model_arms:
        payload = {
            "status": "error",
            "error": error_payload(
                "E_INPUT",
                "--emit-live-plan and --include-model-arms are mutually exclusive",
            ),
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 2
    if arguments.confirm_model_runs is not None and not (
        arguments.include_model_arms or arguments.emit_live_plan
    ):
        payload = {
            "status": "error",
            "error": error_payload(
                "E_INPUT",
                "--confirm-model-runs is only meaningful with --include-model-arms "
                "or --emit-live-plan",
            ),
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 2
    try:
        if arguments.emit_live_plan:
            plan = build_live_four_arm_plan(
                confirm_model_runs=arguments.confirm_model_runs,
                natural_tasks_pack=arguments.natural_tasks_pack,
            ).to_dict()
            encoded = json.dumps(plan, ensure_ascii=False, indent=2)
            sys.stdout.write(encoded + "\n")
            if arguments.output is not None:
                write_report(arguments.output, plan)
            return 0

        report = run_smoke(
            receipt_dir=arguments.receipt_dir,
            include_model_arms=arguments.include_model_arms,
            confirm_live_budget=arguments.confirm_live_budget,
            confirm_model_runs=arguments.confirm_model_runs,
        )
        encoded = json.dumps(report, ensure_ascii=False, indent=2)
        sys.stdout.write(encoded + "\n")
        if arguments.output is not None:
            write_report(arguments.output, report)
    except CalculatorError as error:
        payload = {
            "status": "error",
            "error": error_payload(error.code, error.message, error.details),
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 2
    if report["decision"].get("promote"):
        return 2
    if report["decision"].get("targetedFix"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
