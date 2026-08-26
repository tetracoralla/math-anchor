from __future__ import annotations

from collections import Counter
from copy import deepcopy
import threading
from typing import Any


class RuntimeTelemetry:
    """Small in-process operational counters with no per-input data."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.counters: Counter[str] = Counter()
        self.timings: dict[str, dict[str, float]] = {}

    def increment(self, name: str, amount: int = 1) -> None:
        with self.lock:
            self.counters[name] += amount

    def observe(self, name: str, milliseconds: float) -> None:
        with self.lock:
            summary = self.timings.setdefault(
                name,
                {"count": 0.0, "totalMs": 0.0, "maxMs": 0.0},
            )
            summary["count"] += 1
            summary["totalMs"] += max(0.0, milliseconds)
            summary["maxMs"] = max(summary["maxMs"], milliseconds)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            timings = deepcopy(self.timings)
            for summary in timings.values():
                count = summary["count"]
                summary["averageMs"] = summary["totalMs"] / count if count else 0.0
                summary["count"] = int(count)
            return {"counters": dict(self.counters), "timings": timings}

    def reset(self) -> None:
        with self.lock:
            self.counters.clear()
            self.timings.clear()


RUNTIME_TELEMETRY = RuntimeTelemetry()
