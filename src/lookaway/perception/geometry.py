"""Pure geometry for attention scoring. Implements SPECS/13 steps 1-3, 5-6.

Conventions (OpenCV camera frame: x right, y down, z away from the camera):

* ``R_cam_head`` maps head-local axes to camera axes. Head-local: x = image-right when frontal,
  y = down, z = into the head. ``R = I`` is an upright head facing the camera.
* Forward axis ``f_head = R @ (0, 0, -1)``. Positive yaw turns the face toward -x_cam (image left);
  positive pitch turns it toward +y_cam (down).
* Eye angles are head-local: positive eye_yaw looks toward +x_head, positive eye_pitch looks down.

AC-PER-05 will pin this convention against real MediaPipe output; until then
``tests/fixtures/synth.py`` shares it by construction.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from lookaway.types import FaceObservation, Intrinsics, Mat3, Vec2

Vec3 = NDArray[np.float64]
_FORWARD_LOCAL = np.array([0.0, 0.0, -1.0])


def head_rotation(yaw_rad: float, pitch_rad: float) -> NDArray[np.float64]:
    """R_cam_head = Ry(yaw) @ Rx(pitch)."""
    cy, sy = math.cos(yaw_rad), math.sin(yaw_rad)
    cp, sp = math.cos(pitch_rad), math.sin(pitch_rad)
    ry = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]])
    rx = np.array([[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]])
    return ry @ rx


def _mat(R: Mat3 | NDArray[np.float64]) -> NDArray[np.float64]:
    return np.asarray(R, dtype=np.float64)


def forward_axis(R: Mat3 | NDArray[np.float64]) -> Vec3:
    return _mat(R) @ _FORWARD_LOCAL


def face_position(centroid_px: Vec2, iod_px: float, intr: Intrinsics, ipd_m: float) -> Vec3:
    """p_cam from the centroid ray and depth z = fx * ipd / iod."""
    z = intr.fx * ipd_m / max(iod_px, 1e-6)
    ray = np.array(
        [(centroid_px[0] - intr.cx) / intr.fx, (centroid_px[1] - intr.cy) / intr.fy, 1.0]
    )
    return ray * z


def eye_offsets(obs: FaceObservation, k_yaw_rad: float, k_pitch_rad: float) -> tuple[float, float]:
    """Width-weighted mean (eye_yaw, eye_pitch) in radians from iris offsets (SPECS/13 step 3)."""
    yaw_sum = pitch_sum = w_sum = 0.0
    for iris, (c0, c1), (up, lo) in zip(
        obs.iris_px, obs.eye_corners_px, obs.eye_lids_px, strict=True
    ):
        width = math.hypot(c1[0] - c0[0], c1[1] - c0[1])
        height = abs(lo[1] - up[1])
        if width <= 1e-6 or height <= 1e-6:
            continue
        u = (iris[0] - (c0[0] + c1[0]) / 2) / width
        v = (iris[1] - (up[1] + lo[1]) / 2) / height
        yaw_sum += width * k_yaw_rad * u
        pitch_sum += width * k_pitch_rad * v
        w_sum += width
    if w_sum == 0.0:
        return 0.0, 0.0
    return yaw_sum / w_sum, pitch_sum / w_sum


def gaze_direction(R: Mat3, eye_yaw_rad: float, eye_pitch_rad: float) -> Vec3:
    """Head-forward rotated by the (already weighted) eye angles, in the camera frame."""
    cp = math.cos(eye_pitch_rad)
    local = np.array(
        [math.sin(eye_yaw_rad) * cp, math.sin(eye_pitch_rad), -math.cos(eye_yaw_rad) * cp]
    )
    return _mat(R) @ local


def angle_between(a: Vec3, b: Vec3) -> float:
    c = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    return math.acos(max(-1.0, min(1.0, c)))


def pitch_down(v: Vec3, angle_rad: float) -> Vec3:
    """Rotate ``v`` about the camera x axis toward +y (down in the OpenCV frame)."""
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    rx = np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])
    return rx @ v
