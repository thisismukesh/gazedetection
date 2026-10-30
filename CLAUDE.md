# CLAUDE.md

Guidance for Claude Code working in this repository. Read this file fully before any change.

## 1. Project

**Look Away** is a gaze-reactive art piece developed with Prof. Dennis Hong (RoMeLa, UCLA).

The full piece: three outward-facing cameras (120° horizontal FOV each) mounted on a triangle so no camera sees another, plus three mannequin heads. Each camera watches the people in its view. When a person who was looking at the piece looks away, the head bound to that camera turns toward that person and follows them. It does this every time someone looks away.

**This repo builds the laptop demo.** One webcam, three heads rendered on screen. The webcam frame is split into three zones, one per head, standing in for the three cameras. Physical cameras and actuators are out of scope now, but every camera and actuator access goes through the `CameraSource` and `HeadDriver` interfaces so the physical rig can replace the webcam and the on-screen heads without touching perception, attention or control logic.

### Fixed decisions (see `SPECS/03-decisions.md`)

- **D1 Head motion:** the head turns toward the person by adjusting yaw (horizontal) and pitch (vertical). No roll, no head-cock. Heads are 2-DOF pan/tilt.
- **D2 Viewing distance:** viewers stand a few feet away. Design envelope is 0.5 m to 2.0 m. MediaPipe's built-in short-range face detector covers this; no far-range detector.
- **D3 Ownership:** one person triggers exactly one head. Every track is owned by exactly one zone at a time, and only that zone's head reacts to it.

Do not change these without a spec change approved by the project lead.

## 2. Repo state

M1 is in progress. Done: scaffold, config, core types and events, state machine, scorer, tracker, capture, replay, sector zone map, pipeline, `lookaway replay`. Not started: MediaPipe perception, head controller and drivers, WebSocket bridge, `web/`, `run`/`bench`/`fetch-models`. See the status table in `README.md`.

## 3. Source of truth

- `SPECS/` defines behaviour. Code implements specs. Tests verify the acceptance criteria (AC IDs) in `SPECS/30-acceptance-criteria.md`.
- If code and spec disagree, the spec wins until someone edits the spec.
- Numeric defaults live in one place: the TOML block in `SPECS/18-config.md`. `config/default.toml` must match it exactly; `tests/unit/test_config_matches_spec.py` enforces this. Specs and code reference config keys, never literal numbers.
- Decisions that change scope or behaviour get an entry in `SPECS/03-decisions.md`.

## 4. Architecture

```
CameraSource (webcam | video file | replay)
  -> latest-frame slot (drop stale frames, never queue)
  -> FacePerception (MediaPipe Face Landmarker: landmarks, iris, head pose, blink)
  -> Tracker (IoU + Hungarian, ephemeral IDs)
  -> ZoneMap (audience-frame x -> owning zone, with hysteresis)
  -> AttentionScorer (head pose + iris -> angle to camera -> score, 1-euro filtered)
  -> AttentionStateMachine per track (hysteresis + dwell + cooldown)
  -> EventBus (GazeLost, GazeRegained, TrackUpdated, TrackLost, ...)
  -> HeadController x3 (policy + yaw/pitch target + motion limits)
  -> HeadDriver (SimulatedHeadDriver -> WebSocket -> Three.js heads in browser)
DebugOverlay subscribes to the bus (OpenCV window, toggle D).
```

Concurrency: one capture thread per source writing to a latest-frame slot; one perception thread; one asyncio loop running the control tick (100 Hz) and the render broadcast (60 Hz). All time comes from an injected `Clock`.

Full detail: `SPECS/02-architecture.md`.

## 5. Directory layout

