"""AC-ASSIGN-06: ownership invariants for arbitrary event sequences."""

from __future__ import annotations

import math

from hypothesis import given
from hypothesis import strategies as st

from lookaway.control.assigner import HeadAssigner
from lookaway.events import Event, GazeLost, TrackLost, TrackReleased, TrackUpdated
from lookaway.types import AttentionState

CENTRES = [math.radians(a) for a in (23.0, 0.0, -23.0)]

ev = st.tuples(
    st.sampled_from(["upd", "away", "lost", "gone"]), st.integers(1, 6), st.integers(0, 2)
)


@given(st.lists(ev, max_size=250))
def test_AC_ASSIGN_06_no_head_has_two_owners(seq: list[tuple[str, int, int]]) -> None:
    a = HeadAssigner(CENTRES)
    owner: dict[int, int] = {}  # head -> track, as observed from the output stream
    for kind, track, zone in seq:
        e: Event
        if kind == "upd":
            e = TrackUpdated(0.0, track, zone, 0.0, 0.0, 0.5, AttentionState.LOOKING)
        elif kind == "away":
            e = TrackUpdated(0.0, track, zone, 0.0, 0.0, 0.1, AttentionState.AWAY)
        elif kind == "lost":
            e = GazeLost(0.0, track, zone, 0.0, 0.0, None)
        else:
            e = TrackLost(0.0, track, zone)
        for o in a.on_event(e):
            head = o.zone_id  # type: ignore[attr-defined]
            tid = o.track_id  # type: ignore[attr-defined]
            assert head in (0, 1, 2)
            if isinstance(o, TrackReleased | TrackLost):
                if owner.get(head) == tid:
                    del owner[head]
            else:
                assert owner.get(head, tid) == tid, "a head was handed to a second owner"
                owner[head] = tid
        headed = {t for t in range(1, 7) if a.head_of(t) is not None}
        if len(headed) >= 2:  # D3 holds whenever two or more people have heads
            counts = [sum(1 for t in owner.values() if t == p) for p in headed]
            assert all(c <= 1 for c in counts)
