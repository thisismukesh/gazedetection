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
    task = asyncio.create_task(run_app(cfg, stop=stop, on_ready=port.append, seed=5))
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
                        if h["id"] != 1:
                            max_yaw[h["id"]] = max(max_yaw[h["id"]], abs(h["yaw"]))
                    h1 = msg["heads"][1]
                    modes.add(h1["mode"])
                    if h1["mode"] in ("orient", "hold"):
                        max_yaw[1] = max(max_yaw[1], abs(h1["yaw"]))
                    if max_yaw[1] > 0.3:  # staring turns ~0.5 rad; wander tops out at 0.24
                        break
    finally:
        stop.set()
        await asyncio.wait_for(task, 5.0)
    assert max_yaw[1] > 0.3
    assert max_yaw[0] < 0.05 and max_yaw[2] < 0.05  # idle sway only (2 deg)
    assert "orient" in modes or "hold" in modes


async def test_two_people_one_zone_each_get_a_head_looker_stared_at(tmp_path: Path) -> None:
    path = tmp_path / "two.jsonl"
    write_jsonl(path, scenarios.two_in_one_zone(seconds=7.0))
    cfg = load_config(source=f"replay:{path}")
    cfg = cfg.model_copy(update={"render": cfg.render.model_copy(update={"port": 0})})
    stop = asyncio.Event()
    port: list[int] = []
    task = asyncio.create_task(run_app(cfg, stop=stop, on_ready=port.append, seed=3))
    for _ in range(100):
        if port:
            break
        await asyncio.sleep(0.05)
    span = [[0.0, 0.0] for _ in range(3)]  # per head: [min yaw, max yaw]
    orient: set[int] = set()
    try:
        async with connect(f"ws://127.0.0.1:{port[0]}/") as ws:
            async with asyncio.timeout(8.0):
                end = asyncio.get_running_loop().time() + 6.0
                while asyncio.get_running_loop().time() < end:
                    msg = json.loads(await ws.recv())
                    if msg["type"] != "head_state":
                        continue
                    for h in msg["heads"]:
                        span[h["id"]][0] = min(span[h["id"]][0], h["yaw"])
                        span[h["id"]][1] = max(span[h["id"]][1], h["yaw"])
                        if h["mode"] in ("orient", "hold"):
                            orient.add(h["id"])
    finally:
        stop.set()
        await asyncio.wait_for(task, 5.0)
    assert len(orient) == 1  # only the person who looked away is stared at
    watched = {1, 0, 2} - {i for i in range(3) if max(abs(x) for x in span[i]) < 0.06}
    assert len(watched) == 2  # two people -> two heads in motion (stare + wander)
