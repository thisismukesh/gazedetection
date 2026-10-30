from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from lookaway.capture.base import SourceError, intrinsics_from_hfov
from lookaway.capture.slot import LatestFrameSlot
from lookaway.capture.supervisor import BACKOFF_S, ReadSupervisor
from lookaway.capture.video_file import VideoFileSource
from lookaway.clock import FakeClock
from lookaway.events import EventBus, SourceStatus
from lookaway.types import Frame, SourceInfo


def _frame(i: int) -> Frame:
    return Frame("s", i, float(i), np.zeros((2, 2, 3), np.uint8))


def make_video(path: Path, n: int = 12, fps: int = 10) -> None:
    w = cv2.VideoWriter(str(path), cv2.VideoWriter.fourcc(*"mp4v"), fps, (64, 48))
    for i in range(n):
        w.write(np.full((48, 64, 3), i * 10, np.uint8))
    w.release()


def test_AC_CAP_01_video_file_in_order_then_none(tmp_path: Path) -> None:
    p = tmp_path / "v.mp4"
    make_video(p)
    src = VideoFileSource(str(p), FakeClock(), realtime=False)
    src.open()
    frames: list[Frame] = []
    while (f := src.read()) is not None:
        frames.append(f)
    assert [f.index for f in frames] == list(range(len(frames)))
    assert len(frames) == 12
    ts = [f.t_capture for f in frames]
    assert ts == sorted(ts)
    assert src.read() is None
    src.close()


def test_video_file_realtime_paces_with_clock(tmp_path: Path) -> None:
    p = tmp_path / "v.mp4"
    make_video(p, n=5, fps=10)
    clock = FakeClock()
    src = VideoFileSource(str(p), clock, realtime=True)
    src.open()
    assert src.read() is not None  # frame 0 is due immediately
    assert src.read() is None  # frame 1 is due at 0.1 s
    clock.advance(0.11)
    f = src.read()
    assert f is not None and f.index == 1


def test_AC_CAP_02_slot_returns_newest_and_counts_drops() -> None:
    slot = LatestFrameSlot()
    for i in range(4):
        slot.put(_frame(i))
    got = slot.take_latest()
    assert got is not None and got.index == 3
    assert slot.frames_dropped == 3
    assert slot.take_latest() is None


def test_AC_CAP_03_failure_published_once_with_backoff() -> None:
    clock = FakeClock()
    bus = EventBus()
    status: list[SourceStatus] = []
    bus.subscribe(SourceStatus, status.append)

    class Flaky:
        info = SourceInfo("s", 2, 2, 30.0, intrinsics_from_hfov(2, 2, 1.0))
        attempts: list[float] = []
        ok = False

        def open(self) -> None: ...
        def close(self) -> None: ...

        def read(self) -> Frame | None:
            self.attempts.append(clock.now())
            if not self.ok:
                raise SourceError("nope")
            return _frame(0)

    src = Flaky()
    sup = ReadSupervisor(src, clock, bus)
    t_end = sum(BACKOFF_S[:4]) + 6
    while clock.now() < t_end:
        sup.poll()
        clock.advance(0.05)
    gaps = [b - a for a, b in zip(src.attempts, src.attempts[1:], strict=False)]
    assert gaps[:4] == pytest.approx([0.5, 1.0, 2.0, 5.0], abs=0.06)
    assert [s.ok for s in status] == [False]
    src.ok = True
    while sup.poll() is None:
        clock.advance(0.05)
    assert [s.ok for s in status] == [False, True]


def test_AC_CAP_04_default_intrinsics() -> None:
    import math

    k = intrinsics_from_hfov(1280, 720, math.radians(70.0))
    assert k.fx == pytest.approx(914.0, abs=0.5)
    assert k.fy == k.fx
    assert (k.cx, k.cy) == (640.0, 360.0)
