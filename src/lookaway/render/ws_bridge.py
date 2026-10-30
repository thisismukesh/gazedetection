"""WebSocket + static HTTP server for the Three.js client. Implements SPECS/17.

AC-REN-01 (snapshot first), AC-REN-02 (client loss never disturbs the pipeline).
"""

from __future__ import annotations

import asyncio
import contextlib
import mimetypes
from collections.abc import Callable
from pathlib import Path

import structlog
from websockets.asyncio.server import Server, ServerConnection, broadcast, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response

from lookaway.events import EventBus, HeadModeChanged
from lookaway.render import protocol
from lookaway.types import HeadCommand

_log = structlog.get_logger("lookaway.render")
_LOOPBACK = {"127.0.0.1", "localhost", "::1"}
_ALLOWED_SUFFIX = {".html", ".js", ".css", ".glb", ".json", ".svg", ".png"}


class RenderBridge:
    def __init__(
        self,
        host: str,
        port: int,
        web_dir: Path,
        n_heads: int,
        yaw_limit_rad: float,
        pitch_limit_rad: float,
        rate_hz: int,
        allow_lan: bool,
        now: Callable[[], float],
    ) -> None:
        if host not in _LOOPBACK and not allow_lan:
            raise ValueError("render.host is not loopback; set render.allow_lan = true to allow")
        self._host, self._port = host, port
        self._web = web_dir.resolve()
        self._heads = [protocol.HeadView(i) for i in range(n_heads)]
        self._limits = (yaw_limit_rad, pitch_limit_rad)
        self._period = 1.0 / rate_hz
        self._now = now
        self._clients: set[ServerConnection] = set()
        self._server: Server | None = None
        self._task: asyncio.Task[None] | None = None

    # -- state inputs -----------------------------------------------------------------------

    def update_command(self, cmd: HeadCommand) -> None:
        h = self._heads[cmd.head_id]
        h.yaw, h.pitch = cmd.yaw_rad, cmd.pitch_rad

    def on_mode_changed(self, e: HeadModeChanged) -> None:
        h = self._heads[e.head_id]
        h.mode, h.target_track = e.mode, e.target_track

    @property
    def has_clients(self) -> bool:
        return bool(self._clients)

    def publish_frame(self, jpeg: bytes) -> None:
        """Camera view (D11): a binary message, dropped when nobody is connected."""
        if self._clients:
            broadcast(self._clients, jpeg)

    def publish_debug(self, message: str) -> None:
        if self._clients:
            broadcast(self._clients, message)

    def attach(self, bus: EventBus) -> None:
        bus.subscribe(HeadModeChanged, self.on_mode_changed)

    # -- lifecycle --------------------------------------------------------------------------

    @property
    def port(self) -> int:
        assert self._server is not None
        return int(next(iter(self._server.sockets)).getsockname()[1])

    async def start(self) -> None:
        self._server = await serve(
            self._handler, self._host, self._port, process_request=self._http, compression=None
        )
        self._task = asyncio.create_task(self._broadcast_loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    # -- internals --------------------------------------------------------------------------

    async def _handler(self, ws: ServerConnection) -> None:
        await ws.send(protocol.snapshot(self._heads, *self._limits))
        self._clients.add(ws)
        try:
            async for _msg in ws:  # client hello and anything else is ignored
                pass
        except Exception:
            _log.warning("client_error")
        finally:
            self._clients.discard(ws)

    async def _broadcast_loop(self) -> None:
        while True:
            await asyncio.sleep(self._period)
            if self._clients:
                broadcast(self._clients, protocol.head_state(self._now(), self._heads))

    def _http(self, _ws: ServerConnection, request: Request) -> Response | None:
        if request.headers.get("Upgrade", "").lower() == "websocket":
            return None
        rel = request.path.split("?", 1)[0].lstrip("/") or "index.html"
        target = (self._web / rel).resolve()
        ok = (
            target.is_file()
            and target.suffix in _ALLOWED_SUFFIX
            and target.is_relative_to(self._web)
        )
        if not ok:
            return Response(404, "Not Found", Headers(), b"not found\n")
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        headers = Headers([("Content-Type", ctype), ("Cache-Control", "no-store")])
        return Response(200, "OK", headers, target.read_bytes())
