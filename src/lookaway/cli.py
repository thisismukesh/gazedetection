"""Command line entry point. Implements CLAUDE.md §7 (replay, run, fetch-models)."""

from __future__ import annotations

import argparse
import asyncio
import sys
import webbrowser
from collections.abc import Sequence

from lookaway.capture.replay import ReplaySource
from lookaway.config import config_sha256, load_config
from lookaway.events import EventBus, TrackUpdated
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


def _run(config: str | None, source: str | None, open_browser: bool) -> int:
    from lookaway.app import run_app

    cfg = load_config(config, source)

    def ready(port: int) -> None:
        url = f"http://{cfg.render.host}:{port}/"
        print(f"heads at {url}  (Ctrl-C to quit)")
        if open_browser:
            webbrowser.open(url)

    try:
        asyncio.run(run_app(cfg, on_ready=ready))
    except KeyboardInterrupt:
        pass
    except (FileNotFoundError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


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
    fm = sub.add_parser("fetch-models", help="download models with a SHA-256 check")
    fm.add_argument("--config")
    sub.add_parser("bench")
    args = parser.parse_args(argv)
    if args.cmd == "replay":
        return _replay(args.path, args.config)
    if args.cmd == "fetch-models":
        return _fetch_models(args.config)
    if args.cmd == "run":
        return _run(args.config, args.source, not args.no_browser)
    print(f"lookaway {args.cmd}: not implemented yet (see SPECS/50-roadmap.md)", file=sys.stderr)
    return 2
