"""OpenCV webcam source. Implements SPECS/10 (WebcamSource)."""

from __future__ import annotations

import sys
from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray

from lookaway.capture.base import SourceError, intrinsics_from_hfov
from lookaway.clock import Clock
from lookaway.types import Frame, SourceInfo


class WebcamSource:
    """Requests the configured size and reports the actual size in ``info``."""

    def __init__(
        self, index: int, width: int, height: int, fps: int, hfov_rad: float, clock: Clock
    ) -> None:
        self._req = (index, width, height, fps)
        self._hfov = hfov_rad
        self._clock = clock
        self._cap: cv2.VideoCapture | None = None
        self._index = 0
        self._info: SourceInfo | None = None

    @property
    def info(self) -> SourceInfo:
        if self._info is None:
            raise SourceError("source not open")
        return self._info

    def open(self) -> None:
        idx, w, h, fps = self._req
        backend = cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_ANY
        cap = cv2.VideoCapture(idx, backend)
        if not cap.isOpened():
            raise SourceError(
                f"cannot open webcam {idx}. On macOS, allow camera access for your terminal in "
                "System Settings > Privacy & Security > Camera; if index 0 is an iPhone "
                "(Continuity Camera), try webcam:1."
            )
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        cap.set(cv2.CAP_PROP_FPS, fps)
        aw, ah = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._info = SourceInfo(
            f"webcam:{idx}", aw, ah, float(fps), intrinsics_from_hfov(aw, ah, self._hfov)
        )
        self._cap = cap

    def read(self) -> Frame | None:
        if self._cap is None:
            raise SourceError("source not open")
        ok, image = self._cap.read()
        if not ok:
            raise SourceError("webcam read failed")
        frame = Frame(
            self.info.source_id, self._index, self._clock.now(), cast(NDArray[np.uint8], image)
        )
        self._index += 1
        return frame

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
