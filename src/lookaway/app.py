"""Composition root and runtime loops. Implements CLAUDE.md §4 (concurrency) and SPECS/02.

Capture thread -> latest-frame slot -> perception thread -> pipeline -> events (thread-safe hop)
-> asyncio loop: HeadController x3 at ``control.rate_hz`` and the render bridge.
"""

from __future__ import annotations

import asyncio
import contextlib
import random
import threading
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
import structlog

from lookaway.capture.base import parse_source
from lookaway.capture.replay import ReplaySource
from lookaway.capture.slot import LatestFrameSlot
from lookaway.capture.supervisor import ReadSupervisor
from lookaway.capture.video_file import VideoFileSource
from lookaway.capture.webcam import WebcamSource
from lookaway.clock import Clock, MonotonicClock
from lookaway.config import Config, config_sha256
from lookaway.control.assigner import HeadAssigner
from lookaway.control.drivers.simulated import SimulatedHeadDriver
from lookaway.control.factory import build_head_controller
from lookaway.control.head_controller import HeadController
from lookaway.events import (
    Event,
    EventBus,
    GazeAcquired,
    GazeLost,
    GazeRegained,
    HeadModeChanged,
    SourceStatus,
    TrackLost,
    TrackUpdated,
)
from lookaway.observability.journal import Journal
from lookaway.observability.metrics import Metrics
from lookaway.observability.overlay import OverlayInfo, OverlayWindow
from lookaway.perception.replay import ReplayPerception
from lookaway.pipeline import Pipeline, build_pipeline
from lookaway.render import protocol
from lookaway.render.ws_bridge import RenderBridge
from lookaway.types import CameraSource, FacePerception, Frame

_log = structlog.get_logger("lookaway.app")
WEB_DIR = Path(__file__).resolve().parents[2] / "web"
_EVENT_TYPES = (GazeAcquired, GazeLost, GazeRegained, TrackUpdated, TrackLost, SourceStatus)


def build_source(cfg: Config, clock: Clock) -> CameraSource:
    kind, arg = parse_source(cfg.capture.source)
    c = cfg.capture
    if kind == "webcam":
        return WebcamSource(int(arg), c.width, c.height, c.fps, c.hfov_rad, clock)
    if kind == "video":
        return VideoFileSource(arg, clock, realtime=True, hfov_rad=c.hfov_rad)
    return ReplaySource(arg, c.width, c.height, c.hfov_rad, c.fps, clock, loop=True)


def build_perception(cfg: Config) -> FacePerception:
    kind, arg = parse_source(cfg.capture.source)
    if kind == "replay":
        return ReplayPerception(arg)
    from lookaway.perception.mediapipe_face import MediaPipeFacePerception

    return MediaPipeFacePerception(cfg.perception)


class _Workers:
    """Capture and perception threads sharing a latest-frame slot."""

    def __init__(
        self,
        sup: ReadSupervisor,
        slot: LatestFrameSlot,
        process: Callable[[Frame], object],
        clock: Clock,
        metrics: Metrics,
    ) -> None:
        self._sup, self._slot, self._process = sup, slot, process
        self._clock, self._metrics = clock, metrics
        self._stop = threading.Event()
        self._threads = [
            threading.Thread(target=self._capture, name="capture", daemon=True),
            threading.Thread(target=self._perceive, name="perception", daemon=True),
        ]

    def start(self) -> None:
        for t in self._threads:
            t.start()

    def stop(self) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=2.0)

    def _capture(self) -> None:
        while not self._stop.is_set():
            frame = self._sup.poll()
            if frame is None:
                self._stop.wait(0.001)
            else:
                self._metrics.tick("fps_capture", self._clock.now())
                self._slot.put(frame)
                self._metrics.gauge("frames_dropped", self._slot.frames_dropped)

    def _perceive(self) -> None:
        while not self._stop.is_set():
            frame = self._slot.take_latest()
            if frame is None:
                self._stop.wait(0.001)
                continue
            try:
                self._process(frame)
            except Exception:
                _log.exception("perception_failed")


