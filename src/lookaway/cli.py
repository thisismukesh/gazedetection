"""Command line entry point. Implements CLAUDE.md §7 (replay, run, fetch-models)."""

from __future__ import annotations

import argparse
import asyncio
import sys
import webbrowser
from collections.abc import Sequence
from pathlib import Path

from lookaway.capture.replay import ReplaySource
from lookaway.config import Config, config_sha256, load_config
from lookaway.events import EventBus, TrackUpdated
from lookaway.observability.logging import configure_logging
from lookaway.perception.replay import ReplayPerception
from lookaway.pipeline import build_pipeline


def _replay(path: str, config: str | None) -> int:
    cfg = load_config(config)
    c = cfg.capture
    src = ReplaySource(path, c.width, c.height, c.hfov_rad, c.fps)
    bus = EventBus()
    pipe = build_pipeline(cfg, src.info, ReplayPerception(path), bus)
    print(f"config sha256 {config_sha256(cfg)[:12]}")
    src.open()
    while (frame := src.read()) is not None:
        for e in pipe.process(frame):
            if not isinstance(e, TrackUpdated):
                print(f"{e.t:8.3f}  {type(e).__name__}  {e}")
    src.close()
    return 0


def _fetch_models(config: str | None) -> int:
    from lookaway.models import fetch_model
    from lookaway.perception.mediapipe_face import resolve_model_path

    dest = resolve_model_path(load_config(config).perception.model_path)
    print("downloaded" if fetch_model(dest) else "already present and verified", dest)
    return 0


def _ensure_model(cfg: Config) -> None:
    """First-run convenience: fetch the pinned model if it is missing (explicit, verified)."""
    from lookaway.capture.base import parse_source
    from lookaway.models import fetch_model
    from lookaway.perception.mediapipe_face import resolve_model_path

    if parse_source(cfg.capture.source)[0] == "replay":
        return
    dest = resolve_model_path(cfg.perception.model_path)
    if not dest.exists():
        print(f"model not found, downloading once to {dest} (SHA-256 verified)")
        fetch_model(dest)


def _run(config: str | None, source: str | None, open_browser: bool, overlay: bool) -> int:
    from lookaway.app import run_app

    cfg = load_config(config, source)
    if overlay:
        cfg = cfg.model_copy(
            update={"observability": cfg.observability.model_copy(update={"overlay": True})}
        )
    configure_logging(cfg.observability.log_level, cfg.privacy.mode == "development", Path("logs"))

    def ready(port: int) -> None:
        url = f"http://{cfg.render.host}:{port}/"
        print(f"heads at {url}  (Ctrl-C to quit)")
        if open_browser:
            webbrowser.open(url)

    try:
        _ensure_model(cfg)
        asyncio.run(run_app(cfg, on_ready=ready))
    except KeyboardInterrupt:
        pass
    except (FileNotFoundError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


def _bench(config: str | None, source: str | None, seconds: float) -> int:
    from lookaway.app import build_perception, build_source
    from lookaway.capture.base import parse_source
    from lookaway.capture.video_file import VideoFileSource
    from lookaway.clock import MonotonicClock
    from lookaway.observability.bench import format_report, run_bench

    cfg = load_config(config, source)
    clock = MonotonicClock()
    kind, arg = parse_source(cfg.capture.source)
    _ensure_model(cfg)
    src = (
        VideoFileSource(arg, clock, realtime=False, hfov_rad=cfg.capture.hfov_rad)
        if kind == "video"
        else build_source(cfg, clock)
    )
    if kind == "replay":
        print("note: replay has no perception cost, so these numbers are not representative")
    result = run_bench(cfg, seconds, clock, src, build_perception(cfg))
    print(format_report(result))
    return 1 if result.violations else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lookaway")
    sub = parser.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("replay", help="run the pipeline on a landmark JSONL (no camera, no model)")
    rp.add_argument("path")
    rp.add_argument("--config")
    run = sub.add_parser("run", help="live demo: source -> perception -> heads in the browser")
    run.add_argument("--config")
    run.add_argument("--source", help="webcam:<i> | video:<path> | replay:<path>")
    run.add_argument("--no-browser", action="store_true")
    run.add_argument("--overlay", action="store_true", help="show the OpenCV debug window")
    fm = sub.add_parser("fetch-models", help="download models with a SHA-256 check")
    fm.add_argument("--config")
    bn = sub.add_parser("bench", help="headless latency and FPS report (non-zero exit on miss)")
    bn.add_argument("--config")
    bn.add_argument("--source")
    bn.add_argument("--seconds", type=float, default=10.0)
    args = parser.parse_args(argv)
    if args.cmd == "replay":
        return _replay(args.path, args.config)
    if args.cmd == "fetch-models":
        return _fetch_models(args.config)
    if args.cmd == "bench":
        return _bench(args.config, args.source, args.seconds)
    if args.cmd == "run":
        return _run(args.config, args.source, not args.no_browser, args.overlay)
    print(f"lookaway {args.cmd}: not implemented yet (see SPECS/50-roadmap.md)", file=sys.stderr)
    return 2
