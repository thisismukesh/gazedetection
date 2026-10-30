"""Composition root and runtime loops. Implements CLAUDE.md §4 (concurrency) and SPECS/02.

Capture thread -> latest-frame slot -> perception thread -> pipeline -> events (thread-safe hop)
-> asyncio loop: HeadController x3 at ``control.rate_hz`` and the render bridge.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Callable
from pathlib import Path

import structlog

from lookaway.capture.base import parse_source
from lookaway.capture.replay import ReplaySource
from lookaway.capture.slot import LatestFrameSlot
from lookaway.capture.supervisor import ReadSupervisor
from lookaway.capture.video_file import VideoFileSource
from lookaway.capture.webcam import WebcamSource
from lookaway.clock import Clock, MonotonicClock
from lookaway.config import Config, config_sha256
from lookaway.control.drivers.simulated import SimulatedHeadDriver
from lookaway.control.factory import build_head_controller
from lookaway.control.head_controller import HeadController
from lookaway.events import (
    Event,
    EventBus,
    GazeAcquired,
    GazeLost,
    GazeRegained,
    SourceStatus,
    TrackLost,
    TrackUpdated,
)
from lookaway.perception.replay import ReplayPerception
from lookaway.pipeline import Pipeline, build_pipeline
from lookaway.render.ws_bridge import RenderBridge
from lookaway.types import CameraSource, FacePerception

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
    return ReplaySource(arg, c.width, c.height, c.hfov_rad, c.fps, clock)


def build_perception(cfg: Config) -> FacePerception:
    kind, arg = parse_source(cfg.capture.source)
    if kind == "replay":
        return ReplayPerception(arg)
    from lookaway.perception.mediapipe_face import MediaPipeFacePerception

    return MediaPipeFacePerception(cfg.perception)


class _Workers:
    """Capture and perception threads sharing a latest-frame slot."""

    def __init__(
        self, sup: ReadSupervisor, slot: LatestFrameSlot, process: Callable[..., object]
    ) -> None:
        self._sup, self._slot, self._process = sup, slot, process
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
                self._slot.put(frame)

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


async def run_app(
    cfg: Config,
    perception: FacePerception | None = None,
    source: CameraSource | None = None,
    stop: asyncio.Event | None = None,
    on_ready: Callable[[int], None] | None = None,
) -> None:
    """Run until ``stop`` is set (or forever). ``on_ready`` receives the bridge port."""
    clock = MonotonicClock()
    loop = asyncio.get_running_loop()
    bus = EventBus()  # asyncio-side bus: heads and bridge
    pipe_bus = EventBus()  # perception-thread bus, hopped into the loop

    def hop(event: Event) -> None:
        loop.call_soon_threadsafe(bus.publish, event)

    for et in _EVENT_TYPES:
        pipe_bus.subscribe(et, hop)
    src = source or build_source(cfg, clock)
    src.open()
    pipeline: Pipeline = build_pipeline(
        cfg, src.info, perception or build_perception(cfg), pipe_bus
    )
    bridge = RenderBridge(
        cfg.render.host, cfg.render.port, WEB_DIR, cfg.zones.count, cfg.control.limits.yaw_rad,
        cfg.control.limits.pitch_rad, cfg.render.rate_hz, cfg.render.allow_lan, clock.now,
    )  # fmt: skip
    bridge.attach(bus)
    heads = [
        build_head_controller(cfg.control, k, SimulatedHeadDriver(bridge.update_command), bus)
        for k in range(cfg.zones.count)
    ]
    workers = _Workers(ReadSupervisor(src, clock, pipe_bus), LatestFrameSlot(), pipeline.process)
    await bridge.start()
    _log.info("started", config_sha256=config_sha256(cfg)[:12], port=bridge.port)
    if on_ready is not None:
        on_ready(bridge.port)
    workers.start()
    try:
        await _control_loop(heads, clock, cfg.control.rate_hz, stop)
    finally:
        workers.stop()
        await bridge.stop()
        src.close()


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
