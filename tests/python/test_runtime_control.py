from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import threading
import time

import math_anchor.sandbox as sandbox
from math_anchor import sandbox_testing
from math_anchor.runtime_control import AdmissionController, CircuitBreaker
from math_anchor.runtime_telemetry import RUNTIME_TELEMETRY


def _acquire(
    controller: AdmissionController,
    memory_mb: int,
    request_class: str,
    timeout: float = 1.0,
):
    return controller.acquire(
        memory_mb,
        request_class=request_class,
        deadline=time.monotonic() + timeout,
        cancel_event=None,
        poll_seconds=0.005,
    )


def _permit(breaker: CircuitBreaker):
    permit, retry_after = breaker.allow()
    assert permit is not None
    assert retry_after is None
    return permit


def test_admission_is_bounded_and_memory_weighted() -> None:
    controller = AdmissionController(
        maximum_active=2,
        maximum_batch_active=1,
        maximum_queued=1,
        memory_budget_mb=4096,
    )
    first, error = _acquire(controller, 3072, "single")
    assert first is not None and error is None

    outcome: list[tuple[object, object]] = []
    waiter = threading.Thread(
        target=lambda: outcome.append(_acquire(controller, 2048, "single", 0.2))
    )
    waiter.start()
    deadline = time.monotonic() + 1
    while controller.snapshot()["queued"] != 1 and time.monotonic() < deadline:
        time.sleep(0.005)

    rejected, reason = _acquire(controller, 256, "single")
    assert rejected is None
    assert reason == "overloaded"
    controller.release(first)
    waiter.join(timeout=1)
    assert not waiter.is_alive()
    second, error = outcome[0]
    assert second is not None and error is None
    controller.release(second)
    assert controller.snapshot() == {
        "active": 0,
        "activeBatch": 0,
        "queued": 0,
        "memoryMb": 0,
    }


def test_single_request_passes_queued_batch_and_uses_reserved_lane() -> None:
    controller = AdmissionController(
        maximum_active=2,
        maximum_batch_active=1,
        maximum_queued=4,
        memory_budget_mb=4096,
    )
    active_batch, error = _acquire(controller, 1024, "batch")
    assert active_batch is not None and error is None
    batch_outcome: list[tuple[object, object]] = []
    queued_batch = threading.Thread(
        target=lambda: batch_outcome.append(_acquire(controller, 1024, "batch"))
    )
    queued_batch.start()
    deadline = time.monotonic() + 1
    while controller.snapshot()["queued"] != 1 and time.monotonic() < deadline:
        time.sleep(0.005)

    single, error = _acquire(controller, 1024, "single")
    assert single is not None and error is None
    assert controller.snapshot()["activeBatch"] == 1
    controller.release(single)
    controller.release(active_batch)
    queued_batch.join(timeout=1)
    admitted_batch, error = batch_outcome[0]
    assert admitted_batch is not None and error is None
    controller.release(admitted_batch)


def test_circuit_breaker_opens_and_allows_one_half_open_probe(monkeypatch) -> None:
    clock = [100.0]
    monkeypatch.setattr("math_anchor.runtime_control.time.monotonic", lambda: clock[0])
    breaker = CircuitBreaker(failure_threshold=2, open_seconds=1.0)
    assert breaker.record(
        outcome="infrastructure_failure",
        permit=_permit(breaker),
    ) is False
    assert breaker.record(
        outcome="infrastructure_failure",
        permit=_permit(breaker),
    ) is True
    permit, retry_after = breaker.allow()
    assert permit is None
    assert retry_after == 1000
    clock[0] += 1.1
    probe = _permit(breaker)
    assert probe.probe_id is not None
    assert breaker.allow()[0] is None
    breaker.record(outcome="success", permit=probe)
    assert _permit(breaker).probe_id is None


