#!/usr/bin/env python3
"""One-command A0/A1 vertical for rational-polynomial finite sums.

This script is a research proposal runner. It is not a fifth MCP tool and does
not require Agent Host or a model.
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

from research.polynomial_finite_sum_proposal.baseline import sympy_finite_sum
from research.polynomial_finite_sum_proposal.polynomials import DomainError
from research.polynomial_finite_sum_proposal.runner import (
    run_from_task,
    run_polynomial_finite_sum,
)
from research.polynomial_finite_sum_proposal.telescoping import TelescopingRuleError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Construct a discrete antidifference, independently check "
            "G(k+1)-G(k)=p(k), and apply the hand-provided telescoping rule."
        )
    )
    parser.add_argument("--task", help="JSON task object or path to a JSON file")
    parser.add_argument("--summand", help="Univariate polynomial summand, e.g. k^2")
    parser.add_argument("--variable", default="k")
    parser.add_argument("--lower", type=int)
    parser.add_argument("--upper", type=int)
    parser.add_argument(
        "--antidifference",
        help="Optional candidate G(k). Wrong coefficients fail the identity check.",
    )
    parser.add_argument(
        "--baseline-only",
        action="store_true",
        help="Run only the no-model SymPy summation baseline",
    )
    parser.add_argument(
        "--no-baseline",
        action="store_true",
        help="Skip the SymPy baseline comparison on the checked path",
    )
    parser.add_argument(
        "--receipt-output",
        type=Path,
        help="Write the polynomial-identity obligation receipt to a new file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the full result JSON to a new file in addition to stdout",
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


def _write_new_json(path: Path, value: dict[str, Any], *, label: str) -> None:
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
    try:
        if arguments.task:
            task = _load_task(arguments.task)
            if arguments.baseline_only:
                result = sympy_finite_sum(
                    summand=str(task["summand"]),
                    variable=str(task.get("variable", "k")),
                    lower=task["lower"],
                    upper=task["upper"],
                )
            else:
                result = run_from_task(task, compare_baseline=not arguments.no_baseline)
        else:
            if arguments.summand is None or arguments.lower is None or arguments.upper is None:
                raise CalculatorError(
                    "E_INPUT",
                    "provide --task or all of --summand, --lower, and --upper",
                )
            if arguments.baseline_only:
                result = sympy_finite_sum(
                    summand=arguments.summand,
                    variable=arguments.variable,
                    lower=arguments.lower,
                    upper=arguments.upper,
                )
            else:
                result = run_polynomial_finite_sum(
                    summand=arguments.summand,
                    variable=arguments.variable,
                    lower=arguments.lower,
                    upper=arguments.upper,
                    antidifference=arguments.antidifference,
                    compare_baseline=not arguments.no_baseline,
                )
        if arguments.receipt_output is not None:
            receipt = result.get("obligationReceipt")
            if not isinstance(receipt, dict):
                raise CalculatorError("E_INPUT", "this result has no obligation receipt to write")
            _write_new_json(arguments.receipt_output, receipt, label="receipt output")
        _emit(result, output=arguments.output)
    except (DomainError, TelescopingRuleError, CalculatorError) as error:
        payload = {
            "status": "error",
            "error": error_payload(error.code, error.message),
        }
        _emit(payload, output=arguments.output)
        return 2

    status = result.get("status")
    if status == "ok":
        return 0
    if status == "falsified":
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
