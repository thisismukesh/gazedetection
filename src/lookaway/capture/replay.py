"""Replay source: blank frames matching a recorded landmark stream. Implements SPECS/10."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from lookaway.capture.base import intrinsics_from_hfov
from lookaway.clock import Clock
from lookaway.perception.replay import read_jsonl
from lookaway.types import Frame, SourceInfo


class ReplaySource:
    """Frames carry the recorded index and timestamp; the image is an empty array."""

    def __init__(
        self,
        path: Path | str,
        width: int,
        height: int,
        hfov_rad: float,
        fps: float,
        clock: Clock | None = None,
        loop: bool = False,
    ):
        self._path = Path(path)
        self._info = SourceInfo(
            f"replay:{path}", width, height, fps, intrinsics_from_hfov(width, height, hfov_rad)
        )
        self._stamps: list[tuple[int, float]] = []
        self._pos = 0
        self._clock = clock
        self._loop = loop
        self._t0 = 0.0

    @property
    def info(self) -> SourceInfo:
        return self._info

    def open(self) -> None:
        self._stamps = [(i, t) for i, t, _ in read_jsonl(self._path)]
        self._pos = 0
        self._t0 = self._clock.now() if self._clock is not None else 0.0

    def read(self) -> Frame | None:
        if self._pos >= len(self._stamps):
            if not (self._loop and self._clock is not None and self._stamps):
                return None
            self._pos, self._t0 = 0, self._clock.now()  # fallback demo: loop forever
        index, t = self._stamps[self._pos]
        stamp = t
        if self._clock is not None:
            # Live pacing: release a frame when its recorded offset has elapsed on the clock.
            now = self._clock.now()
            if now - self._t0 < t - self._stamps[0][1]:
                return None
            stamp = now
        self._pos += 1
        return Frame(self._info.source_id, index, stamp, np.empty((0, 0, 3), np.uint8))

    def close(self) -> None:
        self._stamps = []
