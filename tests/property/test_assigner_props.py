"""AC-ASSIGN-06: delivery invariants for arbitrary event sequences."""

from __future__ import annotations

import math

from hypothesis import given
from hypothesis import strategies as st

from lookaway.control.assigner import HeadAssigner
from lookaway.events import Event, GazeLost, TrackLost, TrackUpdated
from lookaway.types import AttentionState

CENTRES = [math.radians(a) for a in (23.0, 0.0, -23.0)]

ev = st.tuples(st.sampled_from(["upd", "lost", "gone"]), st.integers(1, 6), st.integers(0, 2))


@given(st.lists(ev, max_size=200))
def test_AC_ASSIGN_06_invariants(seq: list[tuple[str, int, int]]) -> None:
    a = HeadAssigner(CENTRES)
    live: dict[int, int] = {}  # track -> head, as observed from outputs
    for kind, track, zone in seq:
        e: Event
        if kind == "upd":
            e = TrackUpdated(0.0, track, zone, 0.0, 0.0, 0.5, AttentionState.LOOKING)
        elif kind == "lost":
            e = GazeLost(0.0, track, zone, 0.0, 0.0, None)
        else:
            e = TrackLost(0.0, track, zone)
        out = a.on_event(e)
        assert len(out) <= 1
        for o in out:
            head = o.zone_id  # type: ignore[attr-defined]
            assert head in (0, 1, 2)
            if isinstance(o, TrackLost):
                live.pop(track, None)
            else:
                live[track] = head
        assert len(set(live.values())) == len(live)  # no two live tracks share a head
