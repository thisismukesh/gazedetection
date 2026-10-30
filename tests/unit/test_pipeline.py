from __future__ import annotations

from pathlib import Path

from lookaway.capture.replay import ReplaySource
from lookaway.config import load_config
from lookaway.events import (
    Event,
    EventBus,
    GazeAcquired,
    GazeLost,
    GazeRegained,
    TrackLost,
    TrackUpdated,
)
from lookaway.perception.replay import ReplayPerception, write_jsonl
from lookaway.pipeline import build_pipeline
from tests.fixtures import scenarios


def run_replay(path: Path) -> list[Event]:
    cfg = load_config()
    bus = EventBus()
    events: list[Event] = []
    for et in (GazeAcquired, GazeLost, GazeRegained, TrackUpdated, TrackLost):
        bus.subscribe(et, events.append)
    src = ReplaySource(
        path, cfg.capture.width, cfg.capture.height, cfg.capture.hfov_rad, cfg.capture.fps
    )
    pipe = build_pipeline(cfg, src.info, ReplayPerception(path), bus)
    src.open()
    while (frame := src.read()) is not None:
        pipe.process(frame)
    src.close()
    return events


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
