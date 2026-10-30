"""Assigns heads to people and retargets events. Implements SPECS/16 Assignment, D6, D14, D17.

AC-ASSIGN-01..11. Each person gets one primary head; a lone person also owns every other head.
People beyond the number of heads wait; a head whose person has been away for
``rotate_after_s`` moves on to the waiting person whose gaze was captured most recently.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from lookaway.events import (
    Event,
    GazeAcquired,
    GazeLost,
    GazeRegained,
    TrackLost,
    TrackReleased,
    TrackUpdated,
)
from lookaway.types import AttentionState

_PERSON_EVENTS = (GazeAcquired, GazeLost, GazeRegained, TrackUpdated, TrackLost)
PersonEvent = GazeAcquired | GazeLost | GazeRegained | TrackUpdated | TrackLost
_AWAY = (AttentionState.AWAY, AttentionState.AWAY_PENDING)


@dataclass(slots=True)
class _Waiting:
    """A person with no head: their latest state and when their gaze was last captured."""

    state: AttentionState = AttentionState.UNKNOWN
    capture_t: float = -math.inf


class HeadAssigner:
    """Pairing of live tracks to heads; head k's reference is zone k's centre."""

    def __init__(self, zone_centres_rad: list[float], rotate_after_s: float | None = None) -> None:
        self._centres = zone_centres_rad
        self._rotate_after_s = rotate_after_s
        self._waiting: dict[int, _Waiting] = {}
        self._away_since: dict[int, float] = {}
        self._primary: dict[int, int] = {}
        self._followers: dict[int, set[int]] = {}
        # last known (zone, az_rel, el, away?) per track, to brief a head that joins late
        self._last: dict[int, tuple[int, float, float, bool]] = {}

    def head_of(self, track_id: int) -> int | None:
        return self._primary.get(track_id)

    def heads_of(self, track_id: int) -> list[int]:
        if track_id not in self._primary:
            return []
        return sorted({self._primary[track_id], *self._followers.get(track_id, set())})

    def owners(self) -> dict[int, int]:
        """Head -> owning track (primary or follower); free heads are omitted. AC-ASSIGN-08."""
        return {h: t for t in self._primary for h in self.heads_of(t)}

    def assignments(self) -> dict[int, int]:
        return dict(self._primary)

    def shared_tracks(self) -> set[int]:
        """Tracks that currently own more than one head (a lone person)."""
        return {t for t in self._primary if len(self.heads_of(t)) > 1}

    def on_event(self, e: Event) -> list[Event]:
        if not isinstance(e, _PERSON_EVENTS):
            return []
        out: list[Event] = []
        tid = e.track_id
        if tid not in self._primary:
            if tid in self._waiting or self._assign_primary(tid, e.zone_id) is None:
                self._note_waiting(e)
                return self._rotate(e.t)
            out += self._rebalance(e.t)
        self._remember(e)
        out += [self._retarget(e, h) for h in self.heads_of(tid)]
        if isinstance(e, TrackLost):
            freed = self._primary.pop(tid)
            self._followers.pop(tid, None)
            self._last.pop(tid, None)
            self._away_since.pop(tid, None)
            out += self._give_to_waiting(e.t, freed)  # AC-ASSIGN-11
            out += self._rebalance(e.t)
        return out + self._rotate(e.t)

    # -- waiting and rotation (D17) ---------------------------------------------------------

    def _note_waiting(self, e: PersonEvent) -> None:
        tid = e.track_id
        if isinstance(e, TrackLost):
            self._waiting.pop(tid, None)
            return
        w = self._waiting.setdefault(tid, _Waiting())
        if isinstance(e, GazeAcquired | GazeRegained):
            w.capture_t, w.state = e.t, AttentionState.LOOKING
        elif isinstance(e, TrackUpdated):
            w.state = e.state
        else:  # GazeLost
            w.state = AttentionState.AWAY

    def _best_waiting(self) -> int | None:
        """The LOOKING waiting person whose gaze was captured most recently. AC-ASSIGN-10."""
        lookers = [
            (w.capture_t, t) for t, w in self._waiting.items() if w.state is AttentionState.LOOKING
        ]
        return max(lookers)[1] if lookers else None

    def _give_to_waiting(self, t: float, head: int) -> list[Event]:
        tid = self._best_waiting()
        if tid is None:
            return []
        del self._waiting[tid]
        self._primary[tid] = head
        return [GazeAcquired(t, tid, head)]  # brief the head: its new person is looking

    def _rotate(self, t: float) -> list[Event]:
        """AC-ASSIGN-09: a head whose person stayed away long enough moves to a waiting looker."""
        if self._rotate_after_s is None or not self._waiting:
            return []
        out: list[Event] = []
        for tid, since in sorted(self._away_since.items()):
            if t - since < self._rotate_after_s or self._best_waiting() is None:
                continue
            head = self._primary.pop(tid)
            out += [
                TrackReleased(t, tid, h) for h in sorted({head, *self._followers.pop(tid, set())})
            ]
            del self._away_since[tid]
            self._waiting[tid] = _Waiting(AttentionState.AWAY)
            out += self._give_to_waiting(t, head)
        return out

    # -- internals --------------------------------------------------------------------------

    def _assign_primary(self, track_id: int, zone: int) -> int | None:
        taken = set(self._primary.values())
        free = [k for k in range(len(self._centres)) if k not in taken]
        if not free:
            return None
        head = min(free, key=lambda k: (abs(k - zone), k))
        self._primary[track_id] = head
        return head

    def _rebalance(self, t: float) -> list[Event]:
        """One headed person owns every head; with two or more, each keeps just their own."""
        out: list[Event] = []
        n = len(self._centres)
        if len(self._primary) == 1:
            ((tid, primary),) = self._primary.items()
            wanted = set(range(n)) - {primary}
            current = self._followers.setdefault(tid, set())
            for head in sorted(wanted - current):
                out += self._join(t, tid, head)
            current |= wanted
            return out
        for tid, followers in self._followers.items():
            out += [TrackReleased(t, tid, h) for h in sorted(followers)]
            followers.clear()
        return out

    def _join(self, t: float, tid: int, head: int) -> list[Event]:
        """Brief a head that starts following ``tid``: stare at once if they are looking away."""
        last = self._last.get(tid)
        if last is None or not last[3]:
            return []
        zone, az, el, _ = last
        return [GazeLost(t, tid, head, az + self._centres[zone] - self._centres[head], el, None)]

    def _remember(self, e: PersonEvent) -> None:
        tid = e.track_id
        away_now = (isinstance(e, TrackUpdated) and e.state is AttentionState.AWAY) or isinstance(
            e, GazeLost
        )
        if away_now:
            self._away_since.setdefault(tid, e.t)
        elif isinstance(e, TrackUpdated | GazeRegained | GazeAcquired):
            self._away_since.pop(tid, None)
        if isinstance(e, TrackUpdated):
            self._last[e.track_id] = (e.zone_id, e.az_rel_rad, e.el_rad, e.state in _AWAY)
        elif isinstance(e, GazeLost):
            self._last[e.track_id] = (e.zone_id, e.az_rel_rad, e.el_rad, True)
        elif isinstance(e, GazeRegained | GazeAcquired):
            zone, az, el, _ = self._last.get(e.track_id, (e.zone_id, 0.0, 0.0, False))
            self._last[e.track_id] = (zone, az, el, False)

    def _retarget(self, e: Event, head: int) -> Event:
        if isinstance(e, GazeLost | TrackUpdated):
            az = e.az_rel_rad + self._centres[e.zone_id] - self._centres[head]
            return replace(e, zone_id=head, az_rel_rad=az)
        return replace(e, zone_id=head)  # type: ignore[type-var]
