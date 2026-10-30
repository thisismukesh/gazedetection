"""Per-axis motion profile with position, velocity and acceleration limits.

Implements SPECS/16 Motion. AC-HEAD-08. Also protects real servos later.
"""

from __future__ import annotations

import math


class AxisMotion:
    """Velocity-limited, acceleration-limited follower with braking distance."""

    def __init__(self, limit: float, v_max: float, a_max: float) -> None:
        self._limit = limit
        self._v_max = v_max
        self._a_max = a_max
        self.pos = 0.0
        self.vel = 0.0

    def step(self, target: float, dt: float) -> float:
        e = target - self.pos
        v_des = math.copysign(min(self._v_max, math.sqrt(2.0 * self._a_max * abs(e))), e)
        dv = max(-self._a_max * dt, min(self._a_max * dt, v_des - self.vel))
        self.vel += dv
        nxt = self.pos + self.vel * dt
        if abs(nxt) > self._limit:
            nxt = math.copysign(self._limit, nxt)
            self.vel = 0.0
        self.pos = nxt
        return self.pos
