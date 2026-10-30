"""Headless pipeline benchmark. Implements SPECS/19 Bench. AC-SYS-03, NFR-PERF-01/02."""

from __future__ import annotations

from dataclasses import dataclass, field

from lookaway.clock import Clock
from lookaway.config import Config
from lookaway.events import EventBus
from lookaway.observability.metrics import Metrics
from lookaway.pipeline import build_pipeline
from lookaway.types import CameraSource, FacePerception

MIN_FPS = 24.0  # NFR-PERF-01
MAX_P95_MS = 80.0  # NFR-PERF-02
_STAGES = {
    "capture->perception": "lat.capture_to_perception",
    "perception->score": "lat.perception_to_score",
    "total": "lat.total",
}


@dataclass(slots=True)
class BenchResult:
    frames: int = 0
    seconds: float = 0.0
    fps_processing: float = 0.0
    faces_max: int = 0
    stages: dict[str, dict[str, float]] = field(default_factory=dict[str, dict[str, float]])
    violations: list[str] = field(default_factory=list[str])


def run_bench(
    cfg: Config,
    seconds: float,
    clock: Clock,
    source: CameraSource,
    perception: FacePerception,
) -> BenchResult:
    source.open()  # real sources only know their size once open
    metrics = Metrics(window_s=max(seconds, 1.0) + 1.0)
    pipe = build_pipeline(cfg, source.info, perception, EventBus(), clock, metrics)
    res = BenchResult()
    busy = 0.0
    start = clock.now()
    try:
        while clock.now() - start < seconds:
            frame = source.read()
            if frame is None:
                break
            before = clock.now()
            pipe.process(frame)
            busy += clock.now() - before
            res.frames += 1
            res.faces_max = max(res.faces_max, int(metrics.snapshot(clock.now()).get("faces", 0)))
    finally:
        source.close()
    now = clock.now()
    res.seconds = now - start
    res.fps_processing = res.frames / busy if busy > 0 else float("inf")
    res.stages = {name: metrics.latency(key, now) for name, key in _STAGES.items()}
    if res.frames and res.fps_processing < MIN_FPS:
        res.violations.append(f"NFR-PERF-01: {res.fps_processing:.1f} fps < {MIN_FPS:.0f}")
    if res.frames and res.stages["total"]["p95"] > MAX_P95_MS:
        res.violations.append(
            f"NFR-PERF-02: p95 {res.stages['total']['p95']:.1f} ms > {MAX_P95_MS:.0f} ms"
        )
    return res


def format_report(r: BenchResult) -> str:
    lines = [
        f"frames {r.frames} in {r.seconds:.1f} s, max faces {r.faces_max}, "
        f"processing throughput {r.fps_processing:.1f} fps",
        f"{'stage':<22}{'p50 ms':>10}{'p95 ms':>10}",
    ]
    for name, v in r.stages.items():
        lines.append(f"{name:<22}{v['p50']:>10.1f}{v['p95']:>10.1f}")
    lines.append("event->command        measured live in `lookaway run` (needs the control loop)")
    lines.append("PASS" if not r.violations else "FAIL: " + "; ".join(r.violations))
    return "\n".join(lines)
