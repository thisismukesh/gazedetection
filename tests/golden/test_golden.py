"""Golden tests: landmark JSONL in, expected event JSON out. Regenerate with --update-golden."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest
from tests.fixtures.replay_runner import golden_view, run_replay
from tests.fixtures.scenarios import SCENARIOS

from lookaway.perception.replay import write_jsonl

LANDMARKS = Path(__file__).resolve().parents[1] / "fixtures" / "landmarks"
EXPECTED = Path(__file__).parent / "expected"


def _close(a: Any, b: Any) -> bool:
    """Structural equality with a float tolerance (libm last digits differ across platforms)."""
    if isinstance(a, float) and isinstance(b, float):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(a, list) and isinstance(b, list):
        lst_a, lst_b = a, b
        return len(lst_a) == len(lst_b) and all(
            _close(x, y) for x, y in zip(lst_a, lst_b, strict=True)
        )
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_close(a[k], b[k]) for k in a)
    return bool(a == b)


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_fixture_matches_generator(name: str, tmp_path: Path) -> None:
    fresh = tmp_path / f"{name}.jsonl"
    write_jsonl(fresh, SCENARIOS[name]())
    new = [json.loads(x) for x in fresh.read_text().splitlines()]
    old = [json.loads(x) for x in (LANDMARKS / f"{name}.jsonl").read_text().splitlines()]
    same = _close(new, old)  # keep the failure message small: never diff huge payloads
    assert same, f"{name}.jsonl is stale: run `uv run python -m tests.fixtures.scenarios`"


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
