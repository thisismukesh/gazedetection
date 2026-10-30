"""Per-track attention state machine. Implements SPECS/14. AC-SM-01..09, invariants I1..I6.

Pending dwell is accumulated elapsed time (not ``t - start``) so blink frames can pause it.
In UNKNOWN, the look/away timers are strict: they reset when the score leaves their region.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from lookaway.events import (
    Event,
    GazeAcquired,
    GazeLost,
    GazeRegained,
    TrackLost,
    TrackUpdated,
)
from lookaway.types import AttentionState, ScoredSample

_EPS = 1e-9
_WINDOW_S = 60.0


@dataclass(frozen=True, slots=True)
class SMParams:
    t_on: float
    t_off: float
    away_confirm_s: float
    look_confirm_s: float
    retrigger_cooldown_s: float
    missing_as_away_s: float
    track_timeout_s: float
    trigger_on_first_seen_away: bool
    max_triggers_per_min: int


class AttentionStateMachine:
    """One instance per confirmed track. Deterministic function of its input sequence."""

    def __init__(self, track_id: int, params: SMParams) -> None:
        self._id = track_id
        self._p = params
        self.state = AttentionState.UNKNOWN
        self.suppressed_triggers = 0
        self._prev_t: float | None = None
        self._last_seen_t: float | None = None
        self._last: ScoredSample | None = None
        self._pending_s = 0.0
        self._look_s = 0.0
        self._away_s = 0.0
        self._lost_times: deque[float] = deque()

    def step(self, t: float, sample: ScoredSample | None) -> list[Event]:
        if self.state is AttentionState.LOST:
            return []
        dt = 0.0 if self._prev_t is None else max(t - self._prev_t, 0.0)
        self._prev_t = t
        if self._last_seen_t is None:
            self._last_seen_t = t
        if sample is None:
            return self._step_missing(t)
        return self._step_observed(t, dt, sample)

    # -- observed ---------------------------------------------------------------------------

    def _step_observed(self, t: float, dt: float, s: ScoredSample) -> list[Event]:
        self._last_seen_t = t
        self._last = s
        events: list[Event] = []
        if not s.eyes_closed:
            events += self._transition(t, dt, s)
        events.append(
            TrackUpdated(t, self._id, s.zone_id, s.az_rel_rad, s.el_rad, s.score, self.state)
        )
        return events

    def _transition(self, t: float, dt: float, s: ScoredSample) -> list[Event]:
        p = self._p
        st = self.state
        if st is AttentionState.UNKNOWN:
            return self._from_unknown(t, dt, s)
        if st is AttentionState.LOOKING:
            if s.score <= p.t_off:
                self._enter(AttentionState.AWAY_PENDING)
            return []
        if st is AttentionState.AWAY_PENDING:
            if s.score >= p.t_on:
                self._enter(AttentionState.LOOKING)
                return []
            self._pending_s += dt
            if self._pending_s + _EPS >= p.away_confirm_s:
                self._enter(AttentionState.AWAY)
                return self._lost_if_allowed(t, s)
            return []
        if st is AttentionState.AWAY:
            if s.score >= p.t_on:
                self._enter(AttentionState.LOOKING_PENDING)
            return []
        # LOOKING_PENDING
        if s.score <= p.t_off:
            self._enter(AttentionState.AWAY)
            return []
        self._pending_s += dt
        if self._pending_s + _EPS >= p.look_confirm_s:
            self._enter(AttentionState.LOOKING)
            return [GazeRegained(t, self._id, s.zone_id)]
        return []

    def _from_unknown(self, t: float, dt: float, s: ScoredSample) -> list[Event]:
        p = self._p
        self._look_s = self._look_s + dt if s.score >= p.t_on else 0.0
        self._away_s = self._away_s + dt if s.score <= p.t_off else 0.0
        if s.score >= p.t_on and self._look_s + _EPS >= p.look_confirm_s:
            self._enter(AttentionState.LOOKING)
            return [GazeAcquired(t, self._id, s.zone_id)]
        if s.score <= p.t_off and self._away_s + _EPS >= p.away_confirm_s:
            self._enter(AttentionState.AWAY)
            return self._lost_if_allowed(t, s) if p.trigger_on_first_seen_away else []
        return []

    # -- missing ----------------------------------------------------------------------------

    def _step_missing(self, t: float) -> list[Event]:
        assert self._last_seen_t is not None
        p = self._p
        gap = t - self._last_seen_t
        events: list[Event] = []
        if (
            self.state in (AttentionState.LOOKING, AttentionState.AWAY_PENDING)
            and gap + _EPS >= p.missing_as_away_s
            and self._last is not None
        ):
            self._enter(AttentionState.AWAY)
            events += self._lost_if_allowed(t, self._last)
        if gap + _EPS >= p.track_timeout_s:
            self.state = AttentionState.LOST
            zone = self._last.zone_id if self._last is not None else 0
            events.append(TrackLost(t, self._id, zone))
        return events

    # -- helpers ----------------------------------------------------------------------------

    def _enter(self, state: AttentionState) -> None:
        self.state = state
        self._pending_s = 0.0
        self._look_s = 0.0
        self._away_s = 0.0

    def _lost_if_allowed(self, t: float, s: ScoredSample) -> list[Event]:
        p = self._p
        while self._lost_times and t - self._lost_times[0] >= _WINDOW_S:
            self._lost_times.popleft()
        cooled = not self._lost_times or t - self._lost_times[-1] + _EPS >= p.retrigger_cooldown_s
        if not cooled or len(self._lost_times) >= p.max_triggers_per_min:
            self.suppressed_triggers += 1
            return []
        self._lost_times.append(t)
        return [GazeLost(t, self._id, s.zone_id, s.az_rel_rad, s.el_rad, None)]
