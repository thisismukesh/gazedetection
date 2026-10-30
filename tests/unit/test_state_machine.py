from __future__ import annotations

from lookaway.attention.state_machine import AttentionStateMachine, SMParams
from lookaway.events import (
    Event,
    GazeAcquired,
    GazeLost,
    GazeRegained,
    TrackLost,
    TrackUpdated,
)
from lookaway.types import AttentionState, ScoredSample
from tests.fixtures.params import default_sm_params

DT = 1 / 30
HI, LO, MID = 0.9, 0.1, 0.5


class Driver:
    """Steps a machine at a fixed frame period and collects events."""

    def __init__(self, params: SMParams | None = None, zone: int = 1) -> None:
        self.sm = AttentionStateMachine(7, params or default_sm_params())
        self.t = 0.0
        self.zone = zone
        self.events: list[Event] = []

    def sample(self, score: float, closed: bool = False, az: float = 0.1) -> ScoredSample:
        return ScoredSample(score, closed, self.zone, az, 0.05)

    def run(self, dur: float, score: float | None, closed: bool = False, az: float = 0.1) -> None:
        for _ in range(round(dur / DT)):
            s = None if score is None else self.sample(score, closed, az)
            self.events += self.sm.step(self.t, s)
            self.t += DT

    def of(self, kind: type) -> list[Event]:
        return [e for e in self.events if isinstance(e, kind)]


def looking() -> Driver:
    d = Driver()
    d.run(1.0, HI)
    assert d.sm.state is AttentionState.LOOKING
    return d


def test_unknown_to_looking_emits_acquired() -> None:
    d = Driver()
    d.run(1.0, HI)
    assert len(d.of(GazeAcquired)) == 1


def test_AC_SM_01_sustained_away_emits_one_gaze_lost() -> None:
    d = looking()
    d.run(0.6, LO)
    lost = d.of(GazeLost)
    assert len(lost) == 1
    assert isinstance(lost[0], GazeLost) and lost[0].zone_id == 1


def test_AC_SM_02_short_dip_no_event() -> None:
    d = looking()
    n = len(d.events)
    d.run(0.15, LO)
    d.run(0.5, HI)
    new = d.events[n:]
    assert all(isinstance(e, TrackUpdated) for e in new)


def test_AC_SM_03_blink_does_not_trigger() -> None:
    d = looking()
    d.run(0.3, LO, closed=True)
    d.run(0.5, HI)
    assert d.of(GazeLost) == []


def test_blink_pauses_pending_timer() -> None:
    d = looking()
    d.run(0.15, LO)  # pending, less than away_confirm
    d.run(1.0, LO, closed=True)  # blink must not advance the timer
    assert d.of(GazeLost) == []
    d.run(0.2, LO)
    assert len(d.of(GazeLost)) == 1


def test_AC_SM_04_regained_then_second_lost_after_cooldown() -> None:
    d = looking()
    d.run(0.6, LO)
    d.run(0.5, HI)
    assert len(d.of(GazeRegained)) == 1
    d.run(1.0, HI)
    d.run(0.6, LO)
    assert len(d.of(GazeLost)) == 2


def test_AC_SM_05_cooldown_suppresses_fast_retrigger() -> None:
    p = default_sm_params(look_confirm_s=0.1, away_confirm_s=0.1)
    d = Driver(p)
    d.run(1.0, HI)
    d.run(0.2, LO)
    d.run(0.2, HI)
    d.run(0.2, LO)
    assert len(d.of(GazeLost)) == 1
    assert d.sm.suppressed_triggers == 1


def test_AC_SM_06_first_seen_away_no_trigger() -> None:
    d = Driver()
    d.run(1.0, LO)
    assert d.of(GazeLost) == []
    assert d.sm.state is AttentionState.AWAY


def test_first_seen_away_triggers_when_enabled() -> None:
    d = Driver(default_sm_params(trigger_on_first_seen_away=True))
    d.run(1.0, LO)
    assert len(d.of(GazeLost)) == 1


def test_AC_SM_07_missing_becomes_lost_then_silence() -> None:
    p = default_sm_params()
    d = looking()
    d.run(0.2, MID, az=0.3)
    d.run(p.missing_as_away_s + 0.1, None)
    lost = d.of(GazeLost)
    assert len(lost) == 1
    assert isinstance(lost[0], GazeLost)
    assert lost[0].zone_id == 1 and lost[0].az_rel_rad == 0.3
    assert d.of(TrackLost) == []
    d.run(p.track_timeout_s, None)
    assert len(d.of(TrackLost)) == 1
    n = len(d.events)
    d.run(1.0, HI)
    assert len(d.events) == n
    assert d.sm.state is AttentionState.LOST


def test_hysteresis_band_does_not_start_transitions() -> None:
    d = looking()
    n = len(d.events)
    d.run(3.0, MID)
    assert all(isinstance(e, TrackUpdated) for e in d.events[n:])


def test_AC_SM_09_rate_limit_caps_at_twelve_per_minute() -> None:
    p = default_sm_params()
    d = Driver(p)
    d.run(1.0, HI)
    for _ in range(13):
        d.run(2.0, LO)
        d.run(2.5, HI)
    assert d.t < 60.0
    assert len(d.of(GazeLost)) == p.max_triggers_per_min
    assert d.sm.suppressed_triggers == 1


def test_track_updated_every_observed_step() -> None:
    d = Driver()
    d.run(0.5, HI)
    assert len(d.of(TrackUpdated)) == round(0.5 / DT)
