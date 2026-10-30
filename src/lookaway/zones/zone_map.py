"""Sector zone map with ownership hysteresis. Implements SPECS/15. AC-ZONE-01..05, D3.

Audience frame: ``x_aud = (W - 1) - x``; bearing ``az = -atan((x - cx) / fx)``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from lookaway.types import Intrinsics, Vec2


def pixel_x_to_bearing(x: float, intr: Intrinsics) -> float:
    return -math.atan((x - intr.cx) / intr.fx)


def bearing_to_pixel_x(az_rad: float, intr: Intrinsics) -> float:
    return intr.cx - intr.fx * math.tan(az_rad)


@dataclass(slots=True)
class _Owner:
    zone: int
    candidate: int | None = None
    since: float = 0.0


class SectorZoneMap:
    """One frame split into ``len(boundaries) + 1`` sectors; every track has exactly one owner."""

    def __init__(
        self,
        width: int,
        intrinsics: Intrinsics,
        boundaries: list[float],
        margin_px: float,
        switch_s: float,
    ) -> None:
        self._w = width
        self._intr = intrinsics
        self._edges = [b * width for b in boundaries]
        self._margin = margin_px
        self._switch_s = switch_s
        self._owners: dict[int, _Owner] = {}
        lefts = [0.0, *self._edges]
        rights = [*self._edges, float(width)]
        self._centre_az = [
            pixel_x_to_bearing((width - 1) - (lo + hi) / 2, intrinsics)
            for lo, hi in zip(lefts, rights, strict=True)
        ]

    def _x_aud(self, x: float) -> float:
        return (self._w - 1) - x

    def _containing(self, x_aud: float) -> int:
        return sum(1 for e in self._edges if x_aud >= e)

    def assign(self, track_id: int, centroid_px: Vec2, t: float) -> int:
        x_aud = self._x_aud(centroid_px[0])
        owner = self._owners.get(track_id)
        if owner is None:
            owner = _Owner(self._containing(x_aud))
            self._owners[track_id] = owner
            return owner.zone
        want = self._wanted_neighbour(owner.zone, x_aud)
        if want is None or want != owner.candidate:
            owner.candidate, owner.since = want, t
        elif t - owner.since >= self._switch_s:
            owner.zone, owner.candidate, owner.since = want, None, t
        return owner.zone

    def _wanted_neighbour(self, zone: int, x_aud: float) -> int | None:
        if zone < len(self._edges) and x_aud > self._edges[zone] + self._margin:
            return zone + 1
        if zone > 0 and x_aud < self._edges[zone - 1] - self._margin:
            return zone - 1
        return None

    def forget(self, track_id: int) -> None:
        self._owners.pop(track_id, None)

    def bearing(self, zone_id: int, centroid_px: Vec2) -> tuple[float, float]:
        az = pixel_x_to_bearing(centroid_px[0], self._intr) - self._centre_az[zone_id]
        el = -math.atan((centroid_px[1] - self._intr.cy) / self._intr.fy)
        return az, el