def test_unused_half_open_probe_is_returned_and_regrantable(monkeypatch) -> None:
    clock = [100.0]
    monkeypatch.setattr("math_anchor.runtime_control.time.monotonic", lambda: clock[0])
    breaker = CircuitBreaker(failure_threshold=1, open_seconds=1.0)
    assert breaker.record(outcome="infrastructure_failure") is True
    clock[0] += 1.1
    first_probe = _permit(breaker)
    assert first_probe.probe_id is not None
    # The call that reserved the probe failed before execution; without
    # returning the reservation every later call is refused forever.
    breaker.abandon_probe(first_probe)
    assert breaker.snapshot()["halfOpenProbe"] is False
    second_probe = _permit(breaker)
    breaker.record(outcome="success", permit=second_probe)
    assert breaker.snapshot()["state"] == "closed"


def test_open_circuit_is_closed_only_by_a_successful_call(monkeypatch) -> None:
    clock = [100.0]
    monkeypatch.setattr("math_anchor.runtime_control.time.monotonic", lambda: clock[0])
    breaker = CircuitBreaker(failure_threshold=2, open_seconds=1.0)
    stale_error = _permit(breaker)
    breaker.record(outcome="infrastructure_failure", permit=_permit(breaker))
    assert breaker.record(
        outcome="infrastructure_failure",
        permit=_permit(breaker),
    ) is True
    # An in-flight caller-side error (timeout, cancellation, memory) that
    # completes while the circuit is open must not close it.
    breaker.record(outcome="error", permit=stale_error)
    assert breaker.snapshot()["state"] == "open"
    clock[0] += 1.1
    probe = _permit(breaker)
    assert breaker.record(outcome="success", permit=probe) is False
    assert breaker.snapshot()["state"] == "closed"


def test_inconclusive_outcomes_neither_close_nor_reset_the_streak() -> None:
    breaker = CircuitBreaker(failure_threshold=3, open_seconds=1.0)
    breaker.record(outcome="infrastructure_failure", permit=_permit(breaker))
    breaker.record(outcome="error", permit=_permit(breaker))
    breaker.record(outcome="infrastructure_failure", permit=_permit(breaker))
    assert breaker.record(
        outcome="infrastructure_failure",
        permit=_permit(breaker),
    ) is True
    assert breaker.snapshot()["state"] == "open"
    breaker.reset()
    breaker.record(outcome="infrastructure_failure", permit=_permit(breaker))
    breaker.record(outcome="error", permit=_permit(breaker))
    # Only success proves the provider recovered and resets the streak.
    breaker.record(outcome="success", permit=_permit(breaker))
    breaker.record(outcome="infrastructure_failure", permit=_permit(breaker))
    assert breaker.record(
        outcome="infrastructure_failure",
        permit=_permit(breaker),
    ) is False
    assert breaker.snapshot()["state"] == "closed"


def test_stale_success_cannot_close_an_open_circuit(monkeypatch) -> None:
    clock = [100.0]
    monkeypatch.setattr("math_anchor.runtime_control.time.monotonic", lambda: clock[0])
    breaker = CircuitBreaker(failure_threshold=2, open_seconds=1.0)
    stale_success = _permit(breaker)
    first_failure = _permit(breaker)
    second_failure = _permit(breaker)

    breaker.record(outcome="infrastructure_failure", permit=first_failure)
    breaker.record(outcome="infrastructure_failure", permit=second_failure)
    assert breaker.snapshot()["state"] == "open"

    breaker.record(outcome="success", permit=stale_success)
    assert breaker.snapshot()["state"] == "open"
    assert breaker.allow()[0] is None


def test_stale_completion_cannot_release_the_current_half_open_probe(
    monkeypatch,
) -> None:
    clock = [100.0]
    monkeypatch.setattr("math_anchor.runtime_control.time.monotonic", lambda: clock[0])
    breaker = CircuitBreaker(failure_threshold=1, open_seconds=1.0)
    stale = _permit(breaker)
    breaker.record(outcome="infrastructure_failure", permit=_permit(breaker))
    clock[0] += 1.1
    current_probe = _permit(breaker)

    breaker.record(outcome="error", permit=stale)
    assert breaker.snapshot()["halfOpenProbe"] is True
    assert breaker.allow()[0] is None

    breaker.record(outcome="success", permit=current_probe)
    assert breaker.snapshot()["state"] == "closed"


