"""Read-failure handling with backoff. Implements SPECS/10 §3. AC-CAP-03."""

from __future__ import annotations

from lookaway.capture.base import SourceError
from lookaway.clock import Clock
from lookaway.events import EventBus, SourceStatus
from lookaway.types import CameraSource, Frame

BACKOFF_S = (0.5, 1.0, 2.0, 5.0)  # then 5 s repeating


class ReadSupervisor:
    """Wraps ``CameraSource.read``: publishes SourceStatus once per outage and retries."""

    def __init__(self, source: CameraSource, clock: Clock, bus: EventBus) -> None:
        self._src = source
        self._clock = clock
        self._bus = bus
        self._failures = 0
        self._next_try = 0.0

    def poll(self) -> Frame | None:
        now = self._clock.now()
        if now < self._next_try:
            return None
        try:
            frame = self._src.read()
        except SourceError as e:
            self._on_failure(now, str(e))
            return None
        if frame is not None and self._failures:
            self._failures = 0
            self._bus.publish(SourceStatus(now, self._src.info.source_id, True, "recovered"))
        return frame

    def _on_failure(self, now: float, detail: str) -> None:
        if self._failures == 0:
            self._bus.publish(SourceStatus(now, self._src.info.source_id, False, detail))
        delay = BACKOFF_S[min(self._failures, len(BACKOFF_S) - 1)]
        self._failures += 1
        self._next_try = now + delay
