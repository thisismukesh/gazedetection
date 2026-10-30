"""AC-SM-08: invariants I1..I6 of SPECS/14 for arbitrary sample sequences."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from lookaway.attention.state_machine import AttentionStateMachine
from lookaway.events import Event, GazeAcquired, GazeLost, GazeRegained, TrackLost
from lookaway.types import ScoredSample
from tests.fixtures.params import default_sm_params

P = default_sm_params()

step = st.tuples(
    st.floats(0.005, 0.3),  # dt
    st.one_of(st.none(), st.floats(0.0, 1.0)),  # score or missing
    st.booleans(),  # eyes_closed
)
seqs = st.lists(step, min_size=1, max_size=300)


def run(seq: list[tuple[float, float | None, bool]]) -> list[tuple[float, list[Event]]]:
    sm = AttentionStateMachine(1, P)
    t = 0.0
    out: list[tuple[float, list[Event]]] = []
    for dt, score, closed in seq:
        t += dt
        s = None if score is None else ScoredSample(score, closed, 0, 0.0, 0.0)
        out.append((t, sm.step(t, s)))
    return out


@given(seqs)
@settings(max_examples=200)
def test_I1_regained_between_lost(seq: list[tuple[float, float | None, bool]]) -> None:
    pending_regain = False
    for _, evs in run(seq):
        for e in evs:
            if isinstance(e, GazeLost):
                assert not pending_regain
                pending_regain = True
            elif isinstance(e, GazeRegained):
                pending_regain = False


@given(st.lists(st.tuples(st.floats(0.005, 0.1), st.floats(0.36, 0.64)), max_size=200))
@settings(max_examples=100)
def test_I2_band_scores_are_silent_once_settled(band: list[tuple[float, float]]) -> None:
    sm = AttentionStateMachine(1, P)
    t = 0.0
    for _ in range(60):  # settle into LOOKING
        t += 0.05
        sm.step(t, ScoredSample(0.95, False, 0, 0.0, 0.0))
    for dt, score in band:
        t += dt
        evs = sm.step(t, ScoredSample(score, False, 0, 0.0, 0.0))
        assert not any(isinstance(e, GazeLost | GazeAcquired | GazeRegained) for e in evs)


@given(seqs)
def test_I3_closed_eyes_emit_no_gaze_events(seq: list[tuple[float, float | None, bool]]) -> None:
    for (_, score, closed), (_, evs) in zip(seq, run(seq), strict=True):
        if score is not None and closed:
            assert not any(isinstance(e, GazeLost | GazeAcquired | GazeRegained) for e in evs)


@given(seqs)
def test_I4_cooldown_between_lost(seq: list[tuple[float, float | None, bool]]) -> None:
    times = [t for t, evs in run(seq) for e in evs if isinstance(e, GazeLost)]
    for a, b in zip(times, times[1:], strict=False):
        assert b - a >= P.retrigger_cooldown_s - 1e-6


@given(seqs)
def test_I5_deterministic(seq: list[tuple[float, float | None, bool]]) -> None:
    assert run(seq) == run(seq)


@given(seqs)
def test_I6_nothing_after_track_lost(seq: list[tuple[float, float | None, bool]]) -> None:
    done = False
    for _, evs in run(seq):
        if done:
            assert evs == []
        if any(isinstance(e, TrackLost) for e in evs):
            done = True
