#!/usr/bin/env python3
"""One-command shadow-verifier scaffold. B2/B3 deterministic. B0/B1 live when authorized.

Supports --emit-live-plan (no model calls). --include-model-arms stays
fail-closed without budget confirm + registered backend. When authorized,
the CLI auto-registers an xAI/Grok backend if credentials are available
and executes live B0/B1 up to --confirm-model-runs N.
Not a benefit percentage, not a pack promotion, not Epoch 2 completion.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from math_anchor.errors import CalculatorError, error_payload

from research.shadow_verifier_eval.live_runner import (
    backend_is_registered,
    build_live_four_arm_plan,
    register_live_backend,
)
from research.shadow_verifier_eval.smoke import run_smoke, write_report
from research.shadow_verifier_eval.xai_backend import try_make_xai_backend


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the pre-registered shadow-verifier scaffold (B2/B3 deterministic "
            "obligation runtime; B0/B1 live when --include-model-arms is authorized). "
            "Writes a machine-readable report or a live-arm JSON plan. Not a benefit "
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
            "When those hold, execute live B0/B1 cells up to N complete() calls. "
            "Numbers are not invented. CLI auto-registers xAI/Grok when credentials "
            "exist unless MATH_ANCHOR_SHADOW_DISABLE_AUTO_BACKEND=1."
        ),
    )
    parser.add_argument(
        "--confirm-model-runs",
        type=int,
        default=None,
        help="Written paid-call cap N. Each backend.complete() consumes one.",
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
        help=(
            "Path to natural_tasks pack directory. When set with --emit-live-plan, "
            "loads and validates index.json + tasks into the plan (agent-view "
            "prompts vs controller-oracle split). Missing/invalid path fails closed."
        ),
    )
    return parser


def _emit_error(error: CalculatorError) -> int:
    payload = {
        "status": "error",
        "error": error_payload(error.code, error.message, error.details),
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return 2


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.emit_live_plan and arguments.include_model_arms:
        return _emit_error(
            CalculatorError(
                "E_INPUT",
                "--emit-live-plan and --include-model-arms are mutually exclusive",
            )
        )
    if arguments.confirm_model_runs is not None and not (
        arguments.include_model_arms or arguments.emit_live_plan
    ):
        return _emit_error(
            CalculatorError(
                "E_INPUT",
                "--confirm-model-runs is only meaningful with --include-model-arms "
                "or --emit-live-plan",
            )
        )
    if (
        arguments.include_model_arms
        and not backend_is_registered()
        and os.environ.get("MATH_ANCHOR_SHADOW_DISABLE_AUTO_BACKEND", "").strip()
        not in {"1", "true", "TRUE", "yes", "YES"}
    ):
        auto = try_make_xai_backend()
        if auto is not None:
            register_live_backend(auto)

    try:
        if arguments.emit_live_plan:
            plan = build_live_four_arm_plan(
                confirm_model_runs=arguments.confirm_model_runs,
                natural_tasks_pack=arguments.natural_tasks_pack,
            ).to_dict()
            # Validate/write output before printing success JSON so an overwrite
            # refusal emits exactly one error object (no success+error Extra data).
            if arguments.output is not None:
                write_report(arguments.output, plan)
            sys.stdout.write(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
            return 0

        report = run_smoke(
            receipt_dir=arguments.receipt_dir,
            include_model_arms=arguments.include_model_arms,
            confirm_live_budget=arguments.confirm_live_budget,
            confirm_model_runs=arguments.confirm_model_runs,
        )
        if arguments.output is not None:
            write_report(arguments.output, report)
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    except CalculatorError as error:
        return _emit_error(error)
    if report["decision"].get("promote"):
        return 2
    if report["decision"].get("targetedFix"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
