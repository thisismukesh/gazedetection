"""Synthetic landmark scenarios written as JSONL (stand-ins for recorded fixtures).

Run ``uv run python -m tests.fixtures.scenarios`` to (re)generate tests/fixtures/landmarks/.
"""

from __future__ import annotations

import math
from pathlib import Path

from lookaway.perception.replay import write_jsonl
from lookaway.types import FaceObservation
from tests.fixtures.synth import make_obs

FPS = 30
Record = tuple[int, float, list[FaceObservation]]
OUT = Path(__file__).parent / "landmarks"


def sway(t: float) -> float:
    """Natural postural sway in pixels: real people are never perfectly still (D12)."""
    return 6.0 * math.sin(2 * math.pi * t / 2.5)


def _person(t: float, x: float, away: bool, dist: float = 1.2) -> FaceObservation:
    kw: dict[str, float] = {"head_yaw_deg": 40.0, "head_pitch_deg": 0.0} if away else {}
    return make_obs(t=t, x_px=x + sway(t), distance_m=dist, **kw)


def single_look_away(
    seconds: float = 8.0, away: tuple[float, float] = (3.0, 5.0), x_px: float = 640.0
) -> list[Record]:
    """One person at the frame centre looks at the camera, away for a while, then back."""
    out: list[Record] = []
    for i in range(round(seconds * FPS)):
        t = i / FPS
        out.append((i, t, [_person(t, x_px, away[0] <= t < away[1])]))
    return out


def two_people(seconds: float = 10.0) -> list[Record]:
    """Left and right persons; only the right one (raw image left) looks away."""
    out: list[Record] = []
    for i in range(round(seconds * FPS)):
        t = i / FPS
        faces = [_person(t, 960.0, False), _person(t, 320.0, 3.0 <= t < 6.0)]
        out.append((i, t, faces))
    return out


def two_in_one_zone(seconds: float = 9.0) -> list[Record]:
    """Two people in the middle zone; only the left-hand one (x=480) looks away, 2.5 s to 5.5 s."""
    out: list[Record] = []
    for i in range(round(seconds * FPS)):
        t = i / FPS
        faces = [_person(t, 480.0, 2.5 <= t < 5.5), _person(t, 700.0, False)]
        out.append((i, t, faces))
    return out


def blink_storm(seconds: float = 8.0) -> list[Record]:
    """Looking at the camera while blinking a lot (0.3 s closures every 0.8 s): no trigger."""
    out: list[Record] = []
    for i in range(round(seconds * FPS)):
        t = i / FPS
        closed = (t % 0.8) < 0.3
        blink = (0.9, 0.9) if closed else (0.05, 0.05)
        out.append((i, t, [make_obs(t=t, x_px=520.0 + sway(t), distance_m=1.2, blink=blink)]))
    return out


def phone_glance_down(seconds: float = 9.0) -> list[Record]:
    """A 0.1 s glance down (shorter than away_confirm_s: ignored), then a 2 s look at a phone."""
    out: list[Record] = []
    for i in range(round(seconds * FPS)):
        t = i / FPS
        down = 3.0 <= t < 3.1 or 5.0 <= t < 7.0
        kw: dict[str, float] = {"head_pitch_deg": 30.0, "eye_pitch_deg": 15.0} if down else {}
        out.append((i, t, [make_obs(t=t, x_px=560.0 + sway(t), distance_m=1.2, **kw)]))
    return out


def boundary_walker(seconds: float = 10.0) -> list[Record]:
    """Walks across the whole frame while looking at the camera: zones change, no trigger."""
    out: list[Record] = []
    for i in range(round(seconds * FPS)):
        t = i / FPS
        x = 120.0 + (1160.0 - 120.0) * (t / seconds)
        out.append((i, t, [make_obs(t=t, x_px=x, distance_m=1.2)]))
    return out


def profile_turn(seconds: float = 8.0) -> list[Record]:
    """Turns to profile: the face drops out of detection for 1.5 s, then reappears."""
    out: list[Record] = []
    for i in range(round(seconds * FPS)):
        t = i / FPS
        if 3.3 <= t < 4.8:
            faces: list[FaceObservation] = []
        elif 3.0 <= t < 3.3:
            yaw = 20.0 + 200.0 * (t - 3.0)  # sweeping to 80 degrees
            faces = [
                make_obs(t=t, x_px=640.0, distance_m=1.2, head_yaw_deg=yaw, head_pitch_deg=0.0)
            ]
        else:
            faces = [make_obs(t=t, x_px=640.0 + sway(t), distance_m=1.2)]
        out.append((i, t, faces))
    return out


def static_poster(seconds: float = 8.0) -> list[Record]:
    """A printed face on a wall: perfectly still, never blinks, and its apparent pose flips."""
    out: list[Record] = []
    for i in range(round(seconds * FPS)):
        t = i / FPS
        kw: dict[str, float] = (
            {"head_yaw_deg": 40.0, "head_pitch_deg": 0.0} if 3.0 <= t < 6.0 else {}
        )
        out.append((i, t, [make_obs(t=t, x_px=380.0, distance_m=1.5, **kw)]))
    return out


SCENARIOS = {
    "single_look_away": lambda: single_look_away(x_px=520.0),
    "two_people": two_people,
    "two_in_one_zone": two_in_one_zone,
    "blink_storm": blink_storm,
    "phone_glance_down": phone_glance_down,
    "boundary_walker": boundary_walker,
    "profile_turn": profile_turn,
    "static_poster": static_poster,
}


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, make in SCENARIOS.items():
        write_jsonl(OUT / f"{name}.jsonl", make())
