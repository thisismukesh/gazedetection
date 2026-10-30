from __future__ import annotations

import pytest

from lookaway.observability.metrics import Metrics


def test_rate_over_window() -> None:
    m = Metrics(window_s=10.0)
    for i in range(300):
        m.tick("fps_capture", i / 30)
    assert m.snapshot(9.99)["fps_capture"] == pytest.approx(30.0, rel=0.05)


def test_old_samples_expire() -> None:
    m = Metrics(window_s=2.0)
    for i in range(60):
        m.tick("x", i / 30)
    assert m.snapshot(100.0)["x"] == 0.0


def test_latency_percentiles() -> None:
    m = Metrics(window_s=10.0)
    for i in range(1, 101):
        m.observe("lat", 1.0, float(i))
    snap = m.latency("lat", 1.0)
    assert snap["p50"] == pytest.approx(50.5, abs=1.0)
    assert snap["p95"] == pytest.approx(95.0, abs=1.5)


def test_latency_empty_is_zero() -> None:
    assert Metrics(10.0).latency("none", 0.0) == {"p50": 0.0, "p95": 0.0}


def test_counters_and_gauges() -> None:
    m = Metrics(10.0)
    m.incr("events_total.GazeLost")
    m.incr("events_total.GazeLost", 2)
    m.gauge("faces", 3)
    snap = m.snapshot(0.0)
    assert snap["events_total.GazeLost"] == 3 and snap["faces"] == 3
