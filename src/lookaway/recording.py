"""Consent-gated landmark recording. Implements SPECS/21 P5 (landmarks only, never images)."""

from __future__ import annotations

from pathlib import Path

from lookaway.config import Config
from lookaway.perception.replay import write_jsonl
from lookaway.types import CameraSource, FaceObservation, FacePerception

REPO_ROOT = Path(__file__).resolve().parents[2]


class RecordingRefused(Exception):
    pass


def record_landmarks(
    cfg: Config,
    source: CameraSource,
    perception: FacePerception,
    out_path: Path,
    seconds: float,
    consent_id: str,
) -> int:
    """Record ``seconds`` of observations to ``out_path``; returns the frame count."""
    if cfg.privacy.mode != "development":
        raise RecordingRefused("recording needs privacy.mode = 'development' (config/dev.toml)")
    if not consent_id.strip():
        raise RecordingRefused("a --consent-id is required")
    resolved = out_path.resolve()
    if resolved.is_relative_to(REPO_ROOT):
        raise RecordingRefused("output must be outside the repository")
    records: list[tuple[int, float, list[FaceObservation]]] = []
    first_t: float | None = None
    while (frame := source.read()) is not None:
        first_t = frame.t_capture if first_t is None else first_t
        if frame.t_capture - first_t >= seconds:
            break
        records.append((frame.index, frame.t_capture, perception.process(frame)))
    resolved.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(resolved, records)
    return len(records)
