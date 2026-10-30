"""P2 / NFR-PRIV-01: the pipeline writes nothing to disk in installation mode."""

from __future__ import annotations

import builtins
from pathlib import Path
from typing import Any

import cv2
import pytest

from lookaway.capture.replay import ReplaySource
from lookaway.config import load_config
from lookaway.events import EventBus
from lookaway.perception.replay import ReplayPerception, write_jsonl
from lookaway.pipeline import build_pipeline
from tests.fixtures import scenarios


def test_pipeline_performs_no_file_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "s.jsonl"
    write_jsonl(path, scenarios.single_look_away(seconds=4.0, away=(1.5, 3.0)))
    cfg = load_config()
    assert cfg.privacy.mode == "installation"
    src = ReplaySource(path, cfg.capture.width, cfg.capture.height, cfg.capture.hfov_rad, 30)
    perception = ReplayPerception(path)
    pipe = build_pipeline(cfg, src.info, perception, EventBus())
    src.open()

    real_open = builtins.open
    writes: list[str] = []

    def guarded_open(file: Any, mode: str = "r", *a: Any, **k: Any) -> Any:
        if any(c in mode for c in "wax+"):
            writes.append(f"open({file!r}, {mode!r})")
        return real_open(file, mode, *a, **k)

    def forbid(name: str) -> Any:
        def _f(*_a: Any, **_k: Any) -> None:
            writes.append(name)

        return _f

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(cv2, "imwrite", forbid("cv2.imwrite"))
    monkeypatch.setattr(cv2, "VideoWriter", forbid("cv2.VideoWriter"))
    monkeypatch.setattr(Path, "write_text", forbid("Path.write_text"))
    monkeypatch.setattr(Path, "write_bytes", forbid("Path.write_bytes"))

    while (frame := src.read()) is not None:
        pipe.process(frame)
    assert writes == []
