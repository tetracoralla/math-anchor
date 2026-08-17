#!/usr/bin/env python3
"""Record-only performance benchmark for the Math Anchor calculation core.

Measures, per registered operation:

* warm in-process latency of ``execute_direct`` over a fixed corpus
  (p50 / p95 / p99 / mean / min in milliseconds);
* cold-start cost of a fresh interpreter (spawn + import + first evaluation);
* packaged-binary end-to-end first-result latency: process spawn to the first
  ``expression.evaluate`` result, the user-facing cold start.

This script RECORDS facts. It applies no thresholds, asserts nothing about
good or bad numbers, and is not wired into any check. Receipts are written to
``build/benchmarks/`` which is gitignored; nothing is tracked.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from math_anchor.catalog import OPERATIONS  # noqa: E402
from math_anchor.runtime import execute_direct  # noqa: E402

PACKAGED_RUNTIME = ROOT / "plugins" / "math-anchor" / "runtime" / "math-anchor-runtime" / "math-anchor-runtime"
FIRST_EXPRESSION = "6*7"

# Heavy operations are sampled fewer times so a default run stays practical;
# this manages benchmark wall time only and implies no quality judgment.
HEAVY_OPERATIONS = {"numeric.integrate"}
EXPENSIVE_SAMPLE_MS = 100.0


def _percentile(samples: list[float], fraction: float) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def _summarize(samples: list[float]) -> dict[str, Any]:
    return {
        "samples": len(samples),
        "p50_ms": round(_percentile(samples, 0.50), 3),
        "p95_ms": round(_percentile(samples, 0.95), 3),
        "p99_ms": round(_percentile(samples, 0.99), 3),
        "mean_ms": round(statistics.fmean(samples), 3),
        "min_ms": round(min(samples), 3),
        "max_ms": round(max(samples), 3),
    }


def operation_corpus(selected: list[str]) -> dict[str, list[dict[str, Any]]]:
    corpus: dict[str, list[dict[str, Any]]] = {}
    for operation in selected:
        spec = OPERATIONS[operation]
        examples = [dict(example) for example in spec.examples]
        if operation == "expression.evaluate":
            examples.append({"expression": FIRST_EXPRESSION, "precision": 16})
            examples.append({"expression": "sqrt(2)*exp(3)*pi", "precision": 30})
        corpus[operation] = examples
    return corpus


def benchmark_warm(corpus: dict[str, list[dict[str, Any]]], warm_samples: int) -> dict[str, Any]:
    report: dict[str, Any] = {}
    for operation, examples in corpus.items():
        samples: list[float] = []
        target = 5 if operation in HEAVY_OPERATIONS else warm_samples
        for _ in range(target):
            for arguments in examples:
                started = time.perf_counter()
                execute_direct(operation, arguments)
                samples.append((time.perf_counter() - started) * 1000.0)
        report[operation] = _summarize(samples)
        # Re-check heaviness empirically: anything with a >100ms median gets
        # the reduced sample count treatment on the next run of this script.
        if operation not in HEAVY_OPERATIONS and report[operation]["p50_ms"] > EXPENSIVE_SAMPLE_MS:
            report[operation]["note"] = "median above 100 ms; consider adding to HEAVY_OPERATIONS"
    return report


def benchmark_cold(samples: int) -> dict[str, Any]:
    code = (
        "import time; start = time.perf_counter(); "
        "from math_anchor.runtime import execute_direct; "
        "result = execute_direct('expression.evaluate', "
        f"{{'expression': {FIRST_EXPRESSION!r}, 'precision': 16}}); "
        "print(time.perf_counter() - start)"
    )
    timings: list[float] = []
    for _ in range(samples):
        started = time.perf_counter()
        completed = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True
        )
        wall = (time.perf_counter() - started) * 1000.0
        inner_ms = float(completed.stdout.strip()) * 1000.0
        timings.append(wall)
    summary = _summarize(timings)
    summary["inner_import_and_evaluate_ms"] = round(statistics.fmean([
        inner_ms
    ]), 3) if samples else None
    return summary


def benchmark_packaged(runs: int) -> dict[str, Any]:
    if not PACKAGED_RUNTIME.is_file():
        return {"available": False, "path": str(PACKAGED_RUNTIME)}

    ready_timings: list[float] = []
    first_result_timings: list[float] = []
    warm_followup_timings: list[float] = []
    for _ in range(runs):
        started = time.perf_counter()
        process = subprocess.Popen(
            [str(PACKAGED_RUNTIME), "app"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        assert process.stdin is not None and process.stdout is not None
        ready_line = process.stdout.readline()
        ready_at = (time.perf_counter() - started) * 1000.0
        payload = json.dumps(
            {
                "id": "bench-1",
                "operation": "expression.evaluate",
                "expression": FIRST_EXPRESSION,
                "precision": 16,
            }
        )
        request_started = time.perf_counter()
        process.stdin.write(payload + "\n")
        process.stdin.flush()
        first_line = process.stdout.readline()
        first_at = (time.perf_counter() - request_started) * 1000.0
        warm_started = time.perf_counter()
        process.stdin.write(payload.replace("bench-1", "bench-2") + "\n")
        process.stdin.flush()
        process.stdout.readline()
        warm_at = (time.perf_counter() - warm_started) * 1000.0
        process.stdin.close()
        process.wait(timeout=30)
        ready_timings.append(ready_at)
        first_result_timings.append(first_at)
        warm_followup_timings.append(warm_at)
        assert json.loads(ready_line).get("status") == "ready", ready_line
        assert json.loads(first_line).get("status") == "ok", first_line

    return {
        "available": True,
        "path": str(PACKAGED_RUNTIME),
        "spawn_to_ready_ms": _summarize(ready_timings),
        "first_result_after_ready_ms": _summarize(first_result_timings),
        "second_result_ms": _summarize(warm_followup_timings),
        "cold_start_total_ms": _summarize([a + b for a, b in zip(ready_timings, first_result_timings)]),
    }


def human_table(warm: dict[str, Any]) -> str:
    header = f"{'operation':28} {'p50':>10} {'p95':>10} {'p99':>10} {'mean':>10} {'n':>5}"
    lines = [header, "-" * len(header)]
    for operation, summary in sorted(warm.items()):
        lines.append(
            f"{operation:28} {summary['p50_ms']:>10.3f} {summary['p95_ms']:>10.3f} "
            f"{summary['p99_ms']:>10.3f} {summary['mean_ms']:>10.3f} {summary['samples']:>5}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ops", default="all", help="comma-separated operation ids, or 'all'")
    parser.add_argument("--warm-samples", type=int, default=25)
    parser.add_argument("--cold-samples", type=int, default=5)
    parser.add_argument("--packaged-runs", type=int, default=5)
    parser.add_argument("--output-dir", default=str(ROOT / "build" / "benchmarks"))
    arguments = parser.parse_args()

    selected = (
        sorted(OPERATIONS) if arguments.ops == "all" else arguments.ops.split(",")
    )
    unknown = [operation for operation in selected if operation not in OPERATIONS]
    if unknown:
        parser.error(f"unknown operations: {', '.join(unknown)}")

    corpus = operation_corpus(selected)
    report: dict[str, Any] = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "warm": benchmark_warm(corpus, arguments.warm_samples),
        "cold_interpreter": benchmark_cold(arguments.cold_samples),
        "packaged_runtime": benchmark_packaged(arguments.packaged_runs),
    }

    output_dir = Path(arguments.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    receipt = output_dir / f"benchmark-{stamp}.json"
    receipt.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    latest = output_dir / "latest.json"
    latest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(human_table(report["warm"]))
    cold = report["cold_interpreter"]
    print(f"\ncold interpreter (spawn+import+evaluate): p50 {cold['p50_ms']:.1f} ms "
          f"(inner import+evaluate {cold['inner_import_and_evaluate_ms']:.1f} ms)")
    packaged = report["packaged_runtime"]
    if packaged.get("available"):
        total = packaged["cold_start_total_ms"]
        print(f"packaged binary end-to-end first result: p50 {total['p50_ms']:.1f} ms, "
              f"p95 {total['p95_ms']:.1f} ms "
              f"(spawn->ready p50 {packaged['spawn_to_ready_ms']['p50_ms']:.1f} ms)")
    else:
        print(f"packaged binary not present, skipped: {packaged['path']}")
    print(f"receipt: {receipt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
