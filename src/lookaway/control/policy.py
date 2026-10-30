"""Head behaviour policy: IDLE / ORIENT / HOLD / RETURN. Implements SPECS/16 Policy rules 1-11.

AC-HEAD-03..07, AC-HEAD-09..11. The caller supplies ``arrived`` (pose within tolerance of the
target pose), so the policy stays independent of targeting and motion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from lookaway.events import (
    Event,
    GazeAcquired,
    GazeLost,
    GazeRegained,
    TrackLost,
    TrackReleased,
    TrackUpdated,
)
from lookaway.types import AttentionState, HeadMode

_HEAD_EVENTS = (GazeAcquired, GazeLost, GazeRegained, TrackUpdated, TrackLost, TrackReleased)


@dataclass(frozen=True, slots=True)
class PolicyParams:
    zone_id: int
    hold_s: float
    min_hold_s: float
    next_target_ttl_s: float
    release_on_regain: bool
    regain_release_s: float
    idle_sway_rad: float
    idle_sway_period_s: float
    wander_looking_ttl_s: float


@dataclass(frozen=True, slots=True)
class PolicyOutput:
    mode: HeadMode
    target_track: int | None
    az_rel_rad: float
    el_rad: float
    sway_yaw_rad: float
    wander: bool = False


@dataclass(slots=True)
class _Target:
    track: int
    az: float
    el: float
    stored_t: float = 0.0
    lost: bool = False


class HeadPolicy:
    def __init__(self, params: PolicyParams) -> None:
        self._p = params
        self._mode = HeadMode.IDLE
        self._target: _Target | None = None
        self._next: _Target | None = None
        self._hold_start = 0.0
        self._release_at: float | None = None
        self._stare_t = 0.0
        self._looked_at_until = -math.inf

    # -- events -----------------------------------------------------------------------------

    def on_event(self, e: Event) -> None:
        """Rule 9: only events addressed to this head (``zone_id`` = head id) count."""
        if not isinstance(e, _HEAD_EVENTS) or e.zone_id != self._p.zone_id:
            return
        if isinstance(e, GazeAcquired):
            self._mark_looked_at(e.t)
        elif isinstance(e, GazeLost):
            self._on_lost(e)
        elif isinstance(e, TrackUpdated):
            self._on_updated(e)
        elif isinstance(e, GazeRegained):
            self._on_regained(e)
        elif isinstance(e, TrackLost):
            self._on_track_lost(e)
        else:
            self._on_released(e)

    def _on_lost(self, e: GazeLost) -> None:
        new = _Target(e.track_id, e.az_rel_rad, e.el_rad, e.t)
        if self._mode in (HeadMode.IDLE, HeadMode.RETURN):
            self._orient(new)
        elif self._target is not None and e.track_id == self._target.track:
            self._release_at = None
            self._target.az, self._target.el = e.az_rel_rad, e.el_rad
            if self._mode is HeadMode.HOLD:
                self._hold_start = e.t
        elif self._mode is HeadMode.HOLD and e.t - self._hold_start >= self._p.min_hold_s:
            self._orient(new)
        else:
            self._next = new

    def _mark_looked_at(self, t: float) -> None:
        self._looked_at_until = t + self._p.wander_looking_ttl_s

    def _on_updated(self, e: TrackUpdated) -> None:
        if e.state in (AttentionState.LOOKING, AttentionState.AWAY_PENDING):
            self._mark_looked_at(e.t)
        if self._next is not None and e.track_id == self._next.track:
            self._next.az, self._next.el = e.az_rel_rad, e.el_rad
        t = self._target
        if t is None or e.track_id != t.track or self._mode not in (HeadMode.ORIENT, HeadMode.HOLD):
            return
        if not t.lost:
            t.az, t.el = e.az_rel_rad, e.el_rad
            if self._mode is HeadMode.HOLD and e.state is AttentionState.AWAY:
                self._stare_t = e.t

    def _on_regained(self, e: GazeRegained) -> None:
        self._mark_looked_at(e.t)
        t = self._target
        if (
            self._p.release_on_regain
            and t is not None
            and e.track_id == t.track
            and self._mode in (HeadMode.ORIENT, HeadMode.HOLD)
        ):
            self._release_at = e.t + self._p.regain_release_s

    def _on_released(self, e: TrackReleased) -> None:
        """Rule 8: the assigner took this head off ``e.track_id`` (D14). Let go, stop wandering."""
        self._looked_at_until = -math.inf  # that person is no longer this head's to watch
        if self._next is not None and e.track_id == self._next.track:
            self._next = None
        following = self._mode in (HeadMode.ORIENT, HeadMode.HOLD)
        if following and self._target is not None and e.track_id == self._target.track:
            self._next = None
            self._to_return()

    def _on_track_lost(self, e: TrackLost) -> None:
        if self._target is not None and e.track_id == self._target.track:
            self._target.lost = True
        if self._next is not None and e.track_id == self._next.track:
            self._next = None

    # -- tick -------------------------------------------------------------------------------

    def tick(self, t: float, arrived: bool) -> PolicyOutput:
        if self._mode is HeadMode.ORIENT and arrived:
            self._mode, self._hold_start = HeadMode.HOLD, t
        elif self._mode is HeadMode.HOLD and (
            t - max(self._hold_start, self._stare_t) >= self._p.hold_s
            or (self._release_at is not None and t >= self._release_at)
        ):
            self._to_return(t)
        elif self._mode is HeadMode.RETURN and arrived:
            self._mode = HeadMode.IDLE
        return self._output(t)

    def output(self, t: float) -> PolicyOutput:
        """Current output without advancing state."""
        return self._output(t)

    def _orient(self, target: _Target) -> None:
        self._mode, self._target, self._release_at = HeadMode.ORIENT, target, None

    def _to_return(self, t: float | None = None) -> None:
        self._release_at = None
        queued, self._next = self._next, None
        self._target = None
        now = t if t is not None else 0.0
        if queued and not queued.lost and (t is None or now - queued.stored_t <= self._ttl()):
            self._orient(queued)
        else:
            self._mode = HeadMode.RETURN

    def _ttl(self) -> float:
        return self._p.next_target_ttl_s

    def _output(self, t: float) -> PolicyOutput:
        tg = self._target
        sway = 0.0
        wander = self._mode is HeadMode.IDLE and t < self._looked_at_until
        if self._mode is HeadMode.IDLE and not wander and self._p.idle_sway_rad > 0:
            sway = self._p.idle_sway_rad * math.sin(2 * math.pi * t / self._p.idle_sway_period_s)
        if tg is None:
            return PolicyOutput(self._mode, None, 0.0, 0.0, sway, wander)
        return PolicyOutput(self._mode, tg.track, tg.az, tg.el, sway)
