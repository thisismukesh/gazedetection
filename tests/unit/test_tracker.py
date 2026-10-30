from __future__ import annotations

from lookaway.tracking.iou_tracker import IouTracker, TrackerParams
from lookaway.types import FaceObservation, Track
from tests.fixtures.synth import make_obs

DT = 1 / 30
PARAMS = TrackerParams(iou_gate=0.2, high_conf=0.6, confirm_hits=3, max_coast_s=1.0)


def tracker() -> IouTracker:
    return IouTracker(PARAMS, frame_size=(1280, 720))


def obs(t: float, x: float, y: float = 360.0, conf: float = 1.0) -> FaceObservation:
    return make_obs(t=t, x_px=x, y_px=y, confidence=conf, distance_m=1.0)


def test_AC_TRK_01_two_faces_keep_single_ids() -> None:
    tr = tracker()
    ids: dict[str, set[int]] = {"a": set(), "b": set()}
    for i in range(100):
        t = i * DT
        a = obs(t, 200 + 3 * i)  # 3 px/frame, well under 5% of width
        b = obs(t, 1000 - 3 * i)
        out = tr.update([a, b], t)
        for trk in out:
            if trk.confirmed:
                ids["a" if trk.centroid_px[0] < 600 else "b"].add(trk.id)
    assert len(ids["a"]) == 1 and len(ids["b"]) == 1
    assert ids["a"] != ids["b"]


def test_fast_motion_five_percent_of_width_per_frame() -> None:
    tr = tracker()
    seen: set[int] = set()
    for i in range(17):
        t = i * DT
        for trk in tr.update([obs(t, 100 + 64 * i)], t):  # 64 px = 5% of 1280
            seen.add(trk.id)
    assert len(seen) == 1


def test_AC_TRK_02_short_gap_keeps_id() -> None:
    tr = tracker()
    first: Track | None = None
    for i in range(10):
        t = i * DT
        out = tr.update([obs(t, 500)], t)
        first = out[0]
    assert first is not None
    for i in range(10, 25):  # 0.5 s with no detections
        tr.update([], i * DT)
    out = tr.update([obs(25 * DT, 505)], 25 * DT)
    assert [t.id for t in out] == [first.id]
    assert out[0].confirmed


def test_AC_TRK_03_long_gap_new_never_reused_id() -> None:
    tr = tracker()
    old = 0
    for i in range(10):
        old = tr.update([obs(i * DT, 500)], i * DT)[0].id
    t = 10 * DT
    for _ in range(50):  # 1.67 s gap, > max_coast_s
        t += DT
        out = tr.update([], t)
    assert out == []
    new = tr.update([obs(t + DT, 500)], t + DT)[0].id
    assert new != old and new > old


def test_AC_TRK_04_unconfirmed_until_confirm_hits() -> None:
    tr = tracker()
    flags = [tr.update([obs(i * DT, 500)], i * DT)[0].confirmed for i in range(5)]
    assert flags == [False, False, True, True, True]


def test_tentative_track_dropped_on_first_miss() -> None:
    tr = tracker()
    tr.update([obs(0.0, 500)], 0.0)
    assert tr.update([], DT) == []


def test_low_confidence_matches_in_second_pass() -> None:
    tr = tracker()
    for i in range(5):
        tr.update([obs(i * DT, 500)], i * DT)
    out = tr.update([obs(5 * DT, 502, conf=0.3)], 5 * DT)
    assert len(out) == 1 and out[0].misses == 0 and out[0].last_obs is not None


def test_coasting_track_has_no_obs_and_counts_misses() -> None:
    tr = tracker()
    for i in range(5):
        tr.update([obs(i * DT, 500)], i * DT)
    out = tr.update([], 5 * DT)
    assert out[0].last_obs is None and out[0].misses == 1 and out[0].confirmed