```
look-away/
├── CLAUDE.md
├── README.md
├── pyproject.toml              # uv; ruff, pyright, pytest config
├── uv.lock
├── config/
│   ├── default.toml            # mirrors SPECS/18-config.md
│   ├── demo.toml               # laptop demo overrides
│   └── dev.toml                # privacy.mode = "development"
├── SPECS/
├── src/lookaway/
│   ├── app.py                  # composition root
│   ├── cli.py                  # lookaway run | replay | bench | fetch-models
│   ├── clock.py                # Clock, MonotonicClock, FakeClock
│   ├── types.py                # all cross-module value types (SPECS/20)
│   ├── events.py               # EventBus + event types
│   ├── config.py               # pydantic models
│   ├── capture/                # base.py, webcam.py, video_file.py, replay.py, slot.py
│   ├── perception/             # base.py, mediapipe_face.py, replay.py, geometry.py
│   ├── tracking/               # iou_tracker.py
│   ├── zones/                  # zone_map.py
│   ├── attention/              # scorer_base.py, geometric.py, one_euro.py, state_machine.py
│   ├── control/                # targeting.py, motion.py, policy.py, head_controller.py
│   │   └── drivers/            # base.py, simulated.py, serial_stub.py
│   ├── render/                 # ws_bridge.py, protocol.py
│   └── observability/          # logging.py, metrics.py, overlay.py
├── web/                        # index.html, main.js (Three.js), pose.js (pure), pose.test.js, assets/
├── tests/
│   ├── unit/ property/ contract/ golden/ integration/
│   └── fixtures/               # synth.py, landmark JSONL, golden event JSON
├── tools/                      # record_landmarks.py (consent-gated), fetch_models.py
└── models/                     # gitignored, fetched with SHA-256 check
```

### Purity rule

These modules are **pure**: `attention/state_machine.py`, `attention/one_euro.py`, `zones/zone_map.py`, `control/targeting.py`, `control/motion.py`, `control/policy.py`, `perception/geometry.py`. They import only the standard library, NumPy, `types` and `events`. No OpenCV, no MediaPipe, no threads, no I/O, no wall-clock. They take inputs plus a timestamp and return outputs. `tests/unit/test_import_rules.py` enforces this.

Only `capture/*`, `perception/mediapipe_face.py`, `render/*`, `control/drivers/*`, `observability/overlay.py`, `cli.py` and `app.py` may touch cameras, models, sockets, the GUI or the filesystem.

## 6. Tech stack

Python 3.12, uv, OpenCV, MediaPipe Tasks (Face Landmarker), NumPy, SciPy, pydantic v2, structlog, websockets, Three.js (in `web/`), pytest, hypothesis, pytest-asyncio, ruff, pyright (strict on `src/`).

Adding a runtime dependency requires updating the table in `SPECS/02-architecture.md` with its license.

## 7. Commands

```bash
uv sync                                                   # install
uv run lookaway fetch-models                              # download models with SHA-256 check
uv run lookaway run --config config/demo.toml             # live demo, webcam 0
uv run lookaway run --config config/demo.toml --source video:path/to/clip.mp4
uv run lookaway replay tests/fixtures/landmarks/two_people.jsonl   # no camera, no model
uv run lookaway bench --config config/demo.toml           # latency and FPS report

uv run pytest                                             # all default tests, no camera needed
uv run pytest -m "not integration"                        # fast loop
uv run pytest --update-golden                             # regenerate golden files, review the diff
uv run ruff check . && uv run ruff format --check .
uv run pyright
node --test "web/*.test.js"                              # web/pose.js mapping tests (Node 22: bare `web/` fails)
```

Renderer: http://127.0.0.1:8765 (served by the app). Overlay keys: `D` toggle, `Q` quit.

## 8. Coding conventions

