"""Head behaviour policy. Implements SPECS/16 Policy rules 1-11 and Reaction behaviour (D17).

Modes: IDLE (wander or sway), then on a look-away either MASK (``behaviour = "mask"``: face
forward wearing a random emoji) or ORIENT -> HOLD -> RETURN (``behaviour = "stare"``).
AC-HEAD-03..07, AC-HEAD-09..14, AC-MASK-01..04. The caller supplies ``arrived`` (pose within
tolerance of the target pose), so the policy stays independent of targeting and motion.
"""

from __future__ import annotations

import math
import random
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
_FOLLOWING = (HeadMode.ORIENT, HeadMode.HOLD)


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
    behaviour: str = "stare"  # "mask" | "stare" (D17)
    mask_emojis: tuple[str, ...] = ()
    mask_min_s: float = 0.0


@dataclass(frozen=True, slots=True)
class PolicyOutput:
    mode: HeadMode
    target_track: int | None
    az_rel_rad: float
    el_rad: float
    sway_yaw_rad: float
    wander: bool = False
    mask: str | None = None  # the emoji worn in MASK (D17)


@dataclass(slots=True)
class _Target:
    track: int
    az: float
    el: float
    stored_t: float = 0.0
    lost: bool = False


class HeadPolicy:
    def __init__(self, params: PolicyParams, rng: random.Random | None = None) -> None:
        self._p = params
        self._rng = rng or random.Random()
        self._mode = HeadMode.IDLE
        self._target: _Target | None = None
        self._next: _Target | None = None
        self._hold_start = 0.0
        self._release_at: float | None = None
        self._stare_t = 0.0
        self._looked_at_until = -math.inf
        self._mask: str | None = None
        self._mask_start = 0.0

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
            self._react(new)
        elif self._target is not None and e.track_id == self._target.track:
            self._release_at = None
            self._target.az, self._target.el = e.az_rel_rad, e.el_rad
            if self._mode is HeadMode.HOLD:
                self._hold_start = e.t
        elif self._mode is HeadMode.HOLD and e.t - self._hold_start >= self._p.min_hold_s:
            self._orient(new)
        elif self._mode in _FOLLOWING:
            self._next = new

    def _mark_looked_at(self, t: float) -> None:
        self._looked_at_until = t + self._p.wander_looking_ttl_s

    def _on_updated(self, e: TrackUpdated) -> None:
        if e.state in (AttentionState.LOOKING, AttentionState.AWAY_PENDING):
            self._mark_looked_at(e.t)
        if self._next is not None and e.track_id == self._next.track:
            self._next.az, self._next.el = e.az_rel_rad, e.el_rad
        if e.state is AttentionState.AWAY and self._mode in (HeadMode.IDLE, HeadMode.RETURN):
            self._react(_Target(e.track_id, e.az_rel_rad, e.el_rad, e.t))  # D16: away = react
            return
        t = self._target
        if t is None or e.track_id != t.track or self._mode is HeadMode.RETURN:
            return
        if not t.lost:
            t.az, t.el = e.az_rel_rad, e.el_rad
        if e.state is AttentionState.AWAY:
            self._release_at = None  # still away: keep reacting
            if self._mode is HeadMode.HOLD:
                self._stare_t = e.t
        elif e.state is AttentionState.LOOKING:
            self._schedule_release(e.t)  # D16: looking again = let go

    def _on_regained(self, e: GazeRegained) -> None:
        self._mark_looked_at(e.t)
        t = self._target
        if t is not None and e.track_id == t.track:
            self._schedule_release(e.t)

    def _schedule_release(self, t: float) -> None:
        if self._release_at is not None:
            return
        if self._mode is HeadMode.MASK:  # AC-MASK-02: never shorter than mask_min_s
            self._release_at = max(
                t + self._p.regain_release_s, self._mask_start + self._p.mask_min_s
            )
        elif self._p.release_on_regain and self._mode in _FOLLOWING:
            self._release_at = t + self._p.regain_release_s

    def _on_released(self, e: TrackReleased) -> None:
        """Rule 8: the assigner took this head off ``e.track_id`` (D14). Let go, stop wandering."""
        self._looked_at_until = -math.inf  # that person is no longer this head's to watch
        if self._next is not None and e.track_id == self._next.track:
            self._next = None
        if self._target is None or e.track_id != self._target.track:
            return
        if self._mode is HeadMode.MASK:
            self._unmask()  # AC-MASK-04: off at once
        elif self._mode in _FOLLOWING:
            self._next = None
            self._to_return()

    def _on_track_lost(self, e: TrackLost) -> None:
        if self._target is not None and e.track_id == self._target.track:
            self._target.lost = True
            if self._mode is HeadMode.MASK:
                self._release_at = max(e.t, self._mask_start + self._p.mask_min_s)
        if self._next is not None and e.track_id == self._next.track:
            self._next = None

    # -- tick -------------------------------------------------------------------------------

    def tick(self, t: float, arrived: bool) -> PolicyOutput:
        if self._mode is HeadMode.MASK:
            if self._release_at is not None and t >= self._release_at:
                self._unmask()
        elif self._mode is HeadMode.ORIENT and arrived:
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

    # -- transitions ------------------------------------------------------------------------

    def _react(self, target: _Target) -> None:
        if self._p.behaviour == "mask" and self._p.mask_emojis:
            self._put_on_mask(target)
        else:
            self._orient(target)

    def _put_on_mask(self, target: _Target) -> None:
        """AC-MASK-01/03: face forward with a fresh random emoji."""
        self._mode, self._target, self._release_at = HeadMode.MASK, target, None
        self._mask = self._rng.choice(self._p.mask_emojis)
        self._mask_start = target.stored_t

    def _unmask(self) -> None:
        self._mode, self._target, self._mask, self._release_at = HeadMode.IDLE, None, None, None

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
        return PolicyOutput(self._mode, tg.track, tg.az, tg.el, sway, False, self._mask)
