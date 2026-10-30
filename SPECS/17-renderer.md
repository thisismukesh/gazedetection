# 17 Renderer

## Transport

A WebSocket server at `render.host:render.port` (default 127.0.0.1:8765) that also serves `web/` over HTTP. Bound to localhost unless `render.allow_lan = true`.

## Protocol (JSON, version 1, angles in radians)

Server to client:

- `snapshot`, sent first on every connection:
  `{"type": "snapshot", "v": 1, "heads": [{"id", "yaw", "pitch", "mode"}], "limits": {"yaw", "pitch"}}`
- `head_state`, at `render.rate_hz`:
  `{"type": "head_state", "t", "heads": [{"id", "yaw", "pitch", "mode", "target_track", "person"}]}`
  `target_track` is the face the head is staring at (ORIENT/HOLD), else null. `person` is the face the head is assigned to by the `HeadAssigner` (D6, D14), else null.
- `debug`, at `render.debug_rate_hz` when the overlay is enabled:
  `{"type": "debug", "t", "tracks": [{"id", "zone", "score", "state"}], "fps", "latency_ms": {"p50", "p95"}}`
  Never contains images or landmarks.

- Binary messages (after `snapshot`, only when `render.camera_view` is on): one JPEG of the camera frame with the overlay drawn on it (track boxes, score bars, head direction in cyan, gaze direction in yellow, iris points, assigned head), at `render.camera_view_fps`, `render.camera_view_width` pixels wide, mirrored when `capture.mirror_display`. Sent only while a client is connected.

Client to server: `{"type": "hello", "client": "three"}`.

Message schemas live in `render/protocol.py` and are covered by contract tests.

## Client (`web/`)

- `index.html` + `main.js` (Three.js, loaded from a pinned CDN version or vendored).
- Loads `assets/heads.glb` if present; otherwise draws procedural heads (sphere plus a nose cone so direction is readable).
- Layout: the camera view sits at the top middle of the page; the heads sit below it, shifted down so the two never overlap.
- Under each head, an indicator names the face it is looking at, using the same `#N` track number as the camera view: `staring at #N` (ORIENT/HOLD), `glancing · watched by #N` (assigned, not staring), `returning`, or `idle · no one`, followed by the head's live direction (`· 34° right`, as the audience sees it) whenever it is turned more than 3 degrees. It updates with every `head_state` message. The indicator is coloured per face so heads sharing a face match.
- Heads are placed left to right as zone 0, 1, 2 from the audience's view.
- Pose mapping lives in `web/pose.js` as a pure function: `rotation.order = "YXZ"`, `rotation.y = yaw`, `rotation.x = -pitch`. With the Three.js camera looking down -z at heads that face +z, positive yaw turns a face toward screen right (audience's right) and positive pitch tilts it up.
- Interpolates toward the latest state with critical damping (30 ms smoothing time, D15). Target 60 FPS.
- On disconnect, shows a sleep pose (pitch down) and reconnects with backoff.

## Acceptance

AC-REN-01 to AC-REN-03.
