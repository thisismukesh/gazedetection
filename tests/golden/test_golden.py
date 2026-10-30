"""Golden tests: landmark JSONL in, expected event JSON out. Regenerate with --update-golden."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.fixtures.replay_runner import golden_view, run_replay
from tests.fixtures.scenarios import SCENARIOS

from lookaway.perception.replay import write_jsonl

LANDMARKS = Path(__file__).resolve().parents[1] / "fixtures" / "landmarks"
EXPECTED = Path(__file__).parent / "expected"


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_fixture_matches_generator(name: str, tmp_path: Path) -> None:
    fresh = tmp_path / f"{name}.jsonl"
    write_jsonl(fresh, SCENARIOS[name]())
    assert fresh.read_bytes() == (LANDMARKS / f"{name}.jsonl").read_bytes()


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_golden_events(name: str, update_golden: bool) -> None:
    got = golden_view(run_replay(LANDMARKS / f"{name}.jsonl"))
    path = EXPECTED / f"{name}.events.json"
    if update_golden:
        path.write_text(json.dumps(got, indent=1) + "\n")
    assert path.exists(), "run pytest --update-golden and review the diff"
    assert got == json.loads(path.read_text())


def _types(name: str) -> list[str]:
    return [str(e["type"]) for e in json.loads((EXPECTED / f"{name}.events.json").read_text())]


def test_golden_semantics_hold() -> None:
    """Guards the intent of each scenario, so a bad --update-golden cannot hide a regression."""
    assert _types("blink_storm") == ["GazeAcquired"]
    assert _types("boundary_walker") == ["GazeAcquired"]
    assert _types("single_look_away").count("GazeLost") == 1
    assert _types("phone_glance_down").count("GazeLost") == 1  # long look only, glance ignored
    assert "GazeLost" in _types("profile_turn")  # dropout counts as looking away
    assert _types("two_people").count("GazeLost") == 1
    assert _types("two_in_one_zone").count("GazeLost") == 1
