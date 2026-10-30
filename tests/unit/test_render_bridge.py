from __future__ import annotations

import asyncio
import json
import urllib.request
from pathlib import Path

import pytest
from websockets.asyncio.client import connect

from lookaway.events import EventBus, HeadModeChanged
from lookaway.render.ws_bridge import RenderBridge
from lookaway.types import HeadCommand, HeadMode


@pytest.fixture
async def bridge(tmp_path: Path):  # noqa: ANN201
    (tmp_path / "index.html").write_text("<html>ok</html>")
    (tmp_path / "secret.txt").write_text("nope")
    b = RenderBridge("127.0.0.1", 0, tmp_path, 3, 1.0, 0.5, 100, False, lambda: 1.0)
    await b.start()
    yield b
    await b.stop()


async def test_AC_REN_01_snapshot_is_first_message(bridge: RenderBridge) -> None:
    async with connect(f"ws://127.0.0.1:{bridge.port}/") as ws:
        first = json.loads(await ws.recv())
        assert first["type"] == "snapshot" and first["v"] == 1
        assert [h["id"] for h in first["heads"]] == [0, 1, 2]
        assert first["limits"] == {"yaw": 1.0, "pitch": 0.5}
        await ws.send(json.dumps({"type": "hello", "client": "three"}))
        nxt = json.loads(await ws.recv())
        assert nxt["type"] == "head_state"


async def test_head_state_reflects_commands_and_modes(bridge: RenderBridge) -> None:
    bus = EventBus()
    bridge.attach(bus)
    bridge.update_command(HeadCommand(1, 0.0, 0.25, -0.1))
    bus.publish(HeadModeChanged(0.0, 1, HeadMode.ORIENT, 7))
    async with connect(f"ws://127.0.0.1:{bridge.port}/") as ws:
        await ws.recv()
        msg = json.loads(await ws.recv())
        h = msg["heads"][1]
        assert (h["yaw"], h["pitch"], h["mode"], h["target_track"]) == (0.25, -0.1, "orient", 7)


async def test_AC_REN_02_client_drop_does_not_break_bridge(bridge: RenderBridge) -> None:
    ws = await connect(f"ws://127.0.0.1:{bridge.port}/")
    await ws.recv()
    ws.transport.abort()  # abrupt disconnect, no close handshake
    await asyncio.sleep(0.1)
    async with connect(f"ws://127.0.0.1:{bridge.port}/") as ws2:
        assert json.loads(await ws2.recv())["type"] == "snapshot"
        assert json.loads(await ws2.recv())["type"] == "head_state"


async def test_http_serves_index_and_blocks_other_paths(bridge: RenderBridge) -> None:
    loop = asyncio.get_running_loop()

    def get(path: str) -> int:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{bridge.port}{path}") as r:
                return int(r.status)
        except urllib.error.HTTPError as e:
            return int(e.code)

    assert await loop.run_in_executor(None, get, "/") == 200
    assert await loop.run_in_executor(None, get, "/secret.txt") == 404
    assert await loop.run_in_executor(None, get, "/../CLAUDE.md") == 404


def test_non_loopback_host_requires_allow_lan(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        RenderBridge("0.0.0.0", 0, tmp_path, 3, 1.0, 0.5, 60, False, lambda: 0.0)
    RenderBridge("0.0.0.0", 0, tmp_path, 3, 1.0, 0.5, 60, True, lambda: 0.0)


async def test_AC_REN_04_binary_frames_follow_snapshot_and_need_a_client(
    bridge: RenderBridge,
) -> None:
    bridge.publish_frame(b"\xff\xd8nobody-listening")  # no client: must be a no-op, not an error
    assert bridge.has_clients is False
    async with connect(f"ws://127.0.0.1:{bridge.port}/") as ws:
        first = await ws.recv()
        assert isinstance(first, str) and json.loads(first)["type"] == "snapshot"
        await asyncio.sleep(0.05)
        assert bridge.has_clients is True
        bridge.publish_frame(b"\xff\xd8frame")
        got: object = None
        for _ in range(20):  # head_state messages may interleave
            got = await ws.recv()
            if isinstance(got, bytes):
                break
        assert got == b"\xff\xd8frame"
