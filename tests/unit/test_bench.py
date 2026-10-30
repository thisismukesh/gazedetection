from __future__ import annotations

import numpy as np

from lookaway.capture.base import intrinsics_from_hfov
from lookaway.clock import FakeClock
from lookaway.config import load_config
from lookaway.observability.bench import format_report, run_bench
from lookaway.types import FaceObservation, Frame, SourceInfo
from tests.fixtures.synth import make_obs


class FakeSource:
    def __init__(self, clock: FakeClock, fps: float = 30.0) -> None:
        self._clock, self._i, self._dt = clock, 0, 1 / fps
        self._info = SourceInfo("fake", 1280, 720, fps, intrinsics_from_hfov(1280, 720, 1.2))
        self._opened = False

    @property
    def info(self) -> SourceInfo:
        assert self._opened, "info read before open(), like the real sources"
        return self._info

    def open(self) -> None:
        self._opened = True

    def close(self) -> None: ...

    def read(self) -> Frame | None:
        self._clock.advance(self._dt)
        f = Frame("fake", self._i, self._clock.now(), np.empty((0, 0, 3), np.uint8))
        self._i += 1
        return f


class CostlyPerception:
    """Advances the fake clock by ``cost_s`` per frame to emulate processing time."""

    def __init__(self, clock: FakeClock, cost_s: float, faces: int = 2) -> None:
        self._clock, self._cost, self._faces = clock, cost_s, faces

    def process(self, frame: Frame) -> list[FaceObservation]:
        self._clock.advance(self._cost)
        return [make_obs(t=frame.t_capture, x_px=300.0 + 300 * k) for k in range(self._faces)]


def bench(cost_s: float):  # noqa: ANN201
    clock = FakeClock()
    return run_bench(load_config(), 3.0, clock, FakeSource(clock), CostlyPerception(clock, cost_s))


def test_fast_pipeline_meets_targets() -> None:
    r = bench(0.010)
    assert r.violations == [] and r.frames > 50
    assert r.fps_processing > 24 and r.stages["total"]["p95"] < 80


def test_slow_processing_violates_both_targets() -> None:
    r = bench(0.100)
    assert len(r.violations) == 2
    assert any("NFR-PERF-01" in v for v in r.violations)
    assert any("NFR-PERF-02" in v for v in r.violations)


def test_report_lists_stages_and_verdict() -> None:
    text = format_report(bench(0.010))
    for needle in ("capture->perception", "perception->score", "total", "PASS"):
        assert needle in text
    assert "FAIL" in format_report(bench(0.100))
