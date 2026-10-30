# Look Away

A gaze-reactive art piece developed with Prof. Dennis Hong (RoMeLa, UCLA).

Three outward-facing cameras watch the people around the piece. Each camera is bound to one
mannequin head. When someone who was looking at the piece looks away, the head bound to that
camera turns toward them, follows them for a while, then returns to neutral. It does this every
time someone looks away.

**This repository builds the laptop demo:** one webcam split into three zones, with three heads
rendered on screen. Every camera and actuator goes through the `CameraSource` and `HeadDriver`
interfaces, so the physical rig can replace the webcam and on-screen heads later without touching
perception, attention or control logic.

## Status

Milestone **M1 (walking skeleton)** is in progress. Behaviour is defined in [`SPECS/`](SPECS/);
progress against acceptance criteria is tracked in [`SPECS/50-roadmap.md`](SPECS/50-roadmap.md).

| Area | State |
|---|---|
| Config (TOML, pydantic, spec-matching guardrail) | done |
| Clock, types, event bus | done |
| 1-euro filter, attention state machine (AC-SM-01..09, I1..I6) | done |
| Geometric attention scorer (AC-ATT-01..07) | done |
| IoU/Hungarian tracker (AC-TRK-01..04) | done |
| Capture: video file, replay, read supervisor (AC-CAP-01..04) | done. AC-CAP-03 reads "0.5, 1, 2, 5 s" as delays between retries (attempts at 0.5, 1.5, 3.5, 8.5 s); needs project-lead confirmation |
| Webcam source | written, needs a live camera to verify |
| Sector zone map with hysteresis (AC-ZONE-01..04, ownership half of 05) | done (planned for M2, needed by the pipeline) |
| Pipeline + replay determinism (AC-SYS-04) | done |
| Privacy test (no file writes) | done for replay and video sources |
| `web/pose.js` mapping (AC-REN-03) | done |
| MediaPipe Face Landmarker perception, `fetch-models` | not started |
| Head controller (targeting, motion, policy), drivers | not started |
| WebSocket bridge and Three.js heads (`web/`) | not started |
| `lookaway run`, `bench`, debug overlay | not started |

The pipeline currently runs on recorded or synthetic landmark streams, with no camera or model.

## Quick start

Requires [uv](https://docs.astral.sh/uv/). The project pins Python 3.12.

```bash
uv sync
uv run lookaway replay tests/fixtures/landmarks/two_people.jsonl
```

Example output (one person in the audience's right zone looks away at 3.4 s and back at 6.4 s):

```
   0.367  GazeAcquired  GazeAcquired(t=0.367, track_id=2, zone_id=2)
   3.367  GazeLost      GazeLost(t=3.367, track_id=2, zone_id=2, ...)
   6.433  GazeRegained  GazeRegained(t=6.433, track_id=2, zone_id=2)
```

## Development

```bash
uv run pytest                                  # all default tests, no camera needed
uv run pytest --cov=lookaway                   # with coverage
uv run ruff check . && uv run ruff format --check .
uv run pyright                                 # strict on src/
uv run python -m tests.fixtures.scenarios      # regenerate synthetic landmark fixtures
node --test "web/*.test.js"                    # JS pose mapping tests
```

Workflow is spec-driven and test-first: find the SPECS section and AC IDs, write a failing
`test_AC_*` test, make it pass, refactor, cite the spec in the docstring. See
[`CLAUDE.md`](CLAUDE.md) for the full rules (purity rule for core modules, coding conventions,
definition of done).

## How it works

```
CameraSource -> latest-frame slot -> FacePerception -> Tracker -> ZoneMap
  -> AttentionScorer (head pose + iris) -> 1-euro filter -> AttentionStateMachine
  -> EventBus (GazeLost, GazeRegained, ...) -> HeadController x3 -> HeadDriver -> Three.js heads
```

Key decisions (details in [`SPECS/03-decisions.md`](SPECS/03-decisions.md)):

- **D1** heads turn by yaw and pitch only, no roll.
- **D2** viewers stand 0.5 m to 2.0 m away.
- **D3** one person triggers exactly one head; each track is owned by one zone at a time.

## Layout

```
src/lookaway/   capture/ perception/ tracking/ zones/ attention/ control/ render/ observability/
SPECS/          behaviour specs and acceptance criteria (source of truth)
config/         default.toml (mirrors SPECS/18), demo.toml, dev.toml
tests/          unit/ property/ contract/ golden/ integration/ fixtures/
web/            Three.js renderer (not started)
```

## Privacy

Everything runs on the device. In installation mode no frames, crops, landmarks or embeddings are
written anywhere (`tests/unit/test_privacy.py`). There is no face recognition or demographic or
emotion inference. See [`SPECS/21-privacy-ethics.md`](SPECS/21-privacy-ethics.md).
