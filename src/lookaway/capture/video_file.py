"""Video file source. Implements SPECS/10 (VideoFileSource). AC-CAP-01."""

from __future__ import annotations

from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray

from lookaway.capture.base import SourceError, intrinsics_from_hfov
from lookaway.clock import Clock
from lookaway.types import Frame, SourceInfo


class VideoFileSource:
    """``realtime=True`` releases a frame only once the clock reaches its file timestamp."""

    def __init__(self, path: str, clock: Clock, realtime: bool, hfov_rad: float = 1.2217) -> None:
        self._path = path
        self._clock = clock
        self._realtime = realtime
        self._hfov = hfov_rad
        self._cap: cv2.VideoCapture | None = None
        self._index = 0
        self._t0 = 0.0
        self._fps = 30.0
        self._info: SourceInfo | None = None

    @property
    def info(self) -> SourceInfo:
        if self._info is None:
            raise SourceError("source not open")
        return self._info

    def open(self) -> None:
        cap = cv2.VideoCapture(self._path)
        if not cap.isOpened():
            raise SourceError(f"cannot open {self._path}")
        self._cap = cap
        self._fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._info = SourceInfo(
            f"video:{self._path}", w, h, self._fps, intrinsics_from_hfov(w, h, self._hfov)
        )
        self._t0 = self._clock.now()

    def read(self) -> Frame | None:
        if self._cap is None:
            raise SourceError("source not open")
        now = self._clock.now()
        if self._realtime and now - self._t0 < self._index / self._fps:
            return None
        ok, image = self._cap.read()
        if not ok:
            return None
        frame = Frame(self.info.source_id, self._index, now, cast(NDArray[np.uint8], image))
        self._index += 1
        return frame

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