def test_pre_open_completion_cannot_pollute_the_recovered_generation(
    monkeypatch,
) -> None:
    clock = [100.0]
    monkeypatch.setattr("math_anchor.runtime_control.time.monotonic", lambda: clock[0])
    breaker = CircuitBreaker(failure_threshold=2, open_seconds=1.0)
    stale = _permit(breaker)
    breaker.record(outcome="infrastructure_failure", permit=_permit(breaker))
    breaker.record(outcome="infrastructure_failure", permit=_permit(breaker))
    clock[0] += 1.1
    breaker.record(outcome="success", permit=_permit(breaker))
    assert breaker.snapshot()["state"] == "closed"

    current_failure = _permit(breaker)
    breaker.record(outcome="infrastructure_failure", permit=current_failure)
    breaker.record(outcome="success", permit=stale)
    assert breaker.snapshot()["consecutiveFailures"] == 1

    breaker.record(outcome="infrastructure_failure", permit=stale)
    assert breaker.snapshot()["state"] == "closed"
    assert breaker.snapshot()["consecutiveFailures"] == 1


def test_admission_failure_releases_the_reserved_half_open_probe(monkeypatch) -> None:
    isolated = CircuitBreaker(failure_threshold=2, open_seconds=0.05)
    monkeypatch.setattr(sandbox, "_CIRCUIT", isolated)
    monkeypatch.setattr(
        sandbox,
        "_execute_admitted_operation",
        lambda *_args, **_kwargs: sandbox._error("E_RUNTIME", "simulated provider fault"),
    )
    for _ in range(2):
        assert sandbox.run_operation(
            "expression.evaluate", {"expression": "1+1"}
        )["error"]["code"] == "E_RUNTIME"
    assert isolated.snapshot()["state"] == "open"
    time.sleep(0.06)

    # The probe call times out while waiting for admission and never reaches
    # the provider; its reservation must be returned.
    original_admission = sandbox._ADMISSION
    monkeypatch.setattr(
        sandbox,
        "_ADMISSION",
        AdmissionController(maximum_active=0, maximum_batch_active=0, maximum_queued=4),
    )
    timed_out = sandbox.run_operation(
        "expression.evaluate", {"expression": "1+1"}, timeout_ms=100
    )
    assert timed_out["error"]["code"] == "E_TIMEOUT"
    assert timed_out["error"]["phase"] == "admission"
    monkeypatch.setattr(sandbox, "_ADMISSION", original_admission)

    # Before the fix this call was E_UNAVAILABLE forever; after it the freed
    # probe executes, fails as the simulated provider fault, and reopens the
    # circuit for a fresh window instead of stranding the runtime.
    probe = sandbox.run_operation("expression.evaluate", {"expression": "1+1"})
    assert probe["error"]["code"] == "E_RUNTIME"
    assert isolated.snapshot()["state"] == "open"


def test_batch_item_supervision_failure_becomes_item_envelope(monkeypatch) -> None:
    def fake_run(operation, arguments, **_limits):
        if arguments["expression"] == "boom":
            raise RuntimeError("simulated supervision crash")
        return {"status": "ok", "operation": operation, "kind": "scalar", "exact": "42"}

    monkeypatch.setattr(sandbox, "run_operation", fake_run)
    result = sandbox.run_batch(
        [
            {"operation": "expression.evaluate", "arguments": {"expression": "6*7"}},
            {"operation": "expression.evaluate", "arguments": {"expression": "boom"}},
            {"operation": "expression.evaluate", "arguments": {"expression": "1+1"}},
        ]
    )
    assert result["status"] == "partial"
    assert [item["index"] for item in result["results"]] == [0, 1, 2]
    assert result["results"][0]["exact"] == "42"
    assert result["results"][1]["error"]["code"] == "E_RUNTIME"
    assert "RuntimeError" in result["results"][1]["error"]["message"]
    assert result["results"][2]["exact"] == "42"


def test_batch_coalesces_identical_items_without_changing_logical_results(monkeypatch) -> None:
    calls = 0

    def fake_run(operation, arguments, **_limits):
        nonlocal calls
        calls += 1
        return {"status": "ok", "operation": operation, "kind": "scalar", "exact": "42"}

    monkeypatch.setattr(sandbox, "run_operation", fake_run)
    result = sandbox.run_batch(
        [
            {"operation": "expression.evaluate", "arguments": {"expression": "6*7"}}
            for _ in range(8)
        ]
    )
    assert result["status"] == "ok"
    assert calls == 1
    assert [item["index"] for item in result["results"]] == list(range(8))
    assert all(item["exact"] == "42" for item in result["results"])