class _Feed:
    """Latest processed frame handed from the perception thread to the main-thread overlay."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame: Frame | None = None

    def set(self, frame: Frame) -> None:
        with self._lock:
            self._frame = frame

    def get(self) -> Frame | None:
        with self._lock:
            return self._frame


async def run_app(
    cfg: Config,
    perception: FacePerception | None = None,
    source: CameraSource | None = None,
    stop: asyncio.Event | None = None,
    on_ready: Callable[[int], None] | None = None,
    seed: int | None = None,
) -> None:
    """Run until ``stop`` is set (or forever). ``on_ready`` receives the bridge port."""
    clock = MonotonicClock()
    loop = asyncio.get_running_loop()
    stop = stop or asyncio.Event()
    metrics = Metrics(cfg.observability.metrics_window_s)
    raw_bus = EventBus()  # asyncio-side attention events, keyed by zone
    bus = EventBus()  # head-addressed events (after assignment) plus head modes
    pipe_bus = EventBus()  # perception-thread bus, hopped into the loop

    def hop(event: Event) -> None:
        loop.call_soon_threadsafe(raw_bus.publish, event)

    for et in _EVENT_TYPES:
        pipe_bus.subscribe(et, hop)
    src = source or build_source(cfg, clock)
    src.open()
    perc = perception or build_perception(cfg)
    pipeline: Pipeline = build_pipeline(cfg, src.info, perc, pipe_bus, clock, metrics)
    bridge = RenderBridge(
        cfg.render.host, cfg.render.port, WEB_DIR, cfg.zones.count, cfg.control.limits.yaw_rad,
        cfg.control.limits.pitch_rad, cfg.render.rate_hz, cfg.render.allow_lan, clock.now,
    )  # fmt: skip
    bridge.attach(bus)
    assigner = HeadAssigner([pipeline.zone_center(k) for k in range(cfg.zones.count)])
    for et in _EVENT_TYPES:
        raw_bus.subscribe(et, lambda e: bus.publish_all(assigner.on_event(e)))
    modes, targets = _track_head_state(raw_bus, bus, metrics, clock)
    journal = _maybe_journal(cfg, bus)
    heads = [
        build_head_controller(
            cfg.control, k, SimulatedHeadDriver(bridge.update_command), bus, random.Random(seed)
        )
        for k in range(cfg.zones.count)
    ]
    feed = _Feed()

    def process(frame: Frame) -> None:
        pipeline.process(frame)
        feed.set(frame)

    workers = _Workers(
        ReadSupervisor(src, clock, pipe_bus), LatestFrameSlot(), process, clock, metrics
    )
    await bridge.start()
    _log.info("started", config_sha256=config_sha256(cfg)[:12], port=bridge.port)
    if on_ready is not None:
        on_ready(bridge.port)
    workers.start()
    extras: list[asyncio.Task[None]] = []
    if cfg.observability.overlay:
        window = OverlayWindow()
        extras.append(
            asyncio.create_task(
                _overlay_loop(
                    cfg, src, pipeline, metrics, clock, feed, modes, targets, window, stop
                )
            )
        )
        extras.append(asyncio.create_task(_debug_loop(cfg, pipeline, metrics, clock, bridge, stop)))
    try:
        await _control_loop(heads, clock, cfg.control.rate_hz, stop)
    finally:
        workers.stop()
        for t in extras:
            t.cancel()
        if cfg.observability.overlay:
            OverlayWindow().close()
        if journal is not None:
            journal.close()
        await bridge.stop()
        src.close()


def _track_head_state(
    raw_bus: EventBus, bus: EventBus, metrics: Metrics, clock: Clock
) -> tuple[dict[int, str], dict[int, int | None]]:
    """Mirror head modes for the overlay and measure event -> first head reaction."""
    modes: dict[int, str] = {}
    targets: dict[int, int | None] = {}
    seen: dict[int, float] = {}
    raw_bus.subscribe(GazeLost, lambda e: seen.__setitem__(e.track_id, clock.now()))

    def on_mode(e: HeadModeChanged) -> None:
        modes[e.head_id] = e.mode.name.lower()
        targets[e.head_id] = e.target_track
        metrics.gauge(f"head_mode.{e.head_id}", float(e.mode.value))
        t0 = seen.pop(e.target_track, None) if e.target_track is not None else None
        if t0 is not None:
            metrics.observe("lat.event_to_command", clock.now(), (clock.now() - t0) * 1000.0)

    bus.subscribe(HeadModeChanged, on_mode)
    return modes, targets


def _maybe_journal(cfg: Config, bus: EventBus) -> Journal | None:
    if cfg.privacy.mode != "development":
        return None
    journal = Journal(Path("logs") / f"journal-{int(time.time())}.jsonl")
    journal.attach(bus)
    return journal


async def _overlay_loop(
    cfg: Config,
    src: CameraSource,
    pipeline: Pipeline,
    metrics: Metrics,
    clock: Clock,
    feed: _Feed,
    modes: dict[int, str],
    targets: dict[int, int | None],
    window: OverlayWindow,
    stop: asyncio.Event,
) -> None:
    """Runs on the main thread: OpenCV GUI calls must stay off worker threads (macOS)."""
    blank = np.zeros((src.info.height, src.info.width, 3), np.uint8)
    while not stop.is_set():
        frame = feed.get()
        image = frame.image if frame is not None and frame.image.size else blank
        snap = metrics.snapshot(clock.now())
        info = OverlayInfo(
            tracks=list(pipeline.debug),
            boundaries=cfg.zones.boundaries,
            head_modes={k: modes.get(k, "idle") for k in range(cfg.zones.count)},
            head_targets=targets,
            fps=snap.get("fps_perception", 0.0),
            p95_ms=metrics.latency("lat.total", clock.now())["p95"],
            mirror=cfg.capture.mirror_display,
        )
        if not window.show(image, info):
            stop.set()
            return
        await asyncio.sleep(1 / 30)


async def _debug_loop(
    cfg: Config,
    pipeline: Pipeline,
    metrics: Metrics,
    clock: Clock,
    bridge: RenderBridge,
    stop: asyncio.Event,
) -> None:
    while not stop.is_set():
        now = clock.now()
        lat = metrics.latency("lat.total", now)
        tracks = [(t.id, t.zone, t.score, t.state.name) for t in pipeline.debug]
        fps = metrics.snapshot(now).get("fps_perception", 0.0)
        bridge.publish_debug(protocol.debug(now, tracks, fps, lat["p50"], lat["p95"]))
        await asyncio.sleep(1 / cfg.render.debug_rate_hz)


async def _control_loop(
    heads: list[HeadController], clock: Clock, rate_hz: int, stop: asyncio.Event | None
) -> None:
    period = 1.0 / rate_hz
    next_t = asyncio.get_running_loop().time()
    while stop is None or not stop.is_set():
        now = clock.now()
        for h in heads:
            h.tick(now)
        next_t += period
        delay = next_t - asyncio.get_running_loop().time()
        if delay < -0.25:  # fell badly behind: resync rather than burst
            next_t = asyncio.get_running_loop().time()
            delay = 0.0
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.sleep(max(delay, 0.0)), timeout=1.0)
