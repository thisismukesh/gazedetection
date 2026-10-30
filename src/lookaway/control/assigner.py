"""Assigns heads to people and retargets events. Implements SPECS/16 Assignment, D6, D14.

AC-ASSIGN-01..07. Each person gets one primary head. A lone person also owns every other head.
"""

from __future__ import annotations

from dataclasses import replace

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
_AWAY = (AttentionState.AWAY, AttentionState.AWAY_PENDING)


class HeadAssigner:
    """Sticky pairing of live tracks to heads; head k's reference is zone k's centre."""

    def __init__(self, zone_centres_rad: list[float]) -> None:
        self._centres = zone_centres_rad
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
            if self._assign_primary(tid, e.zone_id) is None:
                return []
            out += self._rebalance(e.t)
        self._remember(e)
        out += [self._retarget(e, h) for h in self.heads_of(tid)]
        if isinstance(e, TrackLost):
            del self._primary[tid]
            self._followers.pop(tid, None)
            self._last.pop(tid, None)
            out += self._rebalance(e.t)
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

    def _remember(self, e: Event) -> None:
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
