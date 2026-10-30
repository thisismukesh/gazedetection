"""1-euro filter (Casiez, Roussel, Vogel, CHI 2012). Implements SPECS/13 Smoothing."""

from __future__ import annotations

import math

_MIN_DT = 1e-6


def _alpha(cutoff: float, dt: float) -> float:
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


class OneEuroFilter:
    """Adaptive low-pass: cutoff rises with signal speed so lag stays small on fast moves."""

    def __init__(self, min_cutoff: float, beta: float, d_cutoff: float) -> None:
        self._min_cutoff = min_cutoff
        self._beta = beta
        self._d_cutoff = d_cutoff
        self.reset()

    def reset(self) -> None:
        self._t: float | None = None
        self._x = 0.0
        self._dx = 0.0

    def filter(self, t: float, x: float) -> float:
        if self._t is None:
            self._t, self._x, self._dx = t, x, 0.0
            return x
        dt = max(t - self._t, _MIN_DT)
        a_d = _alpha(self._d_cutoff, dt)
        dx_hat = self._dx + a_d * ((x - self._x) / dt - self._dx)
        cutoff = self._min_cutoff + self._beta * abs(dx_hat)
        a = _alpha(cutoff, dt)
        x_hat = self._x + a * (x - self._x)
        self._t, self._x, self._dx = max(t, self._t), x_hat, dx_hat
        return x_hat
