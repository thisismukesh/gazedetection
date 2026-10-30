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

Milestone **M1 (walking skeleton)** is implemented. Behaviour is defined in [`SPECS/`](SPECS/);
progress against acceptance criteria is tracked in [`SPECS/50-roadmap.md`](SPECS/50-roadmap.md).

| Area | State |
|---|---|
| Config, clock, types, event bus | done |
| 1-euro filter, attention state machine (AC-SM-01..09, I1..I6) | done |
| Geometric attention scorer (AC-ATT-01..07) | done |
| IoU/Hungarian tracker (AC-TRK-01..04) | done |
| Capture: webcam, video file, replay, read supervisor (AC-CAP-01..04) | done. AC-CAP-03 reads "0.5, 1, 2, 5 s" as delays between retries (attempts at 0.5, 1.5, 3.5, 8.5 s); needs project-lead confirmation |
| MediaPipe Face Landmarker perception, `fetch-models` (SHA-256 pinned) | done; webcam run verified on a MacBook (30 fps, face on every frame) |
| Sector zone map with hysteresis (AC-ZONE-01..05) | done |
| Head controller: targeting, motion limits, policy (AC-HEAD-01..08), drivers (simulated, recording, serial stub) | done |
| WebSocket bridge + Three.js heads (AC-REN-01..03) | done; three procedural heads render in Chrome |
| `lookaway run` / `replay` / `fetch-models`, whole-app replay test | done |
| AC-PER-05 axis and wink-side check against a real face | **pending**: run `tools/check_orientation.py` (guided, 20 s) |
| Debug overlay, metrics, `bench`, golden and integration clips, GLB heads | not started (M2/M3) |

## Quick start

Requires [uv](https://docs.astral.sh/uv/). The project pins Python 3.12.

```bash
uv sync
uv run lookaway fetch-models        # one-time model download, SHA-256 checked
uv run lookaway run                 # webcam 0, opens the heads in your browser
uv run lookaway run --source webcam:1                           # pick another camera
uv run lookaway run --source replay:tests/fixtures/landmarks/two_people.jsonl   # no camera
uv run lookaway replay tests/fixtures/landmarks/two_people.jsonl   # print events only
```

**macOS:** the first webcam run asks for camera access for your terminal app. If it is denied,
enable it in System Settings > Privacy & Security > Camera. If index 0 is your iPhone (Continuity
Camera), use `--source webcam:1`. Frames are processed in memory and never stored.

Stand 0.5 m to 2 m from the laptop. Look at the screen, then look away: the head for your zone
(left, middle or right third of the camera view, as the audience sees it) turns toward you.
Place the heads display close under the webcam so the direction reads correctly.

## Development

```bash
uv run pytest                                  # all default tests, no camera needed
uv run pytest --cov=lookaway                   # with coverage
uv run ruff check . && uv run ruff format --check .
uv run pyright                                 # strict on src/
uv run python -m tests.fixtures.scenarios      # regenerate synthetic landmark fixtures
uv run python tools/check_orientation.py       # guided webcam check of head axes (AC-PER-05)
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
web/            Three.js renderer (vendored Three.js r160, MIT)
```

## Privacy

Everything runs on the device. In installation mode no frames, crops, landmarks or embeddings are
written anywhere (`tests/unit/test_privacy.py`). There is no face recognition or demographic or
emotion inference. See [`SPECS/21-privacy-ethics.md`](SPECS/21-privacy-ethics.md).