def test_batch_output_abort_signals_running_siblings(monkeypatch) -> None:
    cancelled: list[str] = []
    all_started = threading.Barrier(3)

    def fake_run(operation, arguments, *, cancel_event, **_limits):
        all_started.wait(timeout=1)
        if arguments["value"] == "large":
            return {
                "status": "ok",
                "operation": operation,
                "kind": "scalar",
                "exact": "9" * 2_000,
            }
        while not cancel_event.is_set():
            time.sleep(0.005)
        cancelled.append(arguments["value"])
        return sandbox._error("E_CANCELLED", "operation was cancelled")

    monkeypatch.setattr(sandbox, "run_operation", fake_run)
    started = time.monotonic()
    result = sandbox.run_batch(
        [
            {"operation": "test.echo", "arguments": {"value": "large"}},
            {"operation": "test.echo", "arguments": {"value": "slow-1"}},
            {"operation": "test.echo", "arguments": {"value": "slow-2"}},
        ],
        max_output_bytes=1_024,
    )
    assert result["error"]["code"] == "E_OUTPUT_LIMIT"
    assert set(cancelled) == {"slow-1", "slow-2"}
    assert time.monotonic() - started < 0.5


def test_repeated_provider_failures_trip_fast_unavailable(monkeypatch) -> None:
    isolated = CircuitBreaker(failure_threshold=3, open_seconds=10)
    monkeypatch.setattr(sandbox, "_CIRCUIT", isolated)
    monkeypatch.setattr(
        sandbox,
        "_execute_admitted_operation",
        lambda *_args, **_kwargs: sandbox._error("E_RUNTIME", "simulated provider fault"),
    )
    for _ in range(3):
        assert sandbox.run_operation(
            "expression.evaluate", {"expression": "1+1"}
        )["error"]["code"] == "E_RUNTIME"
    unavailable = sandbox.run_operation(
        "expression.evaluate", {"expression": "1+1"}
    )
    assert unavailable["error"]["code"] == "E_UNAVAILABLE"
    assert unavailable["error"]["retryable"] is True
    assert unavailable["error"]["retryAfterMs"] > 0


def test_concurrent_stale_success_cannot_bypass_half_open_recovery(monkeypatch) -> None:
    isolated = CircuitBreaker(failure_threshold=3, open_seconds=10)
    monkeypatch.setattr(sandbox, "_CIRCUIT", isolated)
    ready = threading.Barrier(4)
    release_success = threading.Event()

    def fake_execute(request_line: str, **_limits):
        label = json.loads(request_line)["arguments"]["label"]
        if label == "slow-success" or label.startswith("failure-"):
            ready.wait(timeout=2)
        if label == "slow-success":
            release_success.wait(timeout=2)
            return {"status": "ok", "operation": "test.echo", "label": label}
        if label.startswith("failure-"):
            return sandbox._error("E_RUNTIME", "simulated provider fault")
        return {"status": "ok", "operation": "test.echo", "label": label}

    monkeypatch.setattr(sandbox, "_execute_admitted_operation", fake_execute)
    with ThreadPoolExecutor(max_workers=4) as executor:
        slow = executor.submit(
            sandbox.run_operation,
            "test.echo",
            {"label": "slow-success"},
            timeout_ms=5_000,
            memory_mb=256,
        )
        failures = [
            executor.submit(
                sandbox.run_operation,
                "test.echo",
                {"label": f"failure-{index}"},
                timeout_ms=5_000,
                memory_mb=256,
            )
            for index in range(3)
        ]
        assert {
            future.result(timeout=2)["error"]["code"]
            for future in failures
        } == {"E_RUNTIME"}
        assert isolated.snapshot()["state"] == "open"
        refused = sandbox.run_operation(
            "test.echo",
            {"label": "while-open"},
            timeout_ms=5_000,
            memory_mb=256,
        )
        assert refused["error"]["code"] == "E_UNAVAILABLE"

        release_success.set()
        assert slow.result(timeout=2)["status"] == "ok"

    assert isolated.snapshot()["state"] == "open"
    still_refused = sandbox.run_operation(
        "test.echo",
        {"label": "still-open"},
        timeout_ms=5_000,
        memory_mb=256,
    )
    assert still_refused["error"]["code"] == "E_UNAVAILABLE"


