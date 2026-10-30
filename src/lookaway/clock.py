"""Injected time source. Implements CLAUDE.md §8 (all time comes from Clock)."""

from __future__ import annotations

import time
from typing import Protocol


class Clock(Protocol):
    def now(self) -> float: ...


class MonotonicClock:
    """Real monotonic seconds. The only module allowed to read the wall clock."""

    def now(self) -> float:
        return time.monotonic()


class FakeClock:
    """Deterministic clock for tests."""

    def __init__(self, t0: float = 0.0) -> None:
        self._t = t0

    def now(self) -> float:
        return self._t

    def advance(self, dt: float) -> None:
        self._t += dt
