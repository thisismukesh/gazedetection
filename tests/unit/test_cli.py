from __future__ import annotations

from pathlib import Path

import pytest

from lookaway.cli import main
from lookaway.perception.replay import write_jsonl
from tests.fixtures import scenarios


def test_replay_prints_gaze_events(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = tmp_path / "s.jsonl"
    write_jsonl(p, scenarios.single_look_away())
    assert main(["replay", str(p)]) == 0
    out = capsys.readouterr().out
    assert "GazeAcquired" in out and "GazeLost" in out and "GazeRegained" in out
    assert "TrackUpdated" not in out


def test_unimplemented_commands_exit_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["bench"]) == 2
    assert "not implemented" in capsys.readouterr().err
