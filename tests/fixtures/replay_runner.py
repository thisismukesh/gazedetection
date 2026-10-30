"""Run a landmark JSONL through the pipeline and collect events (no camera, no model)."""

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
from lookaway.perception.replay import ReplayPerception
from lookaway.pipeline import build_pipeline


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


def golden_view(events: list[Event]) -> list[dict[str, object]]:
    """Stable JSON form: everything except per-frame TrackUpdated, floats rounded."""
    out: list[dict[str, object]] = []
    for e in events:
        if isinstance(e, TrackUpdated):
            continue
        rec: dict[str, object] = {"type": type(e).__name__}
        for k, v in vars_of(e).items():
            rec[k] = round(v, 3) if isinstance(v, float) else v
        out.append(rec)
    return out


def vars_of(e: Event) -> dict[str, object]:
    from dataclasses import asdict

    return asdict(e)  # type: ignore[arg-type]
