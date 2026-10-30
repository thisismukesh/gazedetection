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


def test_looking_at_display_below_camera_counts_as_looking() -> None:
    """The heads are drawn below the lens: a head pitched down by the target offset is 'looking'."""
    s = score(head_yaw_deg=0.0, head_pitch_deg=CFG.look_target_pitch_deg)
    assert s.raw_score > 0.95
    assert math.degrees(s.angle_to_cam_rad) == pytest.approx(CFG.look_target_pitch_deg, abs=0.5)


def test_looking_up_is_not_looking_at_the_display() -> None:
    up = score(head_yaw_deg=0.0, head_pitch_deg=-CFG.look_target_pitch_deg)
    down = score(head_yaw_deg=0.0, head_pitch_deg=CFG.look_target_pitch_deg)
    assert up.raw_score < down.raw_score


def test_zero_offset_matches_plain_angle_to_camera() -> None:
    from dataclasses import replace

    from lookaway.attention.geometric import GeometricScorer

    plain = GeometricScorer(replace(SCORER._p, look_target_pitch_rad=0.0))  # noqa: SLF001
    obs = make_obs(head_yaw_deg=10.0, head_pitch_deg=0.0)
    s = plain.score(obs, INTR)
    expected = 1 / (1 + math.exp(-(CFG.cone_rad - s.angle_to_cam_rad) / CFG.softness_rad))
    assert s.raw_score == pytest.approx(expected)


def test_a_real_look_away_from_the_display_is_still_away() -> None:
    assert score(head_yaw_deg=35.0, head_pitch_deg=CFG.look_target_pitch_deg).raw_score < 0.1


def test_sample_exposes_head_and_gaze_directions_for_the_overlay() -> None:
    s = score(head_yaw_deg=0.0, head_pitch_deg=0.0)
    assert np.allclose(s.head_dir, (0.0, 0.0, -1.0), atol=1e-9)
    assert np.allclose(s.gaze_dir, s.head_dir, atol=1e-9)  # eyes centred
    assert math.isclose(sum(c * c for c in s.gaze_dir), 1.0, rel_tol=1e-9)


def test_gaze_dir_includes_the_eye_term_head_dir_does_not() -> None:
    s = score(head_yaw_deg=0.0, head_pitch_deg=0.0, eye_yaw_deg=20.0, distance_m=0.9)
    assert s.gaze_dir[0] > 0.3  # eyes looking toward +x of the head
    assert abs(s.head_dir[0]) < 1e-9


# --- D13: eye model -----------------------------------------------------------------------


def _eye_angles(**kw: float) -> tuple[float, float]:
    from lookaway.perception.geometry import eye_offsets

    return tuple(  # type: ignore[return-value]
        math.degrees(a) for a in eye_offsets(make_obs(**kw), CFG.eye_radius_ratio)
    )


def test_eye_angles_round_trip_through_the_eyeball_model() -> None:
    yaw, pitch = _eye_angles(eye_yaw_deg=25.0, eye_pitch_deg=-15.0)
    assert yaw == pytest.approx(25.0, abs=0.01) and pitch == pytest.approx(-15.0, abs=0.01)


def test_eye_signs_looking_image_right_and_down_are_positive() -> None:
    yaw, pitch = _eye_angles(eye_yaw_deg=20.0, eye_pitch_deg=20.0)
    assert yaw > 0 and pitch > 0
    s = score(head_yaw_deg=0.0, head_pitch_deg=0.0, eye_yaw_deg=20.0, eye_pitch_deg=20.0)
    assert s.gaze_dir[0] > 0.2 and s.gaze_dir[1] > 0.2  # gaze vector: right and down


def test_gain_matches_a_real_eyeball() -> None:
    """A 30 degree eye rotation moves the iris by about 0.4 * sin(30) = 0.2 eye widths."""
    obs = make_obs(eye_yaw_deg=30.0, distance_m=0.9)
    (c0, c1), iris = obs.eye_corners_px[0], obs.iris_px[0]
    u = (iris[0] - (c0[0] + c1[0]) / 2) / (c1[0] - c0[0])
    assert u == pytest.approx(0.20, abs=0.01)


def test_eye_angles_follow_head_roll() -> None:
    flat = _eye_angles(eye_yaw_deg=18.0, eye_pitch_deg=10.0)
    for roll in (-25.0, 15.0, 40.0):
        rolled = _eye_angles(eye_yaw_deg=18.0, eye_pitch_deg=10.0, roll_deg=roll)
        assert rolled == pytest.approx(flat, abs=0.01)


def test_eyelid_landmarks_do_not_affect_the_eye_angle() -> None:
    from dataclasses import replace

    from lookaway.perception.geometry import eye_offsets

    obs = make_obs(eye_yaw_deg=12.0, eye_pitch_deg=-8.0)
    lids = tuple(((x, y + 5.0), (x, y - 3.0)) for (x, y), _ in obs.eye_lids_px)  # lids drift
    moved = replace(obs, eye_lids_px=lids)  # type: ignore[arg-type]
    assert eye_offsets(moved, CFG.eye_radius_ratio) == eye_offsets(obs, CFG.eye_radius_ratio)


def test_extreme_iris_offset_is_clamped_not_nan() -> None:
    from dataclasses import replace

    from lookaway.perception.geometry import eye_offsets

    obs = make_obs()
    far = replace(obs, iris_px=((obs.iris_px[0][0] + 500, obs.iris_px[0][1]), obs.iris_px[1]))
    yaw, pitch = eye_offsets(far, CFG.eye_radius_ratio)
    assert math.isfinite(yaw) and math.isfinite(pitch) and abs(yaw) <= math.pi / 2
