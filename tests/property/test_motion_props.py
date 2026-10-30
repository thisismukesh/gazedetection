"""AC-HEAD-08: motion output respects position, velocity and acceleration limits."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from lookaway.config import load_config
from lookaway.control.factory import limits_from_config
from lookaway.control.motion import AxisMotion

LIM = limits_from_config(load_config().control)
TOL = 1e-6


@given(st.lists(st.floats(-1.2, 1.2), min_size=1, max_size=400))
def test_AC_HEAD_08_limits_hold(targets: list[float]) -> None:
    dt = 0.01
    m = AxisMotion(LIM.yaw_rad, LIM.vel_rad_s, LIM.acc_rad_s2)
    poses = [0.0]
    for tgt in targets:
        poses.append(m.step(max(-LIM.yaw_rad, min(LIM.yaw_rad, tgt)), dt))
    vel = [(b - a) / dt for a, b in zip(poses, poses[1:], strict=False)]
    assert all(abs(p) <= LIM.yaw_rad + TOL for p in poses)
    assert all(abs(v) <= LIM.vel_rad_s + TOL for v in vel)
    acc = [(b - a) / dt for a, b in zip(vel, vel[1:], strict=False)]
    assert all(abs(x) <= LIM.acc_rad_s2 + TOL for x in acc)
