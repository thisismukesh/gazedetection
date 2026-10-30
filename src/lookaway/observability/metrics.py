"""In-process sliding-window metrics. Implements SPECS/19 Metrics. Thread-safe."""

from __future__ import annotations

import math
import threading
from collections import defaultdict, deque


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    pos = q * (len(sorted_vals) - 1)
    lo, hi = math.floor(pos), math.ceil(pos)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


class Metrics:
    def __init__(self, window_s: float) -> None:
        self._w = window_s
        self._lock = threading.Lock()
        self._ticks: dict[str, deque[float]] = defaultdict(deque)
        self._obs: dict[str, deque[tuple[float, float]]] = defaultdict(deque)
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = {}

    def tick(self, name: str, t: float) -> None:
        with self._lock:
            self._ticks[name].append(t)

    def observe(self, name: str, t: float, value_ms: float) -> None:
        with self._lock:
            self._obs[name].append((t, value_ms))

    def incr(self, name: str, n: float = 1.0) -> None:
        with self._lock:
            self._counters[name] += n

    def gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def latency(self, name: str, now: float) -> dict[str, float]:
        with self._lock:
            q = self._obs.get(name, deque())
            while q and now - q[0][0] > self._w:
                q.popleft()
            vals = sorted(v for _, v in q)
        return {"p50": _percentile(vals, 0.5), "p95": _percentile(vals, 0.95)}

    def snapshot(self, now: float) -> dict[str, float]:
        out: dict[str, float] = {}
        with self._lock:
            for name, q in self._ticks.items():
                while q and now - q[0] > self._w:
                    q.popleft()
                out[name] = len(q) / self._w
            out.update(self._counters)
            out.update(self._gauges)
        return out
