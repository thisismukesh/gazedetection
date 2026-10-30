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
