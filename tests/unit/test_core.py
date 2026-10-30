from __future__ import annotations

import time

from lookaway.clock import FakeClock, MonotonicClock
from lookaway.events import EventBus, GazeLost, TrackLost


def test_fake_clock_advances() -> None:
    c = FakeClock(1.0)
    assert c.now() == 1.0
    c.advance(0.5)
    assert c.now() == 1.5


def test_monotonic_clock_non_decreasing() -> None:
    c = MonotonicClock()
    a = c.now()
    time.sleep(0.001)
    assert c.now() >= a


def test_bus_fanout_in_order_and_isolated_errors() -> None:
    bus = EventBus()
    seen: list[str] = []

    def bad(_e: GazeLost) -> None:
        raise RuntimeError("boom")

    bus.subscribe(GazeLost, bad)
    bus.subscribe(GazeLost, lambda e: seen.append(f"a{e.track_id}"))
    bus.subscribe(GazeLost, lambda e: seen.append(f"b{e.track_id}"))
    bus.subscribe(TrackLost, lambda e: seen.append("lost"))
    bus.publish_all(
        [
            GazeLost(t=0.0, track_id=1, zone_id=0, az_rel_rad=0.0, el_rad=0.0, distance_m=None),
            TrackLost(t=1.0, track_id=1, zone_id=0),
        ]
    )
    assert seen == ["a1", "b1", "lost"]
