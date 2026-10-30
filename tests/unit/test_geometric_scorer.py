from __future__ import annotations

import math

import numpy as np
import pytest

from lookaway.attention.factory import scorer_from_config
from lookaway.config import load_config
from lookaway.perception.geometry import forward_axis, head_rotation
from tests.fixtures.synth import intrinsics, make_obs

CFG = load_config().attention
INTR = intrinsics()
SCORER = scorer_from_config(CFG)


def score(**kw: float | tuple[float, float]):  # noqa: ANN201
    return SCORER.score(make_obs(**kw), INTR)  # type: ignore[arg-type]


def test_convention_frontal_forward_points_at_camera() -> None:
    f = forward_axis(head_rotation(0.0, 0.0))
    assert np.allclose(f, (0.0, 0.0, -1.0))


def test_convention_yaw_pitch_hand_computed() -> None:
    f = forward_axis(head_rotation(math.radians(30), 0.0))
    assert np.allclose(f, (-0.5, 0.0, -math.cos(math.radians(30))))
    f = forward_axis(head_rotation(0.0, math.radians(30)))
    assert np.allclose(f, (0.0, 0.5, -math.cos(math.radians(30))))


def test_AC_ATT_01_frontal_looking() -> None:
    s = score()
    assert math.degrees(s.angle_to_cam_rad) < 5
    assert s.raw_score > 0.9


def test_AC_ATT_02_head_yaw_40_is_away() -> None:
    assert score(head_yaw_deg=40.0, head_pitch_deg=0.0).raw_score < 0.1


def test_AC_ATT_03_edge_face_turned_toward_camera() -> None:
    assert score(x_px=1180.0, y_px=300.0).raw_score > 0.8


def test_AC_ATT_04_eyes_far_off_with_frontal_head() -> None:
    obs = make_obs(head_yaw_deg=0.0, head_pitch_deg=0.0, eye_yaw_deg=25.0, distance_m=0.9)
    assert obs.iod_px >= CFG.eye_weight_iod_full_px
    assert SCORER.score(obs, INTR).raw_score < 0.2


def test_AC_ATT_05_far_face_ignores_eyes() -> None:
    kw = {"head_yaw_deg": 0.0, "head_pitch_deg": 0.0, "iod_px": CFG.eye_weight_iod_min_px}
    with_eyes = score(eye_yaw_deg=25.0, **kw)
    without = score(**kw)
    assert with_eyes.raw_score == pytest.approx(without.raw_score)
    assert with_eyes.angle_to_cam_rad == pytest.approx(without.angle_to_cam_rad)


def test_eye_term_partial_weight_between_thresholds() -> None:
    mid = (CFG.eye_weight_iod_min_px + CFG.eye_weight_iod_full_px) / 2
    kw = {"head_yaw_deg": 0.0, "head_pitch_deg": 0.0, "eye_yaw_deg": 20.0, "iod_px": mid}
    assert math.degrees(score(**kw).angle_to_cam_rad) == pytest.approx(10.0, abs=0.5)


def test_AC_ATT_06_blink_flags_eyes_closed() -> None:
    assert score(blink=(0.8, 0.8)).eyes_closed
    assert not score(blink=(0.8, 0.1)).eyes_closed


def test_blink_removes_eye_term() -> None:
    kw = {"head_yaw_deg": 0.0, "head_pitch_deg": 0.0, "eye_yaw_deg": 25.0}
    assert score(blink=(1.0, 1.0), **kw).raw_score > 0.9


def test_vertical_eye_offset_counts() -> None:
    s = score(head_yaw_deg=0.0, head_pitch_deg=0.0, eye_pitch_deg=20.0)
    assert math.degrees(s.angle_to_cam_rad) == pytest.approx(20.0, abs=0.5)


def test_quality_scales_with_iod_and_confidence() -> None:
    s = score(confidence=0.5)
    assert s.quality == pytest.approx(0.5)
    assert score(iod_px=CFG.eye_weight_iod_full_px / 2).quality == pytest.approx(0.5)
