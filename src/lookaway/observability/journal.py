"""Development-only event journal (JSONL, scalar fields only). Implements SPECS/19."""

from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import TextIO

from lookaway.events import (
    Event,
    EventBus,
    GazeAcquired,
    GazeLost,
    GazeRegained,
    HeadModeChanged,
    TrackLost,
    TrackUpdated,
)

_TYPES = (GazeAcquired, GazeLost, GazeRegained, TrackUpdated, TrackLost, HeadModeChanged)


class Journal:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._f: TextIO = path.open("w")

    def attach(self, bus: EventBus) -> None:
        for et in _TYPES:
            bus.subscribe(et, self._write)

    def _write(self, e: Event) -> None:
        rec: dict[str, object] = {"type": type(e).__name__}
        for k, v in asdict(e).items():  # pyright: ignore[reportArgumentType]
            rec[k] = v.name if isinstance(v, Enum) else v
        self._f.write(json.dumps(rec) + "\n")
        self._f.flush()

    def close(self) -> None:
        self._f.close()
