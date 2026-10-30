from __future__ import annotations

import math

import pytest

from lookaway.config import load_config
from lookaway.control.drivers.simulated import RecordingHeadDriver
from lookaway.control.factory import build_head_controller
from lookaway.events import EventBus, GazeLost, HeadModeChanged, TrackReleased, TrackUpdated
from lookaway.types import AttentionState, HeadMode

C = load_config().control
D = math.radians


class Rig:
    def __init__(self) -> None:
        self.bus = EventBus()
        self.drivers = [RecordingHeadDriver() for _ in range(3)]
        self.heads = [build_head_controller(C, k, self.drivers[k], self.bus) for k in range(3)]
        self.changes: list[HeadModeChanged] = []
        self.bus.subscribe(HeadModeChanged, self.changes.append)
        self.t = 0.0

    def run(self, secs: float) -> None:
        for _ in range(round(secs * C.rate_hz)):
            self.t += 1 / C.rate_hz
            for h in self.heads:
                h.tick(self.t)

    def pose(self, k: int) -> tuple[float, float]:
        s = self.drivers[k].state()
        assert s is not None
        return math.degrees(s.yaw_rad), math.degrees(s.pitch_rad)

    def lost(self, zone: int, az_deg: float, el_deg: float, track: int = 7) -> None:
        self.bus.publish(GazeLost(self.t, track, zone, D(az_deg), D(el_deg), None))


def test_AC_HEAD_01_yaw_reaches_target_within_0_6s() -> None:
    r = Rig()
    r.run(0.1)
    r.lost(1, 5.0, 0.0)
    r.run(0.6)
    yaw, pitch = r.pose(1)
    assert yaw == pytest.approx(20.0, abs=2.0) and pitch == pytest.approx(0.0, abs=2.0)
    assert r.heads[1].mode in (HeadMode.ORIENT, HeadMode.HOLD)


def test_AC_HEAD_02_pitch_follows_elevation() -> None:
    r = Rig()
    r.run(0.1)
    r.lost(1, 0.0, 5.0)
    r.run(0.6)
    assert r.pose(1)[1] == pytest.approx(10.0, abs=2.0)


def test_AC_HEAD_05_other_heads_do_not_change_mode() -> None:
    r = Rig()
    r.run(0.1)
    r.lost(0, 5.0, 0.0)
    r.run(1.0)
    assert r.heads[0].mode is not HeadMode.IDLE
    assert r.heads[1].mode is HeadMode.IDLE and r.heads[2].mode is HeadMode.IDLE
    assert {c.head_id for c in r.changes} == {0}


def test_AC_HEAD_06_release_affects_only_the_addressed_head() -> None:
    r = Rig()
    r.run(0.1)
    r.lost(1, 5.0, 0.0)
    r.run(1.0)
    assert r.heads[1].mode is HeadMode.HOLD
    r.bus.publish(TrackUpdated(r.t, 7, 2, 0.0, 0.0, 0.1, AttentionState.AWAY))  # for head 2
    r.run(0.05)
    assert r.heads[1].mode is HeadMode.HOLD  # head 1 ignores head 2's copy
    r.bus.publish(TrackReleased(r.t, 7, 1))
    r.run(0.05)
    assert r.heads[1].mode is HeadMode.RETURN
    assert r.heads[2].mode is HeadMode.IDLE


def test_AC_HEAD_07_follows_moving_target() -> None:
    r = Rig()
    r.run(0.1)
    r.lost(1, 2.0, 0.0)
    r.run(0.8)
    steps = 30
    for i in range(steps + 1):
        az = 2.0 + 4.0 * i / steps
        r.bus.publish(TrackUpdated(r.t, 7, 1, D(az), 0.0, 0.1, AttentionState.AWAY))
        r.run(1.0 / steps)
    r.run(0.5)
    assert r.pose(1)[0] == pytest.approx(24.0, abs=3.0)


def test_AC_HEAD_04_returns_to_neutral_after_hold() -> None:
    r = Rig()
    r.run(0.1)
    r.lost(1, 5.0, 0.0)
    r.run(C.hold_s + 1.5)
    yaw, pitch = r.pose(1)
    assert abs(yaw) < 3.0 and abs(pitch) < 3.0
    assert r.heads[1].mode is HeadMode.IDLE


def test_mode_changes_published_in_order() -> None:
    r = Rig()
    r.run(0.1)
    r.lost(1, 5.0, 0.0)
    r.run(C.hold_s + 1.5)
    assert [c.mode for c in r.changes if c.head_id == 1] == [
        HeadMode.ORIENT,
        HeadMode.HOLD,
        HeadMode.RETURN,
        HeadMode.IDLE,
    ]


def test_orient_does_not_complete_before_the_head_moves() -> None:
    r = Rig()
    r.run(0.1)
    r.lost(1, 5.0, 0.0)
    r.run(0.03)
    assert r.heads[1].mode is HeadMode.ORIENT


def test_AC_HEAD_12_head_reacts_almost_immediately() -> None:
    r = Rig()
    r.run(0.1)
    target_yaw = 40.0
    r.lost(1, target_yaw / C.yaw_scale, 0.0)
    r.run(0.1)
    assert abs(r.pose(1)[0]) >= 5.0
    r.run(0.2)
    assert r.pose(1)[0] == pytest.approx(target_yaw, abs=2.0)
