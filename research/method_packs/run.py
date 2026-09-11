#!/usr/bin/env python3
"""CLI for the experimental A2 method pack: extract from T1, apply to a new task.

Research proposal runner. Not a fifth MCP tool. No Agent Host. No model.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from math_anchor.errors import CalculatorError, error_payload

from research.method_packs.apply import PackApplicationError, apply_method_pack
from research.method_packs.extract import extract_from_t1
from research.method_packs.format import (
    DEFAULT_PACK_PATH,
    HELD_OUT_SECOND_TASK_ID,
    PARAM_HELD_OUT_TASK_ID,
    PARAM_PACK_ID,
)
from research.method_packs.loader import PackFormatError, load_pack
from research.method_packs.shifted_square_extract import extract_shifted_square
from research.polynomial_finite_sum_proposal.coverage import (
    coverage_from_failure,
    record_coverage,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Experimental method pack: extract a Gosper polynomial-antidifference "
            "pack from T1, or apply the frozen pack to a new task."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    extract = sub.add_parser("extract", help="Replay T1, propose the pack, write evidence")
    extract.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for evidence JSON (default: the frozen pack's evidence/)",
    )

    extract_shifted = sub.add_parser(
        "extract-shifted-square",
        help="Derive G(k,c) for (k+c)^2, verify scope, write evidence",
    )
    extract_shifted.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for evidence JSON (default: the shifted-square pack's evidence/)",
    )

    apply_cmd = sub.add_parser("apply", help="Load the pack and instantiate it on a task")
    apply_cmd.add_argument("--task", required=True, help="JSON task object or path")
    apply_cmd.add_argument(
        "--pack",
        type=Path,
        default=DEFAULT_PACK_PATH,
        help="Path to pack.json",
    )
    apply_cmd.add_argument("--output", type=Path, help="Write the full result JSON")
    apply_cmd.add_argument("--chain-output", type=Path, help="Write only the method chain")
    apply_cmd.add_argument("--adoption-output", type=Path, help="Write the adoption record")
    apply_cmd.add_argument(
        "--receipt-output",
        type=Path,
        help="Write the polynomial-identity obligation receipt",
    )
    apply_cmd.add_argument(
        "--include-receipt",
        action="store_true",
        help="Include the full obligation receipt in the main result",
    )
    apply_cmd.add_argument(
        "--no-baseline",
        action="store_true",
        help="Skip the SymPy baseline comparison",
    )
    apply_cmd.add_argument(
        "--coverage-output",
        type=Path,
        help="Write the claim→obligation coverage record to a new file",
    )
    return parser


def _load_task(raw: str) -> dict[str, Any]:
    path = Path(raw)
    if path.is_file():
        source = path.read_text(encoding="utf-8")
    else:
        source = raw
    try:
        value = json.loads(source)
    except json.JSONDecodeError as error:
        raise CalculatorError("E_INPUT", f"invalid task JSON: {error}") from error
    if not isinstance(value, dict):
        raise CalculatorError("E_INPUT", "task JSON must be an object")
    return value


def _write_new_json(path: Path, value: object, *, label: str) -> None:
    if path.exists():
        raise CalculatorError("E_INPUT", f"{label} already exists; refusing to overwrite it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _emit(value: dict[str, Any], *, output: Path | None) -> None:
    encoded = json.dumps(value, ensure_ascii=False, indent=2)
    sys.stdout.write(encoded + "\n")
    if output is not None:
        _write_new_json(output, value, label="result output")


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    task: dict[str, Any] | None = None
    try:
        if arguments.command == "extract":
            evidence = extract_from_t1(output_dir=arguments.output_dir)
            _emit(
                {
                    "status": "ok",
                    "kind": "math-anchor.research.experimental-method-pack-extraction.v0",
                    "packId": evidence["packId"],
                    "lifecycle": evidence["lifecycle"],
                    "heldOutSecondTaskId": HELD_OUT_SECOND_TASK_ID,
                    "inScopePassed": evidence["inScopeVerification"]["allPassed"],
                    "negativesRejected": evidence["domainAndNegatives"]["allRejected"],
                    "novelty": evidence["candidate"]["novelty"]["status"],
                    "frozenPackConsistent": evidence.get("frozenPackConsistent", False),
                },
                output=None,
            )
            return 0

        if arguments.command == "extract-shifted-square":
            evidence = extract_shifted_square(output_dir=arguments.output_dir)
            _emit(
                {
                    "status": "ok",
                    "kind": "math-anchor.research.experimental-parameterized-method-pack-extraction.v0",
                    "packId": evidence["packId"],
                    "lifecycle": evidence["lifecycle"],
                    "heldOutSecondTaskId": PARAM_HELD_OUT_TASK_ID,
                    "inScopePassed": evidence["inScopeVerification"]["allPassed"],
                    "negativesRejected": evidence["domainAndNegatives"]["allRejected"],
                    "novelty": evidence["candidate"]["novelty"]["status"],
                    "frozenPackConsistent": evidence.get("frozenPackConsistent", False),
                    "reconstructionDisabledOnApply": True,
                    "whatThePackAddsVersusB1": evidence["whatThePackAddsVersusB1"],
                },
                output=None,
            )
            return 0

        task = _load_task(arguments.task)
        pack = load_pack(arguments.pack)
        result = apply_method_pack(
            task,
            pack=pack,
            compare_baseline=not arguments.no_baseline,
            include_backend_receipt=arguments.include_receipt or arguments.receipt_output is not None,
        )
        coverage = None
        if arguments.coverage_output is not None:
            # Coverage must see the verification association before any evidence
            # presentation strip. Sidecar receipt is not deletion of evidence.
            if pack.get("id") == PARAM_PACK_ID:
                coverage = {
                    "kind": "math-anchor.research.shifted-square-parameterized-coverage.v0",
                    "source": "shifted-square-apply",
                    "coversOriginalTaskClaim": False,
                    "reconstructionDisabled": True,
                    "gosperCalled": False,
                    "parameterC": (result.get("params") or {}).get("parameterC"),
                    "value": result.get("value"),
                    "note": (
                        "A3 polynomial-finite-sum coverage is the Gosper-pack table. "
                        "This record only states that saved G was instantiated."
                    ),
                }
            else:
                coverage = record_coverage(task, result, pack=pack, source="method-pack-apply")
            _write_new_json(arguments.coverage_output, coverage, label="coverage output")
        if arguments.receipt_output is not None:
            receipt = result.get("obligationReceipt")
            if not isinstance(receipt, dict):
                raise CalculatorError("E_INPUT", "this result has no obligation receipt to write")
            _write_new_json(arguments.receipt_output, receipt, label="receipt output")
            if not arguments.include_receipt:
                result = dict(result)
                result.pop("obligationReceipt", None)
        if arguments.chain_output is not None:
            _write_new_json(arguments.chain_output, result["chain"], label="chain output")
        if arguments.adoption_output is not None:
            _write_new_json(arguments.adoption_output, result["adoption"], label="adoption output")
        if coverage is not None:
            result = dict(result)
            result["coverage"] = coverage
        _emit(result, output=arguments.output)
    except (PackFormatError, PackApplicationError, CalculatorError) as error:
        payload: dict[str, Any] = {
            "status": "inapplicable" if isinstance(error, PackApplicationError) and (error.details or {}).get("applicability") == "rejected" else "error",
            "error": error_payload(error.code, error.message, error.details),
        }
        if isinstance(error, PackApplicationError) and error.details:
            payload["reason"] = error.details.get("reason", "pack_application_failed")
            payload["methodPack"] = {"id": error.details.get("methodPackId")}
        if getattr(arguments, "coverage_output", None) is not None:
            failed_task = task if isinstance(task, dict) else {}
            coverage = coverage_from_failure(failed_task, error)
            if not arguments.coverage_output.exists():
                _write_new_json(arguments.coverage_output, coverage, label="coverage output")
            payload["coverage"] = coverage
        _emit(payload, output=getattr(arguments, "output", None))
        return 2

    status = result.get("status")
    if status == "ok":
        return 0
    if status == "falsified":
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