- Type hints everywhere. pyright strict passes on `src/`. No `Any` in public signatures.
- Value types: `@dataclass(frozen=True, slots=True)`. Interfaces: `typing.Protocol`.
- Angles are radians internally, degrees only in config and UI. Suffix names `_rad` or `_deg`.
- Time is float seconds from `Clock.now()` (monotonic). Never call `time.time()`, `time.monotonic()` or `time.sleep()` outside `clock.py` and the asyncio loop driver.
- Name coordinate frames explicitly: `p_cam`, `p_aud`, `p_head`. Camera frame is OpenCV (x right, y down, z forward). The audience frame is defined in `SPECS/15-zones-and-views.md`.
- No global state. Dependencies are passed to constructors in `app.py`.
- Log through structlog. Never log images, crops, landmark arrays or embeddings.
- Keep functions under about 40 lines and modules single-purpose.
- Every implementing class or function has a docstring citing its spec, for example `"""Implements SPECS/14 §3. AC-SM-01..08."""`.
- Pure modules do not raise on valid inputs. Validate at the config boundary.

## 9. Workflow: spec-driven + TDD (mandatory)

For every change, in this order:

1. **Spec.** Find the SPECS section and AC IDs that cover the change. If the behaviour is new or different, edit the spec and `SPECS/30-acceptance-criteria.md` first. No code without a spec reference.
2. **Red.** Write a failing test named after the AC ID, e.g. `test_AC_SM_03_blink_does_not_trigger`. Run it and confirm it fails for the expected reason.
3. **Green.** Write the minimum code that passes. Do not add untested behaviour.
4. **Refactor.** Clean up with all tests green. Run ruff and pyright.
5. **Trace.** Add the spec reference to the docstring.

If asked to "just implement X", still follow steps 1 to 5 and show the failing test before the implementation.

Commit message format: `<area>: <change> [AC-XXX-NN, ...]`.

## 10. Testing strategy

- **Unit** (`tests/unit`): pure modules with synthetic inputs, geometry against hand-computed cases, `FakeClock` for all timing.
- **Property** (`tests/property`, Hypothesis): state machine invariants, zone ownership invariants, motion limits, pixel/bearing round trips.
- **Contract** (`tests/contract`): every `CameraSource`, `FacePerception`, `AttentionScorer` and `HeadDriver` implementation passes the shared suite for its interface.
- **Golden** (`tests/golden`): recorded landmark JSONL in, expected event JSON out. Regenerate only with `--update-golden` and explain the diff.
- **Integration** (`tests/integration`, marker `integration`): full pipeline headless on short consented clips with label sidecars. Needs the model file (cached in CI).
- **Manual** (marker `manual`, skipped by default): anything needing a live camera, GPU or display.

CI never uses a live camera. Coverage: 90% lines on pure modules, 75% overall.

Details: `SPECS/40-test-plan.md`.

## 11. Definition of done

- Spec and AC IDs exist for the behaviour, updated first if behaviour changed.
- A failing test was written first and now passes. Invariants have property tests.
- `ruff check`, `ruff format --check`, `pyright`, and `pytest` are green locally and in CI.
- `config/default.toml` still matches `SPECS/18-config.md`.
- `lookaway bench` p95 latency is within `SPECS/01-requirements.md` NFR-PERF.
- `tests/unit/test_privacy.py` is green.

## 12. Do not

- Do not import OpenCV, MediaPipe or socket libraries outside the modules allowed in section 5.
- Do not write frames, crops, landmarks or embeddings to disk or network, except landmarks via `tools/record_landmarks.py` with `--consent-id` in development mode.
- Do not add face recognition, re-identification, or age, gender or emotion inference.
- Do not add roll to the heads, a far-range detector, or multi-head reactions to one person. These contradict D1 to D3.
- Do not enable non-commercially-licensed weights (Gaze360-trained L2CS-Net, OpenFace, eye-contact-cnn) by default. Plug-ins need `privacy.allow_restricted_models = true` and print a license warning at startup.
- Do not queue frames. Always process the latest frame.
- Do not change numeric defaults in code. Change the spec TOML and `config/default.toml` together.
- Do not widen a test tolerance to fix a flaky test without a spec change.
- Do not commit models, videos or personal data.
