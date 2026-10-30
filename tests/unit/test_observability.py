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
from lookaway.observability.overlay import OverlayInfo, draw_overlay, scale_info
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
    write_jsonl(p, scenarios.single_look_away(seconds=5.0, away=(2.5, 4.0)))
    cfg = load_config()
    src = ReplaySource(p, 1280, 720, cfg.capture.hfov_rad, 30)
    clock, metrics = FakeClock(), Metrics(5.0)
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


def _vec_track(coasting: bool = False) -> DebugTrack:
    return DebugTrack(
        3, 1, 0.9, AttentionState.LOOKING, (400.0, 200.0, 500.0, 330.0),
        centroid_px=(450.0, 260.0), iod_px=50.0,
        head_dir=None if coasting else (0.30, -0.10, -0.95),
        gaze_dir=None if coasting else (-0.40, 0.20, -0.89),
        iris_px=None if coasting else ((430.0, 255.0), (470.0, 255.0)),
    )  # fmt: skip


def _info(track: DebugTrack, assignments: dict[int, int] | None = None) -> OverlayInfo:
    return OverlayInfo(
        tracks=[track], boundaries=[0.3333, 0.6667], head_modes={0: 'idle', 1: 'idle', 2: 'idle'},
        head_targets={}, fps=30.0, p95_ms=20.0, mirror=True, assignments=assignments or {},
    )  # fmt: skip


def test_AC_OBS_01_overlay_draws_vectors_and_iris_only_for_live_tracks() -> None:
    img = np.zeros((720, 1280, 3), np.uint8)
    live = draw_overlay(img, _info(_vec_track()))
    coasting = draw_overlay(img, _info(_vec_track(coasting=True)))
    # cyan head arrow and yellow gaze arrow exist only on the live track
    cyan = np.all(live == (255, 255, 0), axis=2).sum()
    yellow = np.all(live == (0, 255, 255), axis=2).sum()
    assert cyan > 10 and yellow > 10
    assert np.all(coasting == (255, 255, 0), axis=2).sum() == 0
    assert np.all(coasting == (0, 255, 255), axis=2).sum() == 0


def test_overlay_mirrors_arrow_direction() -> None:
    img = np.zeros((720, 1280, 3), np.uint8)
    a = draw_overlay(img, _info(_vec_track()))
    b = draw_overlay(img, replace_mirror(_info(_vec_track()), False))
    assert a.tobytes() != b.tobytes()


def test_overlay_labels_assigned_head() -> None:
    img = np.zeros((720, 1280, 3), np.uint8)
    without = draw_overlay(img, _info(_vec_track()))
    with_head = draw_overlay(img, _info(_vec_track(), {3: 2}))
    assert without.tobytes() != with_head.tobytes()


def replace_mirror(info: OverlayInfo, mirror: bool) -> OverlayInfo:
    from dataclasses import replace

    return replace(info, mirror=mirror)


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


def test_scale_info_scales_every_pixel_quantity() -> None:
    info = _info(_vec_track())
    half = scale_info(info, 0.5)
    t, h = info.tracks[0], half.tracks[0]
    assert h.bbox_px == tuple(v / 2 for v in t.bbox_px)
    assert h.centroid_px == (225.0, 130.0) and h.iod_px == 25.0
    assert h.iris_px == ((215.0, 127.5), (235.0, 127.5))
    assert h.head_dir == t.head_dir and half.boundaries == info.boundaries


def test_overlay_at_camera_view_size_is_legible_and_has_vectors() -> None:
    small = np.zeros((270, 480, 3), np.uint8)
    out = draw_overlay(small, scale_info(_info(_vec_track(), {3: 1}), 480 / 1280))
    assert out.shape == small.shape
    assert np.all(out == (255, 255, 0), axis=2).sum() > 5  # head arrow still visible


def _box_lands_on_face(mirror: bool) -> bool:
    """A bright 'face' patch at a known pixel spot; the drawn box must surround it on screen."""
    img = np.zeros((720, 1280, 3), np.uint8)
    img[300:400, 150:250] = 255  # the face, near the left edge of the raw camera image
    track = DebugTrack(1, 0, 0.9, AttentionState.LOOKING, (150.0, 300.0, 250.0, 400.0))
    info = replace_mirror(_info(track), mirror)
    out = draw_overlay(img, info)
    green = np.all(out == (80, 200, 80), axis=2)  # the LOOKING box colour
    ys, xs = np.nonzero(green)
    white = np.all(out == (255, 255, 255), axis=2)
    wy, wx = np.nonzero(white)
    return bool(
        len(xs) and len(wx) and xs.min() <= wx.min() and xs.max() >= wx.max()
        and ys.min() <= wy.min() and ys.max() >= wy.max()
    )  # fmt: skip


def test_box_surrounds_the_face_unmirrored() -> None:
    assert _box_lands_on_face(mirror=False)


def test_box_surrounds_the_face_when_mirrored() -> None:
    """Regression: the image must be flipped together with the coordinates."""
    assert _box_lands_on_face(mirror=True)
