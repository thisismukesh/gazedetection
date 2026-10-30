"""Clip-based integration tests (AC-SYS-01, AC-PER-04). Skipped until consented clips exist.

Put clips and label sidecars in a folder outside the repo and point LOOKAWAY_CLIPS at it:

    <name>.mp4 + <name>.labels.json     [{"zone": 1, "onset_s": 4.2, "type": "look_away"}, ...]
    distance_<0.5|1.0|1.5|2.0>m.mp4     a frontal face at that distance (AC-PER-04)

Run: LOOKAWAY_CLIPS=~/clips uv run pytest -m integration
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from lookaway.capture.video_file import VideoFileSource
from lookaway.clock import FakeClock
from lookaway.config import load_config
from lookaway.events import EventBus, GazeLost
from lookaway.models import FACE_LANDMARKER_SHA256, sha256_file
from lookaway.pipeline import build_pipeline

pytestmark = pytest.mark.integration

CLIPS = Path(os.environ["LOOKAWAY_CLIPS"]).expanduser() if "LOOKAWAY_CLIPS" in os.environ else None
needs_clips = pytest.mark.skipif(
    CLIPS is None or not CLIPS.exists(), reason="set LOOKAWAY_CLIPS to a folder of consented clips"
)


def _perception():  # noqa: ANN202
    from lookaway.perception.mediapipe_face import MediaPipeFacePerception, resolve_model_path

    cfg = load_config()
    model = resolve_model_path(cfg.perception.model_path)
    if not model.exists() or sha256_file(model) != FACE_LANDMARKER_SHA256:
        pytest.skip("run `uv run lookaway fetch-models` first")
    return MediaPipeFacePerception(cfg.perception)


def _clips_with_labels() -> list[Path]:
    return sorted(CLIPS.glob("*.labels.json")) if CLIPS else []


@needs_clips
@pytest.mark.parametrize("labels_path", _clips_with_labels(), ids=lambda p: p.name)
def test_AC_SYS_01_look_aways_trigger_the_right_zone_in_time(labels_path: Path) -> None:
    clip = labels_path.with_name(labels_path.name.replace(".labels.json", ".mp4"))
    labels = [x for x in json.loads(labels_path.read_text()) if x["type"] == "look_away"]
    cfg = load_config()
    src = VideoFileSource(str(clip), FakeClock(), realtime=False, hfov_rad=cfg.capture.hfov_rad)
    src.open()
    bus, lost = EventBus(), []
    bus.subscribe(GazeLost, lost.append)
    pipe = build_pipeline(cfg, src.info, _perception(), bus)
    fps = src.info.fps_nominal
    last_index = 0
    while (frame := src.read()) is not None:
        # file time is the frame index over fps, independent of how fast we process
        pipe.process(type(frame)(frame.source_id, frame.index, frame.index / fps, frame.image))
        last_index = frame.index

    def in_window(e: GazeLost, lab: dict[str, object]) -> bool:
        onset = float(lab["onset_s"])  # type: ignore[arg-type]
        return e.zone_id == lab["zone"] and onset + 0.15 <= e.t <= onset + 0.6

    for lab in labels:
        assert any(in_window(e, lab) for e in lost), f"no GazeLost for {lab} in {clip.name}"
    false_triggers = [e for e in lost if not any(in_window(e, lab) for lab in labels)]
    minutes = max(last_index / fps / 60, 1e-9)
    assert len(false_triggers) / minutes <= 1.0, "more than one false trigger per minute"


@needs_clips
@pytest.mark.parametrize("dist", ["0.5", "1.0", "1.5", "2.0"])
def test_AC_PER_04_detection_rate_at_distance(dist: str) -> None:
    clip = CLIPS / f"distance_{dist}m.mp4" if CLIPS else Path()
    if not clip.exists():
        pytest.skip(f"no {clip.name}")
    cfg = load_config()
    src = VideoFileSource(str(clip), FakeClock(), realtime=False, hfov_rad=cfg.capture.hfov_rad)
    src.open()
    perception = _perception()
    ok = total = 0
    while (frame := src.read()) is not None:
        total += 1
        ok += len(perception.process(frame)) == 1
    assert total and ok / total >= 0.95
