# 50 Roadmap

Durations are estimates for one engineer.

## M0 Spikes (1 week)

- Measure MediaPipe Face Landmarker FPS and latency with 1 to 4 faces on the reference laptop.
- Confirm detection across 0.5 m to 2.0 m (D2).
- Pin the landmark index table and frame conversion (AC-PER-05).
- Run the threshold tuning study (SPECS/40).

Exit: measurements and tuned values recorded in SPECS/60 and SPECS/18; NFR targets confirmed or revised.

## M1 Walking skeleton (1 week)

- Scaffold the repo per CLAUDE.md section 5. uv, ruff, pyright, pytest, CI.
- `Clock`, `types`, `events`, `config` with `test_config_matches_spec`.
- `ReplaySource` + `ReplayPerception`, tracker, `GeometricScorer`, 1-euro filter, state machine.
- One head driven end to end (procedural Three.js head), webcam and replay sources.

Exit: AC-CAP-01, AC-CAP-04, AC-TRK-01 to 04, AC-ATT-01 to 07, AC-SM-01 to 09, AC-SYS-04 pass. CI green.

## M2 Demo MVP (2 weeks)

- Three zones with ownership hysteresis (D3).
- Head policy, targeting (yaw + pitch, D1), motion profile.
- WebSocket bridge, three heads, debug overlay, metrics.
- Golden tests and integration tests on recorded clips.
- Serial driver stub with contract tests.

Exit: all AC except AC-SYS-03 pass. Internal dry run of the demo.

## M3 Polish (1 to 2 weeks)

- Mannequin GLB heads, idle behaviour, tuned timing and scales.
- `lookaway bench`, fallback demo video, signage.

Exit: AC-SYS-01 and AC-SYS-03 pass. Demo for Prof. Hong.

## Later (out of current scope)

- **M4 One physical head.** Pan/tilt servos through `SerialHeadDriver`; joint calibration; safety limits; measured camera-to-motion latency. Head AC suite reruns against the real driver.
- **M5 Three-camera rig.** Three 120° cameras with intrinsic and fisheye calibration, extrinsics at 0°, 120°, 240°, `CameraZoneMap` with the overlap ownership rule (D3), three physical heads, yaw/pitch scales set to 1.0.
- **M6 Installation hardening.** 8-hour soak (NFR-ROB-04), watchdog and auto-restart, venue lighting profile, privacy review, maintenance guide.
