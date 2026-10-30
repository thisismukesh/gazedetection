"""Record landmarks (never images) from the webcam for fixtures. Consent-gated, development only.

Run: uv run python tools/record_landmarks.py --consent-id C-001 --seconds 20 \
       --out ~/lookaway-recordings/clip.jsonl
The output must be outside the repository (SPECS/21 P5). Keep consent forms with the project lead.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lookaway.app import build_perception, build_source
from lookaway.clock import MonotonicClock
from lookaway.config import load_config
from lookaway.recording import RecordingRefused, record_landmarks

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--consent-id", required=True)
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--source", default=None)
    args = ap.parse_args()
    cfg = load_config(ROOT / "config" / "dev.toml", args.source)
    src = build_source(cfg, MonotonicClock())
    src.open()
    try:
        n = record_landmarks(
            cfg,
            src,
            build_perception(cfg),
            Path(args.out).expanduser(),
            args.seconds,
            args.consent_id,
        )
    except RecordingRefused as e:
        print(f"refused: {e}")
        return 2
    finally:
        src.close()
    print(f"wrote {n} frames of landmarks to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
