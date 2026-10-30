from __future__ import annotations

import math

import pytest

from lookaway.config import load_config
from lookaway.control.factory import limits_from_config, target_params_from_config
from lookaway.control.motion import AxisMotion
from lookaway.control.targeting import target_pose

CFG = load_config().control
TP = target_params_from_config(CFG)
LIM = limits_from_config(CFG)
D = math.radians


def test_yaw_pitch_scaled_by_config() -> None:
    yaw, pitch = target_pose(TP, D(5), D(5))
    assert yaw == pytest.approx(D(5) * CFG.yaw_scale)
    assert pitch == pytest.approx(D(5) * CFG.pitch_scale)


def test_pitch_offset_applies() -> None:
    p = target_params_from_config(CFG.model_copy(update={"pitch_offset_deg": 5.0}))
    assert target_pose(p, 0.0, D(5))[1] == pytest.approx(0.0)


def test_targets_clamped_to_limits() -> None:
    yaw, pitch = target_pose(TP, D(40), D(40))
    assert yaw == pytest.approx(D(CFG.limits.yaw_deg))
    assert pitch == pytest.approx(D(CFG.limits.pitch_deg))
    yaw, pitch = target_pose(TP, -D(40), -D(40))
    assert yaw == pytest.approx(-D(CFG.limits.yaw_deg))


def test_motion_reaches_target_without_exceeding_limits() -> None:
    m = AxisMotion(LIM.yaw_rad, LIM.vel_rad_s, LIM.acc_rad_s2)
    dt = 1 / CFG.rate_hz
    for _ in range(100):
        m.step(D(20), dt)
    assert m.pos == pytest.approx(D(20), abs=D(0.5))


def test_motion_starts_at_neutral_and_holds() -> None:
    m = AxisMotion(LIM.yaw_rad, LIM.vel_rad_s, LIM.acc_rad_s2)
    assert m.step(0.0, 0.01) == 0.0


def test_motion_stops_at_position_limit() -> None:
    m = AxisMotion(D(10), LIM.vel_rad_s, LIM.acc_rad_s2)
    for _ in range(300):
        m.step(D(50), 0.01)
    assert m.pos <= D(10) + 1e-9
