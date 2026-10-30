"""Command line entry point. Implements CLAUDE.md §7. Only ``replay`` exists in M1 so far."""

from __future__ import annotations

import argparse
import sys
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lookaway")
    sub = parser.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("replay", help="run the pipeline on a landmark JSONL (no camera, no model)")
    rp.add_argument("path")
    rp.add_argument("--config")
    for name in ("run", "bench", "fetch-models"):
        sub.add_parser(name)
    args = parser.parse_args(argv)
    if args.cmd == "replay":
        return _replay(args.path, args.config)
    print(f"lookaway {args.cmd}: not implemented yet (see SPECS/50-roadmap.md)", file=sys.stderr)
    return 2
