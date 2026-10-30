from __future__ import annotations

import math
import random

from lookaway.control.wander import Wander, WanderParams

P = WanderParams(
    yaw_rad=math.radians(14), pitch_rad=math.radians(7), min_dwell_s=0.7, max_dwell_s=2.2
)


def test_targets_stay_within_range_and_change() -> None:
    w = Wander(P, random.Random(1))
    seen = set()
    t = 0.0
    for _ in range(2000):
        t += 0.01
        yaw, pitch = w.target(t)
        assert abs(yaw) <= P.yaw_rad and abs(pitch) <= P.pitch_rad
        seen.add((yaw, pitch))
    assert len(seen) >= 8


def test_dwell_between_min_and_max() -> None:
    w = Wander(P, random.Random(2))
    changes: list[float] = []
    last = w.target(0.0)
    t = 0.0
    for _ in range(5000):
        t += 0.01
        cur = w.target(t)
        if cur != last:
            changes.append(t)
            last = cur
    gaps = [b - a for a, b in zip(changes, changes[1:], strict=False)]
    assert gaps and min(gaps) >= P.min_dwell_s - 0.02 and max(gaps) <= P.max_dwell_s + 0.02


def test_deterministic_with_seed() -> None:
    a, b = Wander(P, random.Random(7)), Wander(P, random.Random(7))
    assert [a.target(i * 0.05) for i in range(200)] == [b.target(i * 0.05) for i in range(200)]
