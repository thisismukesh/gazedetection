# 02 Architecture

## Layers

1. **Sources** (`capture/`): `CameraSource` implementations, each feeding a `LatestFrameSlot`.
2. **Perception** (`perception/`): `FacePerception` returns `FaceObservation`s for a frame.
3. **Tracking** (`tracking/`): `Tracker` returns `Track`s with ephemeral IDs.
4. **Zones** (`zones/`): `ZoneMap` assigns each confirmed track one owning zone.
5. **Attention** (`attention/`): `AttentionScorer` returns an `AttentionSample`; `AttentionStateMachine` returns events.
6. **Bus** (`events.py`): synchronous in-process pub/sub. Publishing from the perception thread into the asyncio loop uses `loop.call_soon_threadsafe`.
7. **Control** (`control/`): one `HeadController` per head (policy, targeting, motion profile).
8. **Drivers** (`control/drivers/`): `HeadDriver` implementations.
9. **Render** (`render/` + `web/`): WebSocket bridge, JSON protocol, Three.js client.
10. **Observability** (`observability/`): logs, metrics, overlay.

## Data flow per frame

```
frame = slot.take_latest()
obs   = perception.process(frame)                 # list[FaceObservation]
tracks = tracker.update(obs, frame.t_capture)     # list[Track]
for track in confirmed(tracks):
    zone   = zone_map.assign(track, t)            # exactly one zone
    sample = scorer.score(track.last_obs)         # AttentionSample
    events = machines[track.id].step(t, sample, zone, bearing)
    bus.publish_all(events)
for missing track: machines[id].step(t, None, ...)
```

## Concurrency

- Capture thread per source writes into a single-slot buffer and overwrites stale frames. Dropped frames are counted.
- Perception thread loops: take latest frame, process, publish events.
- Main asyncio loop: control tick at `control.rate_hz`, render broadcast at `render.rate_hz`.
- The debug overlay runs in the perception thread because OpenCV GUI calls must stay on one thread.

## Dependency rule

Pure modules (listed in CLAUDE.md section 5) import only the standard library, NumPy, `lookaway.types` and `lookaway.events`. `tests/unit/test_import_rules.py` parses imports with `ast` and fails on violations.

## Composition root

`app.py` builds the object graph from a validated `Config`. Tests build subgraphs with fakes (`FakeClock`, `ReplayPerception`, `RecordingHeadDriver`).

## Extension points for the physical piece

| Interface | Demo implementation | Physical implementation (later) |
|---|---|---|
| `CameraSource` | `WebcamSource`, `VideoFileSource`, `ReplaySource` | Three `WebcamSource`s or GStreamer sources |
| `ZoneMap` | `SectorZoneMap` (one frame, three sectors) | `CameraZoneMap` (zone = camera id, ownership rule for overlaps) |
| `HeadDriver` | `SimulatedHeadDriver` | `SerialHeadDriver` (pan/tilt servos via microcontroller) |

## Dependencies and licenses

| Dependency | License | Use |
|---|---|---|
| OpenCV (`opencv-python`) | Apache-2.0 | capture, overlay |
| MediaPipe | Apache-2.0 | Face Landmarker |
| NumPy, SciPy | BSD-3-Clause | math, Hungarian assignment |
| pydantic | MIT | config |
| structlog | MIT / Apache-2.0 | logging |
| websockets | BSD-3-Clause | render bridge |
| Three.js | MIT | renderer |
| pytest, hypothesis, pytest-asyncio | MIT / MPL-2.0 | tests |
| ruff, pyright | MIT | lint, types |

Optional scorer plug-ins (ONNX Runtime, MIT) are not part of M1 to M3. Weights with non-commercial terms stay behind `privacy.allow_restricted_models`.
