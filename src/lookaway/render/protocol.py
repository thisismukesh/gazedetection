"""WebSocket JSON protocol v1 (angles in radians). Implements SPECS/17 Protocol."""

from __future__ import annotations

import json
from dataclasses import dataclass

from lookaway.types import HeadMode

VERSION = 1


@dataclass(slots=True)
class HeadView:
    id: int
    yaw: float = 0.0
    pitch: float = 0.0
    mode: HeadMode = HeadMode.IDLE
    target_track: int | None = None
    person: int | None = None  # the face this head is assigned to (D6, D14)


def snapshot(heads: list[HeadView], yaw_limit: float, pitch_limit: float) -> str:
    return json.dumps(
        {
            "type": "snapshot",
            "v": VERSION,
            "heads": [
                {"id": h.id, "yaw": h.yaw, "pitch": h.pitch, "mode": h.mode.name.lower()}
                for h in heads
            ],
            "limits": {"yaw": yaw_limit, "pitch": pitch_limit},
        }
    )


def head_state(t: float, heads: list[HeadView]) -> str:
    return json.dumps(
        {
            "type": "head_state",
            "t": t,
            "heads": [
                {
                    "id": h.id,
                    "yaw": h.yaw,
                    "pitch": h.pitch,
                    "mode": h.mode.name.lower(),
                    "target_track": h.target_track,
                    "person": h.person,
                }
                for h in heads
            ],
        }
    )


def debug(
    t: float,
    tracks: list[tuple[int, int, float, str]],
    fps: float,
    p50_ms: float,
    p95_ms: float,
) -> str:
    """Scalars only: never images or landmarks."""
    return json.dumps(
        {
            "type": "debug",
            "t": t,
            "tracks": [{"id": i, "zone": z, "score": s, "state": st} for i, z, s, st in tracks],
            "fps": fps,
            "latency_ms": {"p50": p50_ms, "p95": p95_ms},
        }
    )
