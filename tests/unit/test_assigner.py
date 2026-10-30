from __future__ import annotations

import math

import pytest

from lookaway.control.assigner import HeadAssigner
from lookaway.events import (
    Event,
    GazeAcquired,
    GazeLost,
    GazeRegained,
    TrackLost,
    TrackUpdated,
)
from lookaway.types import AttentionState

CENTRES = [math.radians(a) for a in (23.0, 0.0, -23.0)]  # zone 0 = audience left


def upd(track: int, zone: int, az: float = 0.0) -> TrackUpdated:
    return TrackUpdated(0.0, track, zone, az, 0.0, 0.9, AttentionState.LOOKING)


def lost(track: int, zone: int, az: float = 0.0) -> GazeLost:
    return GazeLost(0.0, track, zone, az, 0.0, None)


def zones_of(events: list[Event]) -> list[int]:
    return [e.zone_id for e in events if hasattr(e, "zone_id")]  # type: ignore[attr-defined]


def test_AC_ASSIGN_01_single_person_gets_their_zone_head() -> None:
    a = HeadAssigner(CENTRES)
    out = a.on_event(upd(5, 1))
    assert zones_of(out) == [1] and a.head_of(5) == 1
    out = a.on_event(lost(5, 1, az=0.1))
    assert isinstance(out[0], GazeLost) and out[0].zone_id == 1 and out[0].az_rel_rad == 0.1


def test_AC_ASSIGN_02_second_person_in_same_zone_gets_nearest_free_head() -> None:
    a = HeadAssigner(CENTRES)
    a.on_event(upd(1, 1))
    a.on_event(upd(2, 1))
    assert a.head_of(1) == 1 and a.head_of(2) == 0  # tie between 0 and 2 -> lower id


def test_AC_ASSIGN_03_three_in_one_zone_then_fourth_waits() -> None:
    a = HeadAssigner(CENTRES)
    for t in (1, 2, 3):
        a.on_event(upd(t, 1))
    assert sorted(a.head_of(t) for t in (1, 2, 3)) == [0, 1, 2]
    assert a.on_event(upd(4, 1)) == [] and a.head_of(4) is None
    out = a.on_event(TrackLost(0.0, 2, 1))
    assert isinstance(out[0], TrackLost) and a.head_of(2) is None
    assert zones_of(a.on_event(upd(4, 1))) == [a.head_of(4)] and a.head_of(4) is not None


def test_AC_ASSIGN_04_pairing_survives_zone_change() -> None:
    a = HeadAssigner(CENTRES)
    a.on_event(upd(1, 0))
    out = a.on_event(upd(1, 2))
    assert zones_of(out) == [0]


def test_AC_ASSIGN_05_bearing_re_referenced_to_head_centre() -> None:
    a = HeadAssigner(CENTRES)
    a.on_event(upd(1, 1))
    a.on_event(upd(2, 1))  # gets head 0
    out = a.on_event(lost(2, 1, az=0.05))
    assert isinstance(out[0], GazeLost) and out[0].zone_id == 0
    # person is 0.05 rad right of zone 1's centre; head 0's centre is 23 deg further left
    assert out[0].az_rel_rad == pytest.approx(0.05 + CENTRES[1] - CENTRES[0])


def test_all_event_kinds_are_retargeted() -> None:
    a = HeadAssigner(CENTRES)
    evs = [
        GazeAcquired(0.0, 1, 2),
        upd(1, 2),
        lost(1, 2),
        GazeRegained(0.0, 1, 2),
        TrackLost(0.0, 1, 2),
    ]
    assert [type(e) for e in sum((a.on_event(e) for e in evs), [])] == [type(e) for e in evs]


def test_head_freed_after_track_lost_is_reusable() -> None:
    a = HeadAssigner(CENTRES)
    a.on_event(upd(1, 1))
    a.on_event(TrackLost(0.0, 1, 1))
    a.on_event(upd(2, 1))
    assert a.head_of(2) == 1
