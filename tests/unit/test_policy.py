from __future__ import annotations

import math
from dataclasses import replace

from lookaway.config import load_config
from lookaway.control.policy import HeadPolicy, PolicyOutput, PolicyParams
from lookaway.events import GazeLost, GazeRegained, TrackLost, TrackUpdated
from lookaway.types import AttentionState, HeadMode

C = load_config().control
P = PolicyParams(
    zone_id=1,
    hold_s=C.hold_s,
    min_hold_s=C.min_hold_s,
    next_target_ttl_s=C.next_target_ttl_s,
    release_on_regain=C.release_on_regain,
    regain_release_s=C.regain_release_s,
    idle_sway_rad=math.radians(C.idle_sway_deg),
    idle_sway_period_s=C.idle_sway_period_s,
    wander_looking_ttl_s=C.wander_looking_ttl_s,
)


def lost(t: float, track: int = 7, zone: int = 1, az: float = 0.1, el: float = 0.0) -> GazeLost:
    return GazeLost(t, track, zone, az, el, None)


def upd(t: float, track: int = 7, zone: int = 1, az: float = 0.1, el: float = 0.0) -> TrackUpdated:
    return TrackUpdated(t, track, zone, az, el, 0.1, AttentionState.AWAY)


class Rig:
    def __init__(self, params: PolicyParams = P) -> None:
        self.p = HeadPolicy(params)
        self.t = 0.0

    def tick(self, dt: float = 0.01, arrived: bool = False) -> PolicyOutput:
        self.t += dt
        return self.p.tick(self.t, arrived)

    def leave_hold(self, limit_s: float = 10.0) -> PolicyOutput:
        """Tick (arrived) until the mode is no longer HOLD; returns that tick's output."""
        out = self.tick(arrived=True)
        for _ in range(round(limit_s / 0.01)):
            if out.mode is not HeadMode.HOLD:
                break
            out = self.tick(arrived=True)
        return out

    def run(self, secs: float, arrived: bool = False) -> PolicyOutput:
        out = self.tick(0.0, arrived)
        for _ in range(round(secs / 0.01)):
            out = self.tick(0.01, arrived)
        return out


def test_idle_has_sway_and_no_target() -> None:
    r = Rig()
    out = r.tick()
    assert out.mode is HeadMode.IDLE and out.target_track is None
    r.run(1.5)
    assert abs(r.tick().sway_yaw_rad) > 0


def test_gaze_lost_in_zone_starts_orient() -> None:
    r = Rig()
    r.p.on_event(lost(0.0, az=0.2, el=0.05))
    out = r.tick()
    assert out.mode is HeadMode.ORIENT and out.target_track == 7
    assert (out.az_rel_rad, out.el_rad) == (0.2, 0.05)


def test_AC_HEAD_05_other_zone_ignored() -> None:
    r = Rig()
    r.p.on_event(lost(0.0, zone=0))
    r.p.on_event(lost(0.0, zone=2))
    assert r.tick().mode is HeadMode.IDLE


def test_orient_to_hold_when_arrived() -> None:
    r = Rig()
    r.p.on_event(lost(0.0))
    assert r.tick(arrived=False).mode is HeadMode.ORIENT
    assert r.tick(arrived=True).mode is HeadMode.HOLD


def _hold(r: Rig) -> None:
    r.p.on_event(lost(0.0))
    r.tick()
    assert r.tick(arrived=True).mode is HeadMode.HOLD


def test_AC_HEAD_03_new_track_during_early_hold_is_queued() -> None:
    r = Rig()
    _hold(r)
    r.run(0.3, arrived=True)
    r.p.on_event(lost(r.t, track=9))
    assert r.tick(arrived=True).target_track == 7


def test_preempt_after_min_hold() -> None:
    r = Rig()
    _hold(r)
    r.run(P.min_hold_s + 0.1, arrived=True)
    r.p.on_event(lost(r.t, track=9, az=-0.1))
    out = r.tick(arrived=False)
    assert out.mode is HeadMode.ORIENT and out.target_track == 9


def test_AC_HEAD_04_hold_expires_to_return_then_idle() -> None:
    r = Rig()
    _hold(r)
    out = r.leave_hold()
    assert out.mode is HeadMode.RETURN and out.target_track is None
    assert r.tick(arrived=False).mode is HeadMode.RETURN
    assert r.tick(arrived=True).mode is HeadMode.IDLE


