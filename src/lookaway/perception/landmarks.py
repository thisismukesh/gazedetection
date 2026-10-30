"""MediaPipe landmarks -> FaceObservation (no mediapipe import). Implements SPECS/11 table.

Index table (MediaPipe canonical 478-point mesh). Pairs are (image-left eye, image-right eye):
the subject's right eye appears on the image left. AC-PER-05 verifies this against real faces.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from lookaway.types import FaceObservation, Mat3, Vec2

IRIS_IMAGE_LEFT, IRIS_IMAGE_RIGHT = 468, 473
CORNERS_IMAGE_LEFT, CORNERS_IMAGE_RIGHT = (33, 133), (362, 263)
LIDS_IMAGE_LEFT, LIDS_IMAGE_RIGHT = (159, 145), (386, 374)
CENTROID_IDX = (33, 263, 1)

_C = np.diag([1.0, -1.0, -1.0])


def rotation_cv_from_gl(matrix4: NDArray[np.float64]) -> NDArray[np.float64]:
    """R_cv = C R_gl C, with scale removed (SPECS/11 Frame conversion)."""
    m = np.asarray(matrix4, dtype=np.float64)[:3, :3]
    norms = np.linalg.norm(m, axis=0)
    r_gl = m / np.where(norms > 1e-9, norms, 1.0)
    return _C @ r_gl @ _C


def _pt(px: NDArray[np.float64], i: int) -> Vec2:
    return (float(px[i, 0]), float(px[i, 1]))


def observation_from_landmarks(
    norm_xy: NDArray[np.float64],
    blink_image_lr: tuple[float, float],
    matrix4: NDArray[np.float64],
    t: float,
    width: int,
    height: int,
    confidence: float = 1.0,
) -> FaceObservation:
    """``norm_xy``: (N, 2+) normalised landmarks; ``blink_image_lr``: (image-left, image-right)."""
    px = np.asarray(norm_xy, dtype=np.float64)[:, :2] * np.array([width, height], dtype=np.float64)
    x0, y0 = np.clip(px.min(axis=0), 0.0, [width, height])
    x1, y1 = np.clip(px.max(axis=0), 0.0, [width, height])
    centroid = px[list(CENTROID_IDX)].mean(axis=0)
    iris = (_pt(px, IRIS_IMAGE_LEFT), _pt(px, IRIS_IMAGE_RIGHT))
    iod = float(np.linalg.norm(np.array(iris[0]) - np.array(iris[1])))
    rot = rotation_cv_from_gl(matrix4)
    mat: Mat3 = tuple(tuple(float(v) for v in row) for row in rot)  # type: ignore[assignment]
    return FaceObservation(
        t=t,
        bbox_px=(float(x0), float(y0), float(x1), float(y1)),
        centroid_px=(float(centroid[0]), float(centroid[1])),
        confidence=confidence,
        iod_px=iod,
        R_cam_head=mat,
        iris_px=iris,
        eye_corners_px=(
            (_pt(px, CORNERS_IMAGE_LEFT[0]), _pt(px, CORNERS_IMAGE_LEFT[1])),
            (_pt(px, CORNERS_IMAGE_RIGHT[0]), _pt(px, CORNERS_IMAGE_RIGHT[1])),
        ),
        eye_lids_px=(
            (_pt(px, LIDS_IMAGE_LEFT[0]), _pt(px, LIDS_IMAGE_LEFT[1])),
            (_pt(px, LIDS_IMAGE_RIGHT[0]), _pt(px, LIDS_IMAGE_RIGHT[1])),
        ),
        blink=blink_image_lr,
    )
