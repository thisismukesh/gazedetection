from __future__ import annotations

import math

import numpy as np
import pytest

from lookaway.perception.geometry import forward_axis, head_rotation
from lookaway.perception.landmarks import (
    IRIS_IMAGE_LEFT,
    IRIS_IMAGE_RIGHT,
    observation_from_landmarks,
    rotation_cv_from_gl,
)

W, H = 1280, 720


def fake_landmarks() -> np.ndarray:
    """478 normalised points; the indexed ones sit at hand-chosen positions."""
    pts = np.full((478, 2), 0.5)
    pts[33], pts[133] = (0.40, 0.45), (0.46, 0.45)  # image-left eye corners
    pts[362], pts[263] = (0.54, 0.45), (0.60, 0.45)  # image-right eye corners
    pts[159], pts[145] = (0.43, 0.43), (0.43, 0.47)  # image-left lids
    pts[386], pts[374] = (0.57, 0.43), (0.57, 0.47)
    pts[IRIS_IMAGE_LEFT], pts[IRIS_IMAGE_RIGHT] = (0.43, 0.45), (0.57, 0.45)
    pts[1] = (0.50, 0.55)
    return pts


def test_iris_sits_between_its_own_eye_corners() -> None:
    obs = observation_from_landmarks(fake_landmarks(), (0.0, 0.0), np.eye(4), 1.0, W, H)
    (l0, l1), (r0, r1) = obs.eye_corners_px
    assert min(l0[0], l1[0]) < obs.iris_px[0][0] < max(l0[0], l1[0])
    assert min(r0[0], r1[0]) < obs.iris_px[1][0] < max(r0[0], r1[0])


def test_pixel_geometry_and_iod() -> None:
    obs = observation_from_landmarks(fake_landmarks(), (0.1, 0.2), np.eye(4), 2.5, W, H)
    assert obs.iod_px == pytest.approx(0.14 * W)
    assert obs.t == 2.5 and obs.blink == (0.1, 0.2)
    x0, y0, x1, y1 = obs.bbox_px
    assert 0 <= x0 < x1 <= W and 0 <= y0 < y1 <= H
    cx = (0.40 + 0.60 + 0.50) / 3 * W
    assert obs.centroid_px[0] == pytest.approx(cx)


def test_frontal_gl_identity_is_identity_in_our_convention() -> None:
    R = rotation_cv_from_gl(np.eye(4))
    assert np.allclose(R, np.eye(3))
    assert np.allclose(forward_axis(R), (0.0, 0.0, -1.0))


def test_scale_is_removed_from_rotation() -> None:
    M = np.eye(4)
    M[:3, :3] *= 7.0
    assert np.allclose(rotation_cv_from_gl(M), np.eye(3))


def test_gl_turn_toward_image_right_maps_to_negative_x_forward_flip() -> None:
    # In OpenGL the canonical face looks along +z. Rotating it by +30 deg about +y swings the
    # forward vector toward +x (image right); the OpenCV forward axis must do the same.
    a = math.radians(30)
    Ry = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
    M = np.eye(4)
    M[:3, :3] = Ry
    f = forward_axis(rotation_cv_from_gl(M))
    assert f[0] == pytest.approx(math.sin(a)) and f[2] == pytest.approx(-math.cos(a))
    # and our own yaw convention agrees: yaw = -30 deg gives the same forward
    assert np.allclose(forward_axis(head_rotation(-a, 0.0)), f)
