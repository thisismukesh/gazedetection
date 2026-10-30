"""Single-slot latest-frame buffer. Implements SPECS/10 §2. AC-CAP-02."""

from __future__ import annotations

import threading

from lookaway.types import Frame


class LatestFrameSlot:
    """Overwrites stale frames; never queues."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame: Frame | None = None
        self.frames_dropped = 0

    def put(self, frame: Frame) -> None:
        with self._lock:
            if self._frame is not None:
                self.frames_dropped += 1
            self._frame = frame

    def take_latest(self) -> Frame | None:
        with self._lock:
            frame, self._frame = self._frame, None
            return frame
