from __future__ import annotations

import atexit
import threading
import time

from .runtime_telemetry import RUNTIME_TELEMETRY
from .sandbox_errors import _error
from .worker_process import (
    WORKER_POLL_SECONDS,
    _ReusableWorker,
    _resident_memory_bytes,
    _start_worker,
)


DEFAULT_TIMEOUT_MS = 10_000
DEFAULT_MEMORY_MB = 1024
MAX_REUSABLE_WORKERS = 4
WORKER_PREWARM_BUDGET_SECONDS = 10.0
MAX_REQUESTS_PER_WORKER = 5_000
WORKER_RECYCLE_RSS_MB = 768
# Route Pint-backed calls toward workers that have already paid at least one
# lazy registry construction cost. A contract test pins this to operation specs.
UNIT_REGISTRY_OPERATIONS = frozenset(
    {
        "units.convert", "quantity.evaluate", "dimension.check",
        "dimension.infer", "dimension.pi_groups",
    }
)


class _WorkerPool:
    def __init__(self, maximum: int = MAX_REUSABLE_WORKERS) -> None:
        self.maximum = maximum
        self.condition = threading.Condition()
        self.available: list[_ReusableWorker] = []
        self.total = 0
        self.generation = 0
        self.prewarm_generation: int | None = None
        self.prewarm_cancel: threading.Event | None = None
        self.prewarm_thread: threading.Thread | None = None
        # Start conservatively with one warm process. Real concurrent demand
        # raises this target, so later recycling restores observed capacity
        # without prestarting four heavyweight symbolic runtimes for a client
        # that only ever makes serial calls.
        self.desired_warm = 1

    def acquire(
        self,
        memory_bytes: int,
        *,
        deadline: float,
        timeout_ms: int,
        cancel_event: threading.Event | None = None,
        prefer_unit_registries: bool = False,
    ) -> tuple[_ReusableWorker | None, dict[str, Any] | None]:
        while True:
            # Evicted workers terminate outside the pool lock: terminate()
            # blocks in kill/wait/join for up to ~2 s per worker, and holding
            # the condition during that stalls every other acquire/release.
            discarded: list[_ReusableWorker] = []
            selected: _ReusableWorker | None = None
            under_warm = False
            try:
                with self.condition:
                    if cancel_event is not None and cancel_event.is_set():
                        return None, _error("E_CANCELLED", "operation was cancelled")
                    while self.available:
                        worker = self._pop_available_worker(
                            prefer_unit_registries=prefer_unit_registries,
                        )
                        resident = _resident_memory_bytes(worker.process.pid)
                        if worker.is_running and (resident is None or resident <= memory_bytes):
                            selected = worker
                            # Handing out a pooled worker is often the last
                            # observation of the pool before it goes quiet;
                            # re-check the warm target here so capacity lost
                            # to earlier evictions is replaced instead of
                            # silently decaying until the next busy spell.
                            under_warm = self._should_replenish(self.generation)
                            break
                        self.total -= 1
                        discarded.append(worker)
                    if selected is None:
                        if self.prewarm_generation == self.generation:
                            remaining = deadline - time.monotonic()
                            if remaining <= 0:
                                return None, _error(
                                    "E_TIMEOUT",
                                    f"operation exceeded {timeout_ms} ms while waiting for a worker",
                                    {"phase": "queue", "timeoutMs": timeout_ms},
                                )
                            self.condition.wait(timeout=min(remaining, WORKER_POLL_SECONDS))
                            continue
                        if self.total < self.maximum:
                            self.total += 1
                            self.desired_warm = max(self.desired_warm, self.total)
                            generation = self.generation
                            break
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            return None, _error(
                                "E_TIMEOUT",
                                f"operation exceeded {timeout_ms} ms while waiting for a worker",
                                {"phase": "queue", "timeoutMs": timeout_ms},
                            )
                        self.condition.wait(timeout=min(remaining, WORKER_POLL_SECONDS))
            finally:
                for victim in discarded:
                    victim.terminate()
            if selected is not None:
                if under_warm:
                    self._prewarm_one()
                return selected, None

        try:
            worker, error = _start_worker(
                memory_bytes,
                deadline=deadline,
                timeout_ms=timeout_ms,
                cancel_event=cancel_event,
            )
        except Exception as startup_exception:
            worker = None
            error = _error(
                "E_RUNTIME",
                f"worker startup failed: {type(startup_exception).__name__}",
                phase="startup",
            )
        if worker is None:
            with self.condition:
                self.total -= 1
                self.condition.notify()
            return None, error
        worker.pool_generation = generation
        return worker, None

    def _pop_available_worker(
        self,
        *,
        prefer_unit_registries: bool,
    ) -> _ReusableWorker:
        if prefer_unit_registries:
            for index in range(len(self.available) - 1, -1, -1):
                if self.available[index].unit_registry_loaded:
                    return self.available.pop(index)
        return self.available.pop()

    def _should_replenish(self, generation: int | None) -> bool:
        with self.condition:
            return (
                generation == self.generation
                and self.total < self.desired_warm
                and self.prewarm_generation is None
            )

    def _prewarm_one(self) -> None:
        RUNTIME_TELEMETRY.increment("workers.adaptivePrewarm")
        warm_worker_pool()

    def release(self, worker: _ReusableWorker, *, reusable: bool) -> None:
        terminate = False
        replenish = False
        with self.condition:
            if reusable:
                worker.requests_completed += 1
                resident = _resident_memory_bytes(worker.process.pid)
                if (
                    worker.requests_completed >= MAX_REQUESTS_PER_WORKER
                    or (
                        resident is not None
                        and resident > WORKER_RECYCLE_RSS_MB * 1024 * 1024
                    )
                ):
                    reusable = False
                    RUNTIME_TELEMETRY.increment("workers.recycled")
            if (
                reusable
                and worker.is_running
                and worker.pool_generation == self.generation
            ):
                worker.reset_stderr()
                self.available.append(worker)
            else:
                self.total -= 1
                terminate = True
                replenish = self._should_replenish(worker.pool_generation)
            self.condition.notify()
        if terminate:
            worker.terminate()
        if replenish:
            self._prewarm_one()

    def reserve_prewarm(self) -> int | None:
        """Reserve one missing observed-capacity slot for async startup."""
        with self.condition:
            if (
                self.total >= self.desired_warm
                or self.prewarm_generation is not None
                or self.prewarm_thread is not None
            ):
                return None
            generation = self.generation
            self.total += 1
            self.prewarm_generation = generation
            self.prewarm_cancel = threading.Event()
            return generation

    def prewarm_cancel_event(self, generation: int) -> threading.Event | None:
        with self.condition:
            if self.prewarm_generation != generation:
                return None
            return self.prewarm_cancel

    def start_prewarm_thread(self, thread: threading.Thread, generation: int) -> bool:
        with self.condition:
            if self.prewarm_generation != generation or self.prewarm_thread is not None:
                return False
            self.prewarm_thread = thread
            thread.start()
            return True

    def owns_prewarm(self, generation: int) -> bool:
        with self.condition:
            return self.prewarm_generation == generation

    def finish_prewarm(
        self,
        worker: _ReusableWorker | None,
        *,
        generation: int,
    ) -> None:
        terminate = worker is not None
        with self.condition:
            owns_reservation = self.prewarm_generation == generation
            if owns_reservation:
                self.prewarm_generation = None
                self.prewarm_cancel = None
            if (
                owns_reservation
                and generation == self.generation
                and worker is not None
                and worker.is_running
            ):
                worker.pool_generation = generation
                worker.reset_stderr()
                self.available.append(worker)
                terminate = False
            elif owns_reservation:
                self.total -= 1
            self.condition.notify_all()
        if terminate and worker is not None:
            worker.terminate()
        with self.condition:
            if self.prewarm_thread is threading.current_thread():
                self.prewarm_thread = None
            self.condition.notify_all()

    def shutdown(self) -> None:
        with self.condition:
            self.generation += 1
            workers = self.available
            self.available = []
            self.total -= len(workers)
            prewarm_thread = self.prewarm_thread
            if self.prewarm_generation is not None:
                self.total -= 1
                self.prewarm_generation = None
            if self.prewarm_cancel is not None:
                self.prewarm_cancel.set()
                self.prewarm_cancel = None
            self.desired_warm = 1
            self.condition.notify_all()
        for worker in workers:
            worker.terminate()
        if prewarm_thread is not None and prewarm_thread is not threading.current_thread():
            # Startup observes the cancellation event inside the same bounded
            # worker boundary. Join it so shutdown does not return while its
            # child pipes, diagnostics descriptor, and output-reader thread are
            # still alive.
            prewarm_thread.join(timeout=2)


