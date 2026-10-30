"""Assigns each person one head and retargets events. Implements SPECS/16 Assignment, D6.

AC-ASSIGN-01..06.
"""

from __future__ import annotations

from dataclasses import replace

from lookaway.events import (
    Event,
    GazeAcquired,
    GazeLost,
    GazeRegained,
    TrackLost,
    TrackUpdated,
)

_PERSON_EVENTS = (GazeAcquired, GazeLost, GazeRegained, TrackUpdated, TrackLost)


class HeadAssigner:
    """Sticky 1:1 pairing of live tracks to heads; head k's reference is zone k's centre."""

    def __init__(self, zone_centres_rad: list[float]) -> None:
        self._centres = zone_centres_rad
        self._head_of: dict[int, int] = {}

    def head_of(self, track_id: int) -> int | None:
        return self._head_of.get(track_id)

    def assignments(self) -> dict[int, int]:
        return dict(self._head_of)

    def on_event(self, e: Event) -> list[Event]:
        if not isinstance(e, _PERSON_EVENTS):
            return []
        head = self._head_of.get(e.track_id)
        if head is None:
            head = self._assign(e.track_id, e.zone_id)
            if head is None:
                return []
        out: Event
        if isinstance(e, GazeLost | TrackUpdated):
            az = e.az_rel_rad + self._centres[e.zone_id] - self._centres[head]
            out = replace(e, zone_id=head, az_rel_rad=az)
        else:
            out = replace(e, zone_id=head)
        if isinstance(e, TrackLost):
            del self._head_of[e.track_id]
        return [out]

    def _assign(self, track_id: int, zone: int) -> int | None:
        taken = set(self._head_of.values())
        free = [k for k in range(len(self._centres)) if k not in taken]
        if not free:
            return None
        head = min(free, key=lambda k: (abs(k - zone), k))
        self._head_of[track_id] = head
        return head
