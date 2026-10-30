"""Whole app (threads, asyncio control loop, bridge) on a synthetic replay: no camera, no model."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from websockets.asyncio.client import connect

from lookaway.app import run_app
from lookaway.config import load_config
from lookaway.perception.replay import write_jsonl
from tests.fixtures import scenarios


async def test_look_away_turns_only_the_owning_head(tmp_path: Path) -> None:
    path = tmp_path / "s.jsonl"
    write_jsonl(path, scenarios.single_look_away(seconds=5.0, away=(1.0, 4.0), x_px=520.0))
    cfg = load_config(source=f"replay:{path}")
    cfg = cfg.model_copy(update={"render": cfg.render.model_copy(update={"port": 0})})
    stop = asyncio.Event()
    port: list[int] = []
    task = asyncio.create_task(run_app(cfg, stop=stop, on_ready=port.append))
    for _ in range(100):
        if port:
            break
        await asyncio.sleep(0.05)
    assert port
    max_yaw = [0.0, 0.0, 0.0]
    modes: set[str] = set()
    try:
        async with connect(f"ws://127.0.0.1:{port[0]}/") as ws:
            async with asyncio.timeout(6.0):
                while True:
                    msg = json.loads(await ws.recv())
                    if msg["type"] != "head_state":
                        continue
                    for h in msg["heads"]:
                        max_yaw[h["id"]] = max(max_yaw[h["id"]], abs(h["yaw"]))
                    modes.add(msg["heads"][1]["mode"])
                    if max_yaw[1] > 0.15:
                        break
    finally:
        stop.set()
        await asyncio.wait_for(task, 5.0)
    assert max_yaw[1] > 0.15
    assert max_yaw[0] < 0.05 and max_yaw[2] < 0.05  # idle sway only (2 deg)
    assert "orient" in modes or "hold" in modes
