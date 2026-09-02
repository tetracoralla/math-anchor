from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import threading
import time
from typing import Any


MAX_ACTIVE_REQUESTS = 4
MAX_ACTIVE_BATCH_REQUESTS = 3
MAX_QUEUED_REQUESTS = 32
GLOBAL_MEMORY_BUDGET_MB = 4096
CIRCUIT_FAILURE_THRESHOLD = 3
CIRCUIT_OPEN_SECONDS = 1.0


class CombinedCancelEvent:
    def __init__(self, *events: threading.Event | None) -> None:
        self.events = tuple(event for event in events if event is not None)

    def is_set(self) -> bool:
        return any(event.is_set() for event in self.events)


def batch_worker_count(items: list[dict[str, Any]], default_memory_mb: int = 1_024) -> int:
    requested_limits = [
        item.get("memoryMb", default_memory_mb)
        for item in items
        if isinstance(item, dict)
        and isinstance(item.get("memoryMb", default_memory_mb), int)
        and not isinstance(item.get("memoryMb", default_memory_mb), bool)
    ]
    largest_limit = max(requested_limits, default=default_memory_mb)
    memory_bounded_workers = max(1, GLOBAL_MEMORY_BUDGET_MB // max(default_memory_mb, largest_limit))
    return max(1, min(MAX_ACTIVE_BATCH_REQUESTS, len(items), memory_bounded_workers))


@dataclass(frozen=True)
class AdmissionLease:
    memory_mb: int
    request_class: str
    queue_ms: float


@dataclass(frozen=True)
class CircuitPermit:
    """Bind one admitted execution to a circuit generation and probe slot."""

    generation: int
    probe_id: int | None = None


@dataclass
class _Ticket:
    memory_mb: int
    request_class: str


class AdmissionController:
    """Bound request concurrency and requested memory across every caller.

    Interactive calls may pass queued batch work, and batches can occupy at
    most three of four active slots. This leaves a real lane for a coding
    Agent's follow-up calculation instead of letting one 32-item batch own the
    complete worker pool.
    """

    def __init__(
        self,
        *,
        maximum_active: int = MAX_ACTIVE_REQUESTS,
        maximum_batch_active: int = MAX_ACTIVE_BATCH_REQUESTS,
        maximum_queued: int = MAX_QUEUED_REQUESTS,
        memory_budget_mb: int = GLOBAL_MEMORY_BUDGET_MB,
    ) -> None:
        self.maximum_active = maximum_active
        self.maximum_batch_active = min(maximum_batch_active, maximum_active)
        self.maximum_queued = maximum_queued
        self.memory_budget_mb = memory_budget_mb
        self.condition = threading.Condition()
        self.queue: deque[_Ticket] = deque()
        self.active = 0
        self.active_batch = 0
        self.memory_mb = 0

    def acquire(
        self,
        memory_mb: int,
        *,
        request_class: str,
        deadline: float,
        cancel_event: Any | None,
        poll_seconds: float,
    ) -> tuple[AdmissionLease | None, str | None]:
        if request_class not in {"single", "batch"}:
            raise ValueError(f"unsupported request class: {request_class}")
        started = time.monotonic()
        ticket = _Ticket(memory_mb=memory_mb, request_class=request_class)
        with self.condition:
            if len(self.queue) >= self.maximum_queued:
                return None, "overloaded"
            self.queue.append(ticket)
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    self.queue.remove(ticket)
                    self.condition.notify_all()
                    return None, "cancelled"
                if self._may_enter(ticket):
                    self.queue.remove(ticket)
                    self.active += 1
                    self.memory_mb += memory_mb
                    if request_class == "batch":
                        self.active_batch += 1
                    return (
                        AdmissionLease(
                            memory_mb=memory_mb,
                            request_class=request_class,
                            queue_ms=(time.monotonic() - started) * 1000,
                        ),
                        None,
                    )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self.queue.remove(ticket)
                    self.condition.notify_all()
                    return None, "timeout"
                self.condition.wait(timeout=min(remaining, poll_seconds))

    def _may_enter(self, ticket: _Ticket) -> bool:
        if self.active >= self.maximum_active:
            return False
        if self.memory_mb + ticket.memory_mb > self.memory_budget_mb:
            return False
        if (
            ticket.request_class == "batch"
            and self.active_batch >= self.maximum_batch_active
        ):
            return False
        if ticket.request_class == "batch" and any(
            queued.request_class == "single" for queued in self.queue
        ):
            return False
        # A single request is allowed to pass queued batch work. Batch work
        # stays FIFO relative to other batches but yields to every queued
        # single request, guaranteeing an interactive lane without a second
        # worker pool or priority thread executor.
        for queued in self.queue:
            if queued is ticket:
                return True
            if ticket.request_class == "single":
                if queued.request_class == "single":
                    return False
            else:
                return False
        return False

    def release(self, lease: AdmissionLease) -> None:
        with self.condition:
            self.active -= 1
            self.memory_mb -= lease.memory_mb
            if lease.request_class == "batch":
                self.active_batch -= 1
            self.condition.notify_all()

    def snapshot(self) -> dict[str, int]:
        with self.condition:
            return {
                "active": self.active,
                "activeBatch": self.active_batch,
                "queued": len(self.queue),
                "memoryMb": self.memory_mb,
            }


class CircuitBreaker:
    """Fail fast after repeated provider faults, then allow one half-open probe."""

    def __init__(
        self,
        *,
        failure_threshold: int = CIRCUIT_FAILURE_THRESHOLD,
        open_seconds: float = CIRCUIT_OPEN_SECONDS,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.open_seconds = open_seconds
        self.lock = threading.Lock()
        self.consecutive_failures = 0
        self.opened_at: float | None = None
        self.generation = 0
        self.next_probe_id = 0
        self.active_probe_id: int | None = None

    def allow(self) -> tuple[CircuitPermit | None, int | None]:
        now = time.monotonic()
        with self.lock:
            if self.opened_at is None:
                return CircuitPermit(generation=self.generation), None
            remaining = self.open_seconds - (now - self.opened_at)
            if remaining > 0:
                return None, max(1, int(remaining * 1000))
            if self.active_probe_id is not None:
                return None, max(1, int(self.open_seconds * 1000))
            self.next_probe_id += 1
            self.active_probe_id = self.next_probe_id
            return CircuitPermit(
                generation=self.generation,
                probe_id=self.active_probe_id,
            ), None

    def abandon_probe(self, permit: CircuitPermit) -> None:
        """Return a reserved half-open probe that no execution consumed.

        allow() reserves the single probe before admission, so a call that
        then fails admission never reaches the provider. Without returning
        the reservation, half_open_probe stays set while opened_at grows
        stale, and every later call is refused forever.
        """
        with self.lock:
            if (
                permit.generation == self.generation
                and permit.probe_id == self.active_probe_id
            ):
                self.active_probe_id = None

    def record(
        self,
        *,
        outcome: str,
        permit: CircuitPermit | None = None,
    ) -> bool:
        """Record one completed call and return whether this call opened it.

        outcome is "success", "error", or "infrastructure_failure". Only the
        current half-open probe can close an open circuit: caller-side errors
        (timeout, cancellation, memory breach) are not provider-health
        evidence in either direction, so an earlier in-flight completion
        cannot bypass the open -> half-open -> healthy-probe recovery sequence.
        """
        with self.lock:
            is_current_generation = (
                permit is None or permit.generation == self.generation
            )
            is_current_probe = (
                permit is not None
                and is_current_generation
                and permit.probe_id is not None
                and permit.probe_id == self.active_probe_id
            )
            if self.opened_at is not None:
                # Ordinary calls admitted before the circuit opened are stale:
                # neither their later success nor their caller-side error may
                # close the circuit or release the current half-open probe.
                if not is_current_probe:
                    return False
                self.active_probe_id = None
                if outcome == "success":
                    self.consecutive_failures = 0
                    self.opened_at = None
                    return False
                if outcome == "infrastructure_failure":
                    self.consecutive_failures = max(
                        self.consecutive_failures,
                        self.failure_threshold,
                    )
                    self.generation += 1
                    self.opened_at = time.monotonic()
                    return True
                # A caller-side probe error is inconclusive. Keep the circuit
                # open and let the next call reserve a fresh probe.
                return False

            # A probe from an earlier open generation completed after another
            # probe already restored service. It is stale in the closed state
            # as well and must not start or reset a new failure streak.
            if not is_current_generation or (
                permit is not None and permit.probe_id is not None
            ):
                return False
            if outcome == "infrastructure_failure":
                self.consecutive_failures += 1
                if self.consecutive_failures >= self.failure_threshold:
                    self.generation += 1
                    self.opened_at = time.monotonic()
                    return True
                return False
            if outcome == "success":
                self.consecutive_failures = 0
                self.opened_at = None
                return False
            # Inconclusive ordinary outcomes do not change provider health.
            return False

    def reset(self) -> None:
        with self.lock:
            self.consecutive_failures = 0
            self.opened_at = None
            self.active_probe_id = None
            self.generation += 1

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "consecutiveFailures": self.consecutive_failures,
                "state": "open" if self.opened_at is not None else "closed",
                "halfOpenProbe": self.active_probe_id is not None,
            }
