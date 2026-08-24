#!/usr/bin/env python3
"""Exercise sustained and failure-heavy Math Anchor supervisor traffic.

This is a runtime gate, not a microbenchmark. It records timings but only
fails on wrong results, failed recovery, or clear process/thread/descriptor
leaks. Receipts are gitignored under build/load-checks/.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys
import threading
import time
from typing import Any

import psutil


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import math_anchor.sandbox as sandbox  # noqa: E402
from math_anchor.runtime_telemetry import RUNTIME_TELEMETRY  # noqa: E402


def _percentile(samples: list[float], fraction: float) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * fraction))
    return ordered[index]


def _summary(samples: list[float]) -> dict[str, float | int]:
    return {
        "samples": len(samples),
        "p50Ms": round(_percentile(samples, 0.50), 3),
        "p95Ms": round(_percentile(samples, 0.95), 3),
        "p99Ms": round(_percentile(samples, 0.99), 3),
        "meanMs": round(statistics.fmean(samples), 3),
        "maxMs": round(max(samples), 3),
    }


def _resources() -> dict[str, int]:
    process = psutil.Process()
    return {
        "rssBytes": process.memory_info().rss,
        "threads": process.num_threads(),
        "fileDescriptors": process.num_fds(),
        "children": len(process.children(recursive=True)),
    }


def _call(expression: str = "6*7", *, timeout_ms: int = 10_000) -> dict[str, Any]:
    return sandbox.run_operation(
        "expression.evaluate",
        {"expression": expression},
        timeout_ms=timeout_ms,
    )


def _timed_calls(count: int, concurrency: int) -> tuple[list[float], list[dict[str, Any]]]:
    def one(index: int) -> tuple[float, dict[str, Any]]:
        started = time.perf_counter()
        result = _call(f"{index % 97}+1")
        return (time.perf_counter() - started) * 1000, result

    if concurrency == 1:
        completed = [one(index) for index in range(count)]
    else:
        with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="load-check") as executor:
            completed = list(executor.map(one, range(count)))
    return [item[0] for item in completed], [item[1] for item in completed]


def _require_success(results: list[dict[str, Any]], label: str) -> None:
    failures = [result for result in results if result.get("status") != "ok"]
    if failures:
        raise AssertionError(f"{label}: {len(failures)} calls failed; first={failures[0]}")


def _cancellation_storm(count: int) -> dict[str, Any]:
    events = [threading.Event() for _ in range(count)]

    def one(index: int) -> dict[str, Any]:
        return sandbox.run_operation(
            "expression.evaluate",
            {"expression": "floor(gamma(exp(7)))", "precision": 16},
            timeout_ms=30_000,
            cancel_event=events[index],
        )

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=count, thread_name_prefix="cancel-storm") as executor:
        futures = [executor.submit(one, index) for index in range(count)]
        time.sleep(0.1)
        for event in events:
            event.set()
        results = [future.result(timeout=10) for future in futures]
    codes = [result.get("error", {}).get("code") for result in results]
    if set(codes) != {"E_CANCELLED"}:
        raise AssertionError(f"cancellation storm returned unexpected codes: {codes}")
    recovered = _call("40+2")
    if recovered.get("exact") != "42":
        raise AssertionError(f"runtime did not recover after cancellation storm: {recovered}")
    return {
        "calls": count,
        "elapsedMs": round((time.perf_counter() - started) * 1000, 3),
        "codes": {"E_CANCELLED": count},
        "recovered": True,
    }


def _worker_crash_recovery() -> dict[str, Any]:
    warm = _call("20+22")
    if warm.get("exact") != "42":
        raise AssertionError(f"could not warm a worker: {warm}")
    with sandbox._WORKER_POOL.condition:
        if not sandbox._WORKER_POOL.available:
            raise AssertionError("worker pool has no warm worker to crash-test")
        victim = sandbox._WORKER_POOL.available[-1]
        victim_pid = victim.process.pid
        victim.process.kill()
        victim.process.wait(timeout=2)
    recovered = _call("21*2")
    if recovered.get("exact") != "42":
        raise AssertionError(f"runtime did not recover from worker crash: {recovered}")
    with sandbox._WORKER_POOL.condition:
        if not sandbox._WORKER_POOL.available:
            raise AssertionError("worker pool has no replacement worker after crash")
        replacement_pid = sandbox._WORKER_POOL.available[-1].process.pid
    if replacement_pid == victim_pid:
        raise AssertionError("dead worker was returned as its own replacement")
    return {
        "victimPid": victim_pid,
        "replacementPid": replacement_pid,
        "recovered": True,
    }


def _batch_probe() -> dict[str, Any]:
    items = [
        {
            "operation": "expression.evaluate",
            "arguments": {"expression": f"{index}+1"},
        }
        for index in range(32)
    ]
    started = time.perf_counter()
    result = sandbox.run_batch(items)
    if result.get("status") != "ok" or result.get("count") != 32:
        raise AssertionError(f"32-item batch failed: {result}")
    duplicate = sandbox.run_batch([items[0] for _ in range(32)])
    if duplicate.get("status") != "ok" or duplicate.get("count") != 32:
        raise AssertionError(f"coalesced batch failed: {duplicate}")
    return {
        "elapsedMs": round((time.perf_counter() - started) * 1000, 3),
        "ordered": [item["index"] for item in result["results"]] == list(range(32)),
        "duplicateLogicalCount": duplicate["count"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calls", type=int, default=10_000)
    parser.add_argument("--output-dir", default=str(ROOT / "build" / "load-checks"))
    arguments = parser.parse_args()
    if arguments.calls < 100:
        parser.error("--calls must be at least 100")

    sandbox._WORKER_POOL.shutdown()
    sandbox._CIRCUIT.reset()
    RUNTIME_TELEMETRY.reset()
    warm = _call("6*7")
    if warm.get("exact") != "42":
        raise AssertionError(f"warm-up failed: {warm}")
    sandbox._WORKER_POOL.shutdown()
    before = _resources()

    serial_timings, serial_results = _timed_calls(arguments.calls, 1)
    _require_success(serial_results, "serial soak")
    burst_count = max(100, arguments.calls // 10)
    cold_burst_timings, cold_burst_results = _timed_calls(burst_count, 8)
    _require_success(cold_burst_results, "8-way scale-up burst")
    warm_burst_timings, warm_burst_results = _timed_calls(burst_count, 8)
    _require_success(warm_burst_results, "8-way warm burst")
    batch = _batch_probe()
    cancellations = _cancellation_storm(12)
    crash = _worker_crash_recovery()

    sandbox._WORKER_POOL.shutdown()
    # A prewarm racing the final shutdown is terminated by its own
    # finish_prewarm path once startup completes; drain that bounded window
    # instead of misreporting an orderly late termination as a leak.
    for _ in range(50):
        if len(psutil.Process().children(recursive=True)) == 0:
            break
        time.sleep(0.1)
    after = _resources()
    delta = {key: after[key] - before[key] for key in before}
    if after["children"] != 0:
        raise AssertionError(f"worker children leaked after shutdown: {after['children']}")
    if delta["threads"] > 2:
        raise AssertionError(f"threads leaked: delta={delta['threads']}")
    if delta["fileDescriptors"] > 4:
        raise AssertionError(f"file descriptors leaked: delta={delta['fileDescriptors']}")
    if delta["rssBytes"] > 256 * 1024 * 1024:
        raise AssertionError(f"parent RSS grew by more than 256 MiB: {delta['rssBytes']}")

    report = {
        "recordedAt": datetime.now(timezone.utc).isoformat(),
        "serial": _summary(serial_timings),
        "burst8ScaleUp": _summary(cold_burst_timings),
        "burst8Warm": _summary(warm_burst_timings),
        "batch": batch,
        "cancellationStorm": cancellations,
        "workerCrash": crash,
        "resources": {"before": before, "after": after, "delta": delta},
        "telemetry": RUNTIME_TELEMETRY.snapshot(),
    }
    output_dir = Path(arguments.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    receipt = output_dir / f"load-check-{stamp}.json"
    receipt.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output_dir / "latest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "PASS", "receipt": str(receipt), **report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