def test_runtime_telemetry_records_only_operational_aggregates(monkeypatch) -> None:
    RUNTIME_TELEMETRY.reset()
    monkeypatch.setattr(
        sandbox,
        "_execute_admitted_operation",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "operation": "expression.evaluate",
            "kind": "scalar",
            "exact": "42",
        },
    )
    sandbox.run_operation("expression.evaluate", {"expression": "secret-value"})
    snapshot = RUNTIME_TELEMETRY.snapshot()
    assert snapshot["counters"]["requests.total"] == 1
    assert snapshot["counters"]["requests.single"] == 1
    assert snapshot["timings"]["requests.totalMs"]["count"] == 1
    assert "secret-value" not in repr(snapshot)


def test_cancelled_worker_start_is_not_reported_as_provider_failure(monkeypatch) -> None:
    def cancelled_start(*_args, **_kwargs):
        return None, sandbox._error("E_CANCELLED", "startup cancelled")

    RUNTIME_TELEMETRY.reset()
    process_runtime = sandbox_testing.process_runtime()
    monkeypatch.setattr(process_runtime, "_start_worker_impl", cancelled_start)
    worker, error = process_runtime._start_worker(
        sandbox.DEFAULT_MEMORY_MB * 1024 * 1024,
        deadline=time.monotonic() + 1,
        timeout_ms=1_000,
        cancel_event=threading.Event(),
    )

    assert worker is None
    assert error is not None and error["error"]["code"] == "E_CANCELLED"
    counters = RUNTIME_TELEMETRY.snapshot()["counters"]
    assert counters["workers.startCancelled"] == 1
    assert "workers.startFailed" not in counters


def test_worker_recycles_after_bounded_request_count_and_adaptively_refills(
    monkeypatch,
) -> None:
    sandbox._WORKER_POOL.shutdown()
    monkeypatch.setattr(sandbox_testing.pool_runtime(), "MAX_REQUESTS_PER_WORKER", 2)
    try:
        first = sandbox.run_operation(
            "expression.evaluate", {"expression": "6*7"}, timeout_ms=2_000
        )
        assert first["exact"] == "42"
        first_pid = sandbox._WORKER_POOL.available[-1].process.pid
        second = sandbox.run_operation(
            "expression.evaluate", {"expression": "7*8"}, timeout_ms=2_000
        )
        assert second["exact"] == "56"

        # The retiring call schedules a replacement in the background. A new
        # request either consumes that prewarm or starts the replacement itself.
        third = sandbox.run_operation(
            "expression.evaluate", {"expression": "9*9"}, timeout_ms=2_000
        )
        assert third["exact"] == "81"
        assert sandbox._WORKER_POOL.available[-1].process.pid != first_pid
    finally:
        sandbox._WORKER_POOL.shutdown()


def test_acquire_refills_observed_warm_capacity_lost_to_eviction() -> None:
    sandbox._WORKER_POOL.shutdown()
    pool = sandbox._WORKER_POOL
    try:
        first = sandbox.run_operation(
            "expression.evaluate", {"expression": "6*7"}, timeout_ms=2_000
        )
        assert first["exact"] == "42"
        with pool.condition:
            # Simulate the state after a resident-memory eviction dropped a
            # warm worker: observed capacity (desired_warm) above the pool's
            # actual total. The next acquire hands out a healthy pooled
            # worker and must schedule a replacement, or every later clean
            # acquire silently runs on a decayed pool.
            pool.desired_warm = 2

        second = sandbox.run_operation(
            "expression.evaluate", {"expression": "7*8"}, timeout_ms=2_000
        )
        assert second["exact"] == "56"

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with pool.condition:
                if pool.total >= 2 and len(pool.available) >= 2:
                    break
            time.sleep(0.02)
        with pool.condition:
            assert pool.total >= 2
            assert len(pool.available) >= 2
    finally:
        sandbox._WORKER_POOL.shutdown()
