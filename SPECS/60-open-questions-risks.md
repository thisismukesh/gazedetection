# 60 Open Questions and Risks

## Resolved (2026-10-29)

- Head motion: turn toward the person with yaw and pitch, no roll. See D1.
- Viewing distance: a few feet; envelope 0.5 m to 2.0 m. See D2.
- A person seen by two cameras triggers just one head. See D3.
- Which heads react (former Q7): heads are assigned to people, not zones; a lone person gets all three (D6, D14).
- People who keep looking get acknowledged (former Q2): their heads wander (D7).

## Open questions (owner: artist + RoMeLa)

- **Q1** If several people in one zone look away within a few seconds, is "latest wins after `min_hold_s`" the right behaviour, or should the head prefer the closest person?
- **Q3** Will the piece be exhibited commercially or sold? This decides whether any non-commercially-licensed model or dataset may be used at all.
- **Q4** Actuators for the physical piece: hobby servos through a microcontroller, smart servos on a bus, or the lab's ROS 2 stack? Affects M4.
- **Q5** Exact overlap ownership rule for the three-camera rig (proposed: closest optical axis, with hysteresis). Cameras sit on a triangle, not one point, so there are near-field blind wedges between them.
- **Q6** Camera height and pitch range for children and wheelchair users.
- **Q8** With defaults, a track queued during HOLD is older than `next_target_ttl_s` (1.5 s) by the time `hold_s` (2.0 s) ends, so the queue only helps after an early release (regain). Should the TTL be measured from the last `TrackUpdated` instead of from `GazeLost`?

## Measurements to record (M0)

Measured so far (MacBook Pro, Apple Silicon, 1280x720 webcam, one face, `lookaway bench`): 64 fps processing throughput, capture-to-score p50 16.0 ms, p95 17.0 ms (targets: 24 fps, 80 ms). The tuning study and distance clips still need participants.

| Item | Value | Date |
|---|---|---|
| FPS at 1 / 2 / 4 faces | | |
| Perception latency p50 / p95 | | |
| Detection rate at 0.5 / 1.0 / 1.5 / 2.0 m | | |
| Tuned `cone_deg`, `look_target_pitch_deg`, `eye_radius_ratio` | | |
| Tuned `t_on`, `t_off`, `away_confirm_s` | | |
| False triggers per minute at chosen point | | |

## Risks

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | False triggers from glasses, lighting, or downward phone gaze ambiguity | Medium | Piece looks erratic | Hysteresis, cooldown, rate limit, tuning study |
| R2 | Eyes-only glances missed | Medium | Missed triggers | Iris term stays weighted across the D2 envelope; tune gains in M0 |
| R3 | Three people cannot fit side by side at close range | High at under 1 m | Weak multi-person demo | Floor marks at about 1.2 m; overlay shows zones |
| R4 | Non-commercial model licenses | Medium | Legal | Default path permissive only (NFR-LIC-01, P7) |
| R5 | On-screen head direction looks wrong if the display is far from the camera | Medium | Concept unclear | Place display under the camera; tune scales (D4) |
| R6 | 120° lens distortion degrades landmarks at frame edges | High in M5 | Accuracy | Calibrate and undistort; edge-case tests |
| R7 | CPU load with three cameras | Medium in M5 | FPS drop | One process per camera, lower resolution, accelerated runtimes |
| R8 | Visitor privacy concerns | Medium | Reputation | SPECS/21, signage, no storage |
| R9 | Demo-day camera or lighting failure | Medium | Demo fails | Fallback replay source (D9) |
| R10 | Printed faces, masks or screens in view are detected as people | High in decorated rooms | A head stares at a poster | Liveness gate (D12) |