_WORKER_POOL = _WorkerPool()
atexit.register(_WORKER_POOL.shutdown)


def warm_worker_pool() -> None:
    """Pre-start one reusable worker on a background thread.

    A session's first math.run or math.batch call otherwise pays the full
    worker startup (~200 ms warm-cache, more on a cold cache) after the
    client is already interactive. Warming overlaps that startup with MCP
    initialization. Best effort: any failure leaves the pool empty and the
    first call starts a worker normally.
    """

    generation = _WORKER_POOL.reserve_prewarm()
    if generation is None:
        return
    prewarm_cancel = _WORKER_POOL.prewarm_cancel_event(generation)
    if prewarm_cancel is None:
        return

    def warm() -> None:
        worker: _ReusableWorker | None = None
        try:
            # A shutdown can land between reserving the slot and reaching
            # this thread; spawning then would create a child nobody owns.
            if _WORKER_POOL.owns_prewarm(generation):
                worker, _unused = _start_worker(
                    DEFAULT_MEMORY_MB * 1024 * 1024,
                    deadline=time.monotonic() + WORKER_PREWARM_BUDGET_SECONDS,
                    timeout_ms=DEFAULT_TIMEOUT_MS,
                    cancel_event=prewarm_cancel,
                )
        except Exception:
            pass
        finally:
            _WORKER_POOL.finish_prewarm(worker, generation=generation)

    thread = threading.Thread(target=warm, name="calculator-worker-prewarm", daemon=True)
    _WORKER_POOL.start_prewarm_thread(thread, generation)
