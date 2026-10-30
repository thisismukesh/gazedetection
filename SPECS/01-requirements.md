# 01 Requirements

## Functional

- **FR-01** Capture frames from a `CameraSource`: webcam, video file, or landmark replay.
- **FR-02** Divide the frame into `zones.count` (3) zones in the audience frame.
- **FR-03** Detect up to `perception.max_faces` faces per frame with landmarks including iris, head rotation, and blink scores.
- **FR-04** Give each face a stable, ephemeral track ID across frames.
- **FR-05** Assign each confirmed track to exactly one owning zone, with hysteresis at boundaries (D3).
- **FR-06** Compute a per-track attention score from head pose and iris offset.
- **FR-07** Run a per-track attention state machine. Emit `GazeLost` once per LOOKING to AWAY transition, plus `GazeAcquired`, `GazeRegained`, `TrackUpdated`, `TrackLost`.
- **FR-08** Route each `GazeLost` only to the head of the track's owning zone.
- **FR-09** That head turns toward the person by setting yaw from horizontal bearing and pitch from vertical bearing (D1), follows the person while holding, then returns to neutral.
- **FR-10** Repeat FR-09 every time a new `GazeLost` arrives, subject to cooldown and preemption rules.
- **FR-11** Render three heads in a browser at 60 FPS from streamed head states.
- **FR-12** Show a toggleable debug overlay with zones, tracks, scores, states and latencies.
- **FR-13** Run in replay mode from recorded landmark JSONL with no camera and no model.
- **FR-14** Load configuration from TOML with validation. CLI flags override source and config path.
- **FR-15** Head output goes through `HeadDriver`. The simulated driver is used now. A serial driver stub exists and passes the contract tests against a fake port.

## Non-functional

- **NFR-PERF-01** Pipeline at 24 FPS or more at 1280x720 with up to 4 faces on the reference laptop (Apple M-series or recent x86-64, CPU only).
- **NFR-PERF-02** Perception latency (capture timestamp to attention score) p95 at or below 80 ms.
- **NFR-PERF-03** Event to first changed `HeadCommand` at or below 50 ms.
- **NFR-PERF-04** Look-away onset to visible head motion at or below 450 ms with default debounce.
- **NFR-ROB-01** No trigger from blinks up to 400 ms or from score dips shorter than `attention.away_confirm_s`.
- **NFR-ROB-02** No per-user calibration.
- **NFR-ROB-03** Detects frontal faces at 0.5 m to 2.0 m in at least 95% of frames under normal indoor lighting (D2).
- **NFR-ROB-04** Runs 8 hours without crashing or growing memory by more than 50 MB.
- **NFR-PRIV-01** In installation mode, no frames, crops, landmarks or embeddings are persisted or sent off the machine.
- **NFR-PORT-01** Runs on macOS (Apple Silicon), Windows 11, and Ubuntu 22.04+ on x86-64.
- **NFR-MAINT-01** Pure modules have 90% line coverage or more. pyright strict is clean.
- **NFR-LIC-01** The default configuration uses only permissively licensed code and model weights.

These FPS and latency figures are targets. M0 measures them and updates this file if needed.
