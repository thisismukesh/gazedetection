# 17 Renderer

## Transport

A WebSocket server at `render.host:render.port` (default 127.0.0.1:8765) that also serves `web/` over HTTP. Bound to localhost unless `render.allow_lan = true`.

## Protocol (JSON, version 1, angles in radians)

Server to client:

- `snapshot`, sent first on every connection:
  `{"type": "snapshot", "v": 1, "heads": [{"id", "yaw", "pitch", "mode"}], "limits": {"yaw", "pitch"}}`
- `head_state`, at `render.rate_hz`:
  `{"type": "head_state", "t", "heads": [{"id", "yaw", "pitch", "mode", "target_track"}]}`
- `debug`, at `render.debug_rate_hz` when the overlay is enabled:
  `{"type": "debug", "t", "tracks": [{"id", "zone", "score", "state"}], "fps", "latency_ms": {"p50", "p95"}}`
  Never contains images or landmarks.

Client to server: `{"type": "hello", "client": "three"}`.

Message schemas live in `render/protocol.py` and are covered by contract tests.

## Client (`web/`)

- `index.html` + `main.js` (Three.js, loaded from a pinned CDN version or vendored).
- Loads `assets/heads.glb` if present; otherwise draws procedural heads (sphere plus a nose cone so direction is readable).
- Heads are placed left to right as zone 0, 1, 2 from the audience's view.
- Pose mapping lives in `web/pose.js` as a pure function: `rotation.order = "YXZ"`, `rotation.y = yaw`, `rotation.x = -pitch`. With the Three.js camera looking down -z at heads that face +z, positive yaw turns a face toward screen right (audience's right) and positive pitch tilts it up.
- Interpolates toward the latest state with critical damping. Target 60 FPS.
- On disconnect, shows a sleep pose (pitch down) and reconnects with backoff.

## Acceptance

AC-REN-01 to AC-REN-03.
