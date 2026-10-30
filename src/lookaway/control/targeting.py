"""Bearing -> head pose targeting. Implements SPECS/16 Targeting, D1, D4. AC-HEAD-01, -02."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TargetParams:
    yaw_scale: float
    pitch_scale: float
    pitch_offset_rad: float
    yaw_limit_rad: float
    pitch_limit_rad: float


def _clamp(x: float, lim: float) -> float:
    return max(-lim, min(lim, x))


def target_pose(p: TargetParams, az_rel_rad: float, el_rad: float) -> tuple[float, float]:
    """(yaw, pitch) in radians. Positive yaw = toward audience's right, positive pitch = up."""
    yaw = _clamp(p.yaw_scale * az_rel_rad, p.yaw_limit_rad)
    pitch = _clamp(p.pitch_scale * (el_rad - p.pitch_offset_rad), p.pitch_limit_rad)
    return yaw, pitch