def test_queued_target_taken_when_hold_ends() -> None:
    r = Rig()
    _hold(r)
    r.run(0.3, arrived=True)
    r.p.on_event(lost(r.t, track=9))
    r.p.on_event(upd(r.t, track=9, az=-0.2))
    r.p.on_event(GazeRegained(r.t, 7, 1))  # target 7 looks back: early release, queue is fresh
    out = r.leave_hold()
    assert out.mode is HeadMode.ORIENT and out.target_track == 9
    assert out.az_rel_rad == -0.2


def test_stale_queued_target_discarded() -> None:
    r = Rig()
    _hold(r)
    r.run(0.1, arrived=True)
    r.p.on_event(lost(r.t, track=9))
    r.run(P.next_target_ttl_s + 0.2, arrived=True)
    out = r.leave_hold()
    assert out.mode is HeadMode.RETURN and out.target_track is None


def test_queued_target_lost_is_discarded() -> None:
    r = Rig()
    _hold(r)
    r.run(0.1, arrived=True)
    r.p.on_event(lost(r.t, track=9))
    r.p.on_event(TrackLost(r.t, 9, 1))
    out = r.leave_hold()
    assert out.mode is HeadMode.RETURN and out.target_track is None


def test_same_target_again_restarts_hold() -> None:
    r = Rig()
    _hold(r)
    r.run(P.hold_s - 0.2, arrived=True)
    r.p.on_event(lost(r.t, track=7))
    assert r.run(0.5, arrived=True).mode is HeadMode.HOLD


def test_AC_HEAD_06_target_moves_to_other_zone_returns() -> None:
    r = Rig()
    _hold(r)
    r.p.on_event(upd(r.t, track=7, zone=2))
    assert r.tick(arrived=False).mode is HeadMode.RETURN


def test_AC_HEAD_07_follows_target_bearing_while_holding() -> None:
    r = Rig()
    _hold(r)
    r.p.on_event(upd(r.t, az=0.105))
    assert r.tick(arrived=True).az_rel_rad == 0.105


def test_regain_releases_after_delay() -> None:
    r = Rig()
    _hold(r)
    r.p.on_event(GazeRegained(r.t, 7, 1))
    assert r.run(P.regain_release_s - 0.1, arrived=True).mode is HeadMode.HOLD
    assert r.leave_hold().mode is HeadMode.RETURN


def test_regain_ignored_when_disabled() -> None:
    r = Rig(replace(P, release_on_regain=False))
    _hold(r)
    r.p.on_event(GazeRegained(r.t, 7, 1))
    assert r.run(1.0, arrived=True).mode is HeadMode.HOLD


def test_target_lost_freezes_bearing_until_hold_expiry() -> None:
    r = Rig()
    _hold(r)
    r.p.on_event(upd(r.t, az=0.3))
    r.p.on_event(TrackLost(r.t, 7, 1))
    out = r.run(0.5, arrived=True)
    assert out.mode is HeadMode.HOLD and out.az_rel_rad == 0.3
    assert r.leave_hold().mode is HeadMode.RETURN


def looking_upd(t: float, track: int = 7) -> TrackUpdated:
    return TrackUpdated(t, track, 1, 0.0, 0.0, 0.9, AttentionState.LOOKING)


def test_AC_HEAD_09_wander_flag_follows_being_looked_at() -> None:
    r = Rig()
    assert r.tick().wander is False
    r.p.on_event(looking_upd(r.t))
    assert r.tick().wander is True
    r.run(P.wander_looking_ttl_s - 0.2)
    assert r.tick().wander is True
    r.run(0.5)
    assert r.tick().wander is False


def test_wander_off_while_orienting_and_holding() -> None:
    r = Rig()
    r.p.on_event(looking_upd(r.t))
    r.p.on_event(lost(r.t))
    assert r.tick().wander is False
    assert r.tick(arrived=True).wander is False


def test_AC_HEAD_10_stares_while_person_stays_away() -> None:
    r = Rig()
    _hold(r)
    for _ in range(round((P.hold_s * 2.5) / 0.1)):  # 5 s of AWAY updates
        r.p.on_event(upd(r.t))
        out = r.run(0.1, arrived=True)
        assert out.mode is HeadMode.HOLD
    assert r.leave_hold().mode is HeadMode.RETURN
