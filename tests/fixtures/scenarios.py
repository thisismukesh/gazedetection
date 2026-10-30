"""Synthetic landmark scenarios written as JSONL (stand-ins for recorded fixtures).

Run ``uv run python -m tests.fixtures.scenarios`` to (re)generate tests/fixtures/landmarks/.
"""

from __future__ import annotations

from pathlib import Path

from lookaway.perception.replay import write_jsonl
from lookaway.types import FaceObservation
from tests.fixtures.synth import make_obs

FPS = 30
Record = tuple[int, float, list[FaceObservation]]
OUT = Path(__file__).parent / "landmarks"


def _person(t: float, x: float, away: bool, dist: float = 1.2) -> FaceObservation:
    kw: dict[str, float] = {"head_yaw_deg": 40.0, "head_pitch_deg": 0.0} if away else {}
    return make_obs(t=t, x_px=x, distance_m=dist, **kw)


def single_look_away(seconds: float = 8.0, away: tuple[float, float] = (3.0, 5.0)) -> list[Record]:
    """One person at the frame centre looks at the camera, away for a while, then back."""
    out: list[Record] = []
    for i in range(round(seconds * FPS)):
        t = i / FPS
        out.append((i, t, [_person(t, 640.0, away[0] <= t < away[1])]))
    return out


def two_people(seconds: float = 10.0) -> list[Record]:
    """Left and right persons; only the right one (raw image left) looks away."""
    out: list[Record] = []
    for i in range(round(seconds * FPS)):
        t = i / FPS
        faces = [_person(t, 960.0, False), _person(t, 320.0, 3.0 <= t < 6.0)]
        out.append((i, t, faces))
    return out


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "single_look_away.jsonl", single_look_away())
    write_jsonl(OUT / "two_people.jsonl", two_people())
