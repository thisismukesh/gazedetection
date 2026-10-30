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
    TrackReleased,
    TrackUpdated,
)
from lookaway.types import AttentionState

CENTRES = [math.radians(a) for a in (23.0, 0.0, -23.0)]  # zone 0 = audience left


def upd(track: int, zone: int, az: float = 0.0, t: float = 0.0, away: bool = False) -> TrackUpdated:
    state = AttentionState.AWAY if away else AttentionState.LOOKING
    return TrackUpdated(t, track, zone, az, 0.0, 0.9, state)


def lost(track: int, zone: int, az: float = 0.0, t: float = 0.0) -> GazeLost:
    return GazeLost(t, track, zone, az, 0.0, None)


def heads(events: list[Event], kind: type) -> list[int]:
    return sorted(e.zone_id for e in events if isinstance(e, kind))  # type: ignore[attr-defined]


def test_AC_ASSIGN_01_a_lone_person_owns_every_head() -> None:
    a = HeadAssigner(CENTRES)
    out = a.on_event(upd(5, 1))
    assert heads(out, TrackUpdated) == [0, 1, 2] and a.head_of(5) == 1
    out = a.on_event(lost(5, 1, az=0.1))
    assert heads(out, GazeLost) == [0, 1, 2]
    assert next(e for e in out if e.zone_id == 1).az_rel_rad == 0.1  # type: ignore[attr-defined]


def test_AC_ASSIGN_02_a_second_person_takes_one_head_and_extras_are_released() -> None:
    a = HeadAssigner(CENTRES)
    a.on_event(upd(1, 1))
    out = a.on_event(upd(2, 1))  # nearest free head to zone 1 is 0 (tie -> lower id)
    assert a.head_of(1) == 1 and a.head_of(2) == 0
    released = sorted((e.track_id, e.zone_id) for e in out if isinstance(e, TrackReleased))
    assert released == [(1, 0), (1, 2)]  # person 1 gives up heads 0 and 2
    assert heads(out, TrackUpdated) == [0]  # person 2's event goes to head 0 only
    out = a.on_event(upd(1, 1))
    assert heads(out, TrackUpdated) == [1]  # person 1 now has just their own head


def test_AC_ASSIGN_03_three_in_one_zone_then_fourth_waits() -> None:
    a = HeadAssigner(CENTRES)
    for t in (1, 2, 3):
        a.on_event(upd(t, 1))
    assert sorted(a.head_of(t) for t in (1, 2, 3)) == [0, 1, 2]
    assert a.on_event(upd(4, 1)) == [] and a.head_of(4) is None
    out = a.on_event(TrackLost(0.0, 2, 1))
    assert [type(e) for e in out] == [TrackLost]
    assert a.head_of(2) is None
    assert heads(a.on_event(upd(4, 1)), TrackUpdated) == [a.head_of(4)]
    assert a.head_of(4) is not None


def test_AC_ASSIGN_04_pairing_survives_zone_change() -> None:
    a = HeadAssigner(CENTRES)
    a.on_event(upd(1, 0))
    a.on_event(upd(2, 2))
    assert a.head_of(1) == 0 and a.head_of(2) == 2
    out = a.on_event(upd(1, 2))  # person 1 walks into zone 2: still head 0
    assert heads(out, TrackUpdated) == [0]


def test_AC_ASSIGN_05_bearing_re_referenced_to_each_receiving_head() -> None:
    a = HeadAssigner(CENTRES)
    out = a.on_event(lost(1, 1, az=0.05))
    by_head = {e.zone_id: e.az_rel_rad for e in out if isinstance(e, GazeLost)}
    for h in (0, 1, 2):
        assert by_head[h] == pytest.approx(0.05 + CENTRES[1] - CENTRES[h])


def test_AC_ASSIGN_07_heads_rejoin_and_stare_when_the_other_person_leaves() -> None:
    a = HeadAssigner(CENTRES)
    a.on_event(upd(1, 1))
    a.on_event(upd(2, 1))  # both have a head
    a.on_event(lost(1, 1, az=0.1))  # person 1 looks away: their own head stares
    a.on_event(upd(1, 1, az=0.1, away=True))
    out = a.on_event(TrackLost(1.0, 2, 1))  # person 2 leaves
    stares = [e for e in out if isinstance(e, GazeLost) and e.track_id == 1]
    assert heads(stares, GazeLost) == [0, 2]  # the freed heads join in, staring at once
    assert all(e.az_rel_rad == pytest.approx(0.1 + CENTRES[1] - CENTRES[e.zone_id]) for e in stares)


def test_rejoin_does_not_stare_when_the_person_is_looking() -> None:
    a = HeadAssigner(CENTRES)
    a.on_event(upd(1, 1))
    a.on_event(upd(2, 1))
    out = a.on_event(TrackLost(1.0, 2, 1))
    assert not any(isinstance(e, GazeLost) for e in out)


def test_all_event_kinds_reach_all_heads_for_a_lone_person() -> None:
    a = HeadAssigner(CENTRES)
    evs: list[Event] = [
        GazeAcquired(0.0, 1, 2),
        upd(1, 2),
        lost(1, 2),
        GazeRegained(0.0, 1, 2),
        TrackLost(0.0, 1, 2),
    ]
    out = sum((a.on_event(e) for e in evs), [])
    assert len(out) == 3 * len(evs)


def test_head_freed_after_track_lost_is_reusable() -> None:
    a = HeadAssigner(CENTRES)
    a.on_event(upd(1, 1))
    a.on_event(TrackLost(0.0, 1, 1))
    a.on_event(upd(2, 1))
    assert a.head_of(2) == 1
