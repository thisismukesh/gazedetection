"""Replay source: blank frames matching a recorded landmark stream. Implements SPECS/10."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from lookaway.capture.base import intrinsics_from_hfov
from lookaway.perception.replay import read_jsonl
from lookaway.types import Frame, SourceInfo


class ReplaySource:
    """Frames carry the recorded index and timestamp; the image is an empty array."""

    def __init__(self, path: Path | str, width: int, height: int, hfov_rad: float, fps: float):
        self._path = Path(path)
        self._info = SourceInfo(
            f"replay:{path}", width, height, fps, intrinsics_from_hfov(width, height, hfov_rad)
        )
        self._stamps: list[tuple[int, float]] = []
        self._pos = 0

    @property
    def info(self) -> SourceInfo:
        return self._info

    def open(self) -> None:
        self._stamps = [(i, t) for i, t, _ in read_jsonl(self._path)]
        self._pos = 0

    def read(self) -> Frame | None:
        if self._pos >= len(self._stamps):
            return None
        index, t = self._stamps[self._pos]
        self._pos += 1
        return Frame(self._info.source_id, index, t, np.empty((0, 0, 3), np.uint8))

    def close(self) -> None:
        self._stamps = []
