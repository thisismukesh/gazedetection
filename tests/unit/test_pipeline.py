from __future__ import annotations

from pathlib import Path

from lookaway.events import (
    GazeAcquired,
    GazeLost,
    GazeRegained,
    TrackLost,
)
from lookaway.perception.replay import write_jsonl
from tests.fixtures import scenarios
from tests.fixtures.replay_runner import run_replay


def _write(tmp_path: Path, name: str, records: list[scenarios.Record]) -> Path:
    p = tmp_path / name
    write_jsonl(p, records)
    return p


def test_single_look_away_yields_one_gaze_lost(tmp_path: Path) -> None:
    ev = run_replay(_write(tmp_path, "a.jsonl", scenarios.single_look_away()))
    lost = [e for e in ev if isinstance(e, GazeLost)]
    assert len(lost) == 1
    assert 3.0 <= lost[0].t <= 3.0 + 0.8
    assert len([e for e in ev if isinstance(e, GazeAcquired)]) == 1
    assert len([e for e in ev if isinstance(e, GazeRegained)]) == 1


def test_two_people_only_the_away_person_triggers_in_their_zone(tmp_path: Path) -> None:
    ev = run_replay(_write(tmp_path, "b.jsonl", scenarios.two_people()))
    lost = [e for e in ev if isinstance(e, GazeLost)]
    assert len(lost) == 1
    # raw image-left (x=320) is the audience's right -> zone 2
    assert lost[0].zone_id == 2


def test_AC_SYS_04_replay_is_deterministic(tmp_path: Path) -> None:
    p = _write(tmp_path, "c.jsonl", scenarios.two_people())
    assert run_replay(p) == run_replay(p)


def test_track_lost_after_person_leaves(tmp_path: Path) -> None:
    recs = scenarios.single_look_away(seconds=3.0, away=(9.0, 9.0))
    n = len(recs)
    for i in range(n, n + 60):  # empty scene for 2 s
        recs.append((i, i / scenarios.FPS, []))
    ev = run_replay(_write(tmp_path, "d.jsonl", recs))
    assert len([e for e in ev if isinstance(e, TrackLost)]) == 1


def _drive(recs: list[scenarios.Record], tmp_path: Path):  # noqa: ANN202
    from lookaway.capture.replay import ReplaySource
    from lookaway.config import load_config
    from lookaway.events import EventBus
    from lookaway.perception.replay import ReplayPerception
    from lookaway.pipeline import build_pipeline

    p = _write(tmp_path, "d.jsonl", recs)
    cfg = load_config()
    src = ReplaySource(p, 1280, 720, cfg.capture.hfov_rad, 30)
    bus, events = EventBus(), []
    for et in (GazeAcquired, GazeLost, GazeRegained, TrackLost):
        bus.subscribe(et, events.append)
    pipe = build_pipeline(cfg, src.info, ReplayPerception(p), bus)
    src.open()
    live_trace: list[bool] = []
    while (f := src.read()) is not None:
        pipe.process(f)
        live_trace += [t.live for t in pipe.debug]
    return events, live_trace


def test_AC_TRK_05_static_face_is_ignored(tmp_path: Path) -> None:
    events, live = _drive(scenarios.static_poster(), tmp_path)
    assert events == []
    assert live and not any(live)  # shown as static in the camera view, never live


def test_AC_TRK_06_blink_makes_a_still_face_live_and_it_stays_live(tmp_path: Path) -> None:
    from tests.fixtures.synth import make_obs

    recs: list[scenarios.Record] = []
    for i in range(30 * 9):
        t = i / 30
        blink = (0.9, 0.9) if 2.0 <= t < 2.2 else (0.02, 0.02)
        kw: dict[str, float] = {"head_yaw_deg": 40.0, "head_pitch_deg": 0.0} if t >= 5.0 else {}
        recs.append((i, t, [make_obs(t=t, x_px=520.0, distance_m=1.2, blink=blink, **kw)]))
    events, live = _drive(recs, tmp_path)
    assert not live[0] and live[-1]
    first_live = live.index(True)
    assert all(live[first_live:])  # sticky
    assert [type(e).__name__ for e in events] == ["GazeAcquired", "GazeLost"]
    assert events[0].t >= 2.0  # nothing before the face proved itself


def test_AC_TRK_06_movement_makes_a_face_live(tmp_path: Path) -> None:
    events, live = _drive(scenarios.single_look_away(seconds=6.0, away=(2.5, 4.5)), tmp_path)
    assert live[-1] and any(isinstance(e, GazeLost) for e in events)
