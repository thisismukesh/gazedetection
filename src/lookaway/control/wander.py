"""Random glances while a head is being looked at. Implements SPECS/16 rule 9, D7. AC-HEAD-09."""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WanderParams:
    yaw_rad: float
    pitch_rad: float
    min_dwell_s: float
    max_dwell_s: float


class Wander:
    """Picks a new random (yaw, pitch) every random dwell; the motion profile smooths it."""

    def __init__(self, params: WanderParams, rng: random.Random) -> None:
        self._p = params
        self._rng = rng
        self._next_t: float | None = None
        self._pose = (0.0, 0.0)

    def target(self, t: float) -> tuple[float, float]:
        if self._next_t is None or t >= self._next_t:
            p = self._p
            self._pose = (
                self._rng.uniform(-p.yaw_rad, p.yaw_rad),
                self._rng.uniform(-p.pitch_rad, p.pitch_rad),
            )
            self._next_t = t + self._rng.uniform(p.min_dwell_s, p.max_dwell_s)
        return self._pose
