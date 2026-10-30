"""AC-ATT-07: raw_score is non-increasing as head yaw moves away from facing the camera."""

from __future__ import annotations

import math

from hypothesis import given
from hypothesis import strategies as st

from lookaway.attention.factory import scorer_from_config
from lookaway.config import load_config
from tests.fixtures.synth import facing_camera_angles, intrinsics, make_obs, p_cam

SCORER = scorer_from_config(load_config().attention)
INTR = intrinsics()


def _score(x: float, dist: float, yaw_deg: float, blink: float) -> float:
    obs = make_obs(
        x_px=x, distance_m=dist, head_yaw_deg=yaw_deg, head_pitch_deg=0.0, blink=(blink, blink)
    )
    return SCORER.score(obs, INTR).raw_score


@given(
    x=st.floats(100, 1180),
    dist=st.floats(0.5, 2.0),
    a=st.floats(0, 120),
    b=st.floats(0, 120),
    sign=st.sampled_from([1, -1]),
    blink=st.sampled_from([0.0, 0.4]),
)
def test_AC_ATT_07_monotonic_in_yaw_offset(
    x: float, dist: float, a: float, b: float, sign: int, blink: float
) -> None:
    """Eyes centred, camera-height face: the angle to camera equals |yaw - yaw_facing|."""
    y0 = math.degrees(facing_camera_angles(p_cam(INTR, x, INTR.cy, dist))[0])
    lo, hi = sorted((a, b))
    assert _score(x, dist, y0 + sign * hi, blink) <= _score(x, dist, y0 + sign * lo, blink) + 1e-12
