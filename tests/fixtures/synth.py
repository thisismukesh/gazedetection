"""Synthetic FaceObservation generator (SPECS/40). Inverts the scorer's geometry.

Conventions come from ``lookaway.perception.geometry``: head yaw/pitch build ``R_cam_head`` and the
iris offsets are the inverse of ``u = eye_yaw / k_yaw``, ``v = eye_pitch / k_pitch``.
"""

from __future__ import annotations

import math

import numpy as np

from lookaway.config import load_config
from lookaway.perception.geometry import head_rotation
from lookaway.types import FaceObservation, Intrinsics, Mat3

EYE_WIDTH_PER_IOD = 0.45
EYE_HEIGHT_PER_IOD = 0.2

_CFG = load_config()


def intrinsics(width: int = 1280, height: int = 720, hfov_deg: float = 70.0) -> Intrinsics:
    f = (width / 2) / math.tan(math.radians(hfov_deg) / 2)
    return Intrinsics(f, f, width / 2, height / 2)


def p_cam(intr: Intrinsics, x_px: float, y_px: float, distance_m: float) -> np.ndarray:
    """Face position for a pixel and depth z = distance_m."""
    ray = np.array([(x_px - intr.cx) / intr.fx, (y_px - intr.cy) / intr.fy, 1.0])
    return ray * distance_m


def facing_camera_angles(p: np.ndarray) -> tuple[float, float]:
    """(yaw_rad, pitch_rad) that make the head's forward axis point at the camera."""
    n = np.linalg.norm(p)
    return math.atan2(p[0], p[2]), math.asin(-p[1] / n)


def look_target_yaw_deg(p: np.ndarray, target_pitch_deg: float) -> float:
    """Head yaw (pitch 0, eyes centred) that minimises the angle to the look target."""
    a = math.radians(target_pitch_deg)
    to_cam = -p
    t = np.array(
        [to_cam[0], to_cam[1] * math.cos(a) - to_cam[2] * math.sin(a),
         to_cam[1] * math.sin(a) + to_cam[2] * math.cos(a)]
    )  # fmt: skip
    return math.degrees(math.atan2(-t[0], -t[2]))


def make_obs(
    *,
    t: float = 0.0,
    x_px: float = 640.0,
    y_px: float = 360.0,
    distance_m: float = 1.0,
    head_yaw_deg: float | None = None,
    head_pitch_deg: float | None = None,
    eye_yaw_deg: float = 0.0,
    eye_pitch_deg: float = 0.0,
    blink: tuple[float, float] = (0.0, 0.0),
    confidence: float = 1.0,
    intr: Intrinsics | None = None,
    iod_px: float | None = None,
    roll_deg: float = 0.0,
) -> FaceObservation:
    """Head angles default to 'facing the camera'; pass degrees to override."""
    intr = intr or intrinsics()
    yaw0, pitch0 = facing_camera_angles(p_cam(intr, x_px, y_px, distance_m))
    yaw = yaw0 if head_yaw_deg is None else math.radians(head_yaw_deg)
    pitch = pitch0 if head_pitch_deg is None else math.radians(head_pitch_deg)
    iod = iod_px if iod_px is not None else intr.fx * _CFG.attention.ipd_m / distance_m
    R = head_rotation(yaw, pitch)
    ratio = _CFG.attention.eye_radius_ratio
    u = ratio * math.sin(math.radians(eye_yaw_deg))  # inverts SPECS/13 step 3
    v = ratio * math.sin(math.radians(eye_pitch_deg))
    ew, eh = EYE_WIDTH_PER_IOD * iod, EYE_HEIGHT_PER_IOD * iod
    centres = ((x_px - iod / 2, y_px), (x_px + iod / 2, y_px))
    iris = tuple((cx + u * ew, cy + v * ew) for cx, cy in centres)
    corners = tuple(((cx - ew / 2, cy), (cx + ew / 2, cy)) for cx, cy in centres)
    lids = tuple(((cx, cy - eh / 2), (cx, cy + eh / 2)) for cx, cy in centres)
    if roll_deg:  # in-plane head roll: rotate the eye geometry about the face centre
        a = math.radians(roll_deg)
        ca, sa = math.cos(a), math.sin(a)

        def rot(p: tuple[float, float]) -> tuple[float, float]:
            dx, dy = p[0] - x_px, p[1] - y_px
            return (x_px + ca * dx - sa * dy, y_px + sa * dx + ca * dy)

        iris = tuple(rot(p) for p in iris)
        corners = tuple((rot(c[0]), rot(c[1])) for c in corners)
        lids = tuple((rot(c[0]), rot(c[1])) for c in lids)
    mat: Mat3 = tuple(tuple(float(x) for x in row) for row in R)  # type: ignore[assignment]
    return FaceObservation(
        t=t,
        bbox_px=(x_px - 0.9 * iod, y_px - 1.2 * iod, x_px + 0.9 * iod, y_px + 1.2 * iod),
        centroid_px=(x_px, y_px),
        confidence=confidence,
        iod_px=iod,
        R_cam_head=mat,
        iris_px=iris,  # type: ignore[arg-type]
        eye_corners_px=corners,  # type: ignore[arg-type]
        eye_lids_px=lids,  # type: ignore[arg-type]
        blink=blink,
    )
