"""Bounded timing, resource, sustained-load, and failure-mix probes."""

from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import random
import statistics
import time
from typing import Any

import psutil

import math_anchor.sandbox as sandbox

from load_profiles import EXPECTED_FAILURES, case_for_index, verify_case


MAX_SUSTAINED_TIMING_SAMPLES = 100_000


def timing_summary(samples: list[float]) -> dict[str, float | int]:
    ordered = sorted(samples)

    def percentile(fraction: float) -> float:
        index = min(len(ordered) - 1, round((len(ordered) - 1) * fraction))
        return ordered[index]

    return {
        "samples": len(samples),
        "p50Ms": round(percentile(0.50), 3),
        "p95Ms": round(percentile(0.95), 3),
        "p99Ms": round(percentile(0.99), 3),
        "meanMs": round(statistics.fmean(samples), 3),
        "maxMs": round(max(samples), 3),
    }


def resources() -> dict[str, int]:
    process = psutil.Process()
    children = process.children(recursive=True)
    child_rss = 0
    for child in children:
        try:
            child_rss += child.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    parent_rss = process.memory_info().rss
    return {
        "rssBytes": parent_rss,
        "childRssBytes": child_rss,
        "treeRssBytes": parent_rss + child_rss,
        "threads": process.num_threads(),
        "fileDescriptors": process.num_fds(),
        "children": len(children),
    }


def _expression_call(expression: str) -> dict[str, Any]:
    return sandbox.run_operation(
        "expression.evaluate",
        {"expression": expression},
        timeout_ms=10_000,
    )


def mixed_failure_storm(count: int = 32) -> dict[str, Any]:
    """Mix expected caller errors with healthy work and prove later recovery."""

    def one(index: int) -> tuple[str, str]:
        if index % 2:
            case = case_for_index(index)
            result = sandbox.run_operation(case.operation, case.arguments, timeout_ms=10_000)
            verify_case(case, result)
            return "ok", case.id
        failure_index = (index // 2) % len(EXPECTED_FAILURES)
        operation, arguments, expected_code = EXPECTED_FAILURES[failure_index]
        result = sandbox.run_operation(operation, arguments, timeout_ms=10_000)
        actual_code = result.get("error", {}).get("code")
        if actual_code != expected_code:
            raise AssertionError(
                f"{operation} expected {expected_code} during failure storm, got {result}"
            )
        if result.get("error", {}).get("retryable") is not False:
            raise AssertionError(f"caller error became retryable during failure storm: {result}")
        return "expected-error", expected_code

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=8, thread_name_prefix="mixed-failure") as executor:
        outcomes = list(executor.map(one, range(count)))
    recovered = _expression_call("40+2")
    if recovered.get("exact") != "42":
        raise AssertionError(f"runtime did not recover after mixed failure storm: {recovered}")
    categories = Counter(category for category, _ in outcomes)
    details = Counter(detail for _, detail in outcomes)
    return {
        "calls": count,
        "elapsedMs": round((time.perf_counter() - started) * 1000, 3),
        "outcomes": dict(sorted(categories.items())),
        "details": dict(sorted(details.items())),
        "recovered": True,
    }


def _rss_trend(samples: list[dict[str, int | float]]) -> dict[str, int | float]:
    if not samples:
        return {
            "samples": 0,
            "startBytes": 0,
            "endBytes": 0,
            "maxBytes": 0,
            "deltaBytes": 0,
            "slopeBytesPerSecond": 0.0,
        }
    rss = [int(sample["treeRssBytes"]) for sample in samples]
    times = [float(sample["elapsedSeconds"]) for sample in samples]
    mean_time = statistics.fmean(times)
    mean_rss = statistics.fmean(rss)
    denominator = sum((item - mean_time) ** 2 for item in times)
    slope = 0.0 if denominator == 0 else sum(
        (when - mean_time) * (value - mean_rss)
        for when, value in zip(times, rss)
    ) / denominator
    return {
        "samples": len(samples),
        "startBytes": rss[0],
        "endBytes": rss[-1],
        "maxBytes": max(rss),
        "deltaBytes": rss[-1] - rss[0],
        "slopeBytesPerSecond": round(slope, 3),
    }


def sustained_profile(
    duration_seconds: float,
    concurrency: int,
    profile: str,
) -> dict[str, Any] | None:
    if duration_seconds <= 0:
        return None
    deadline = time.monotonic() + duration_seconds

    def worker(worker_index: int) -> tuple[list[float], Counter[str], int]:
        timings: list[float] = []
        operations: Counter[str] = Counter()
        completed = 0
        sample_limit = max(1, MAX_SUSTAINED_TIMING_SAMPLES // concurrency)
        randomizer = random.Random(worker_index)
        index = worker_index
        while time.monotonic() < deadline:
            started = time.perf_counter()
            if profile == "coding-agent":
                case = case_for_index(index)
                result = sandbox.run_operation(case.operation, case.arguments, timeout_ms=10_000)
                verify_case(case, result)
                operations[case.id] += 1
            else:
                expected = index % 97 + 1
                result = _expression_call(f"{index % 97}+1")
                if result.get("exact") != str(expected):
                    raise AssertionError(f"sustained expression expected {expected}, got {result}")
                operations["expression.evaluate"] += 1
            elapsed_ms = (time.perf_counter() - started) * 1000
            completed += 1
            if len(timings) < sample_limit:
                timings.append(elapsed_ms)
            else:
                replacement = randomizer.randrange(completed)
                if replacement < sample_limit:
                    timings[replacement] = elapsed_ms
            index += concurrency
        return timings, operations, completed

    started = time.monotonic()
    resource_samples: list[dict[str, int | float]] = []
    with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="sustained") as executor:
        futures = [executor.submit(worker, index) for index in range(concurrency)]
        while not all(future.done() for future in futures):
            snapshot: dict[str, int | float] = resources()
            snapshot["elapsedSeconds"] = round(time.monotonic() - started, 3)
            resource_samples.append(snapshot)
            time.sleep(min(1.0, max(0.05, deadline - time.monotonic())))
        completed = [future.result() for future in futures]
    elapsed = time.monotonic() - started
    timings = [
        timing
        for worker_timings, _, _ in completed
        for timing in worker_timings
    ]
    completed_calls = sum(worker_completed for _, _, worker_completed in completed)
    operations: Counter[str] = Counter()
    for _, worker_operations, _ in completed:
        operations.update(worker_operations)
    return {
        "requestedSeconds": duration_seconds,
        "elapsedSeconds": round(elapsed, 3),
        "concurrency": concurrency,
        "completedCalls": completed_calls,
        "throughputCallsPerSecond": round(completed_calls / elapsed, 3),
        "latency": timing_summary(timings),
        "latencySampling": {
            "method": "per-worker deterministic reservoir",
            "sampledCalls": len(timings),
            "maximumSamples": MAX_SUSTAINED_TIMING_SAMPLES,
        },
        "operationCounts": dict(sorted(operations.items())),
        "rssTrend": _rss_trend(resource_samples),
        "resourceSamples": resource_samples,
    }
