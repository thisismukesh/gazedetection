from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import structlog

from lookaway.clock import FakeClock
from lookaway.config import load_config
from lookaway.events import EventBus, GazeLost, TrackUpdated
from lookaway.observability.journal import Journal
from lookaway.observability.logging import configure_logging, scrub_arrays
from lookaway.observability.metrics import Metrics
from lookaway.observability.overlay import OverlayInfo, draw_overlay
from lookaway.pipeline import DebugTrack, build_pipeline
from lookaway.recording import RecordingRefused, record_landmarks
from lookaway.types import AttentionState, Frame
from tests.fixtures import scenarios
from tests.fixtures.synth import intrinsics


def test_scrub_replaces_long_numeric_lists() -> None:
    out = scrub_arrays(None, "info", {"event": "x", "pts": list(range(9)), "ok": [1, 2, 3]})
    assert out["pts"] == "<array redacted>" and out["ok"] == [1, 2, 3]


def test_scrub_catches_nested_and_numpy() -> None:
    out = scrub_arrays(None, "info", {"event": "x", "a": np.zeros((5, 5)), "b": {"c": [0.0] * 20}})
    assert out["a"] == "<array redacted>" and out["b"]["c"] == "<array redacted>"


def test_AC_SYS_02_log_output_has_no_long_numeric_lists(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO", development=False, log_dir=None)
    log = structlog.get_logger("t")
    log.info("hello", values=list(range(50)), scalar=1.5)
    line = capsys.readouterr().out.strip().splitlines()[-1]
    rec = json.loads(line)
    assert rec["event"] == "hello" and rec["values"] == "<array redacted>" and rec["scalar"] == 1.5


def test_pipeline_records_metrics_and_debug(tmp_path: Path) -> None:
    from lookaway.capture.replay import ReplaySource
    from lookaway.perception.replay import ReplayPerception, write_jsonl

    p = tmp_path / "s.jsonl"
    write_jsonl(p, scenarios.single_look_away(seconds=3.0, away=(1.0, 2.0)))
    cfg = load_config()
    src = ReplaySource(p, 1280, 720, cfg.capture.hfov_rad, 30)
    clock, metrics = FakeClock(), Metrics(3.0)
    pipe = build_pipeline(cfg, src.info, ReplayPerception(p), EventBus(), clock, metrics)
    src.open()
    while (f := src.read()) is not None:
        clock.advance(max(f.t_capture - clock.now(), 0.0) + 0.004)
        pipe.process(f)
    snap = metrics.snapshot(clock.now())
    assert snap["fps_perception"] > 20 and snap["confirmed_tracks"] == 1 and snap["faces"] == 1
    assert snap["events_total.GazeLost"] == 1
    assert metrics.latency("lat.total", clock.now())["p95"] >= 4.0
    assert pipe.debug and isinstance(pipe.debug[0], DebugTrack)


def test_overlay_draws_without_mutating_input_and_marks_tracks() -> None:
    img = np.zeros((720, 1280, 3), np.uint8)
    info = OverlayInfo(
        tracks=[DebugTrack(3, 1, 0.9, AttentionState.LOOKING, (400.0, 200.0, 500.0, 330.0))],
        boundaries=[0.3333, 0.6667],
        head_modes={0: "idle", 1: "orient", 2: "idle"},
        head_targets={1: 3},
        fps=29.0,
        p95_ms=41.0,
        mirror=True,
    )
    out = draw_overlay(img, info)
    assert img.sum() == 0 and out.shape == img.shape and out.sum() > 0
    assert draw_overlay(img, info).tobytes() == out.tobytes()  # deterministic


def test_journal_writes_scalars_only(tmp_path: Path) -> None:
    bus = EventBus()
    path = tmp_path / "j.jsonl"
    j = Journal(path)
    j.attach(bus)
    bus.publish(TrackUpdated(1.0, 2, 1, 0.1, 0.0, 0.8, AttentionState.LOOKING))
    bus.publish(GazeLost(2.0, 2, 1, 0.1, 0.0, None))
    j.close()
    recs = [json.loads(x) for x in path.read_text().splitlines()]
    assert [r["type"] for r in recs] == ["TrackUpdated", "GazeLost"]
    assert recs[0]["state"] == "LOOKING"
    assert all(not isinstance(v, list | dict) for r in recs for v in r.values())


def test_recording_requires_development_mode_and_consent(tmp_path: Path) -> None:
    cfg_install = load_config()
    with pytest.raises(RecordingRefused, match="development"):
        record_landmarks(cfg_install, None, None, tmp_path / "o.jsonl", 1.0, "C-1")  # type: ignore[arg-type]
    cfg_dev = cfg_install.model_copy(
        update={"privacy": cfg_install.privacy.model_copy(update={"mode": "development"})}
    )
    with pytest.raises(RecordingRefused, match="consent"):
        record_landmarks(cfg_dev, None, None, tmp_path / "o.jsonl", 1.0, "")  # type: ignore[arg-type]
    inside = Path(__file__).resolve().parents[2] / "tests" / "x.jsonl"
    with pytest.raises(RecordingRefused, match="outside"):
        record_landmarks(cfg_dev, None, None, inside, 1.0, "C-1")  # type: ignore[arg-type]


def test_recording_writes_landmarks_only(tmp_path: Path) -> None:
    from lookaway.capture.replay import ReplaySource
    from lookaway.perception.replay import ReplayPerception, read_jsonl, write_jsonl

    src_path = tmp_path / "in.jsonl"
    write_jsonl(src_path, scenarios.single_look_away(seconds=1.0))
    cfg = load_config()
    cfg = cfg.model_copy(update={"privacy": cfg.privacy.model_copy(update={"mode": "development"})})
    src = ReplaySource(src_path, 1280, 720, cfg.capture.hfov_rad, 30)
    src.open()
    out = tmp_path / "rec" / "out.jsonl"
    n = record_landmarks(cfg, src, ReplayPerception(src_path), out, 5.0, "C-1")
    assert n == 30 and len(read_jsonl(out)) == 30
    assert "image" not in out.read_text()
    assert isinstance(Frame, type) and intrinsics().fx > 0
