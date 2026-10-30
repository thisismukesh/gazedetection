# 30 Acceptance Criteria

Format: Given / When / Then. Test names use the ID, e.g. `test_AC_SM_03_blink_does_not_trigger`. Numbers refer to the defaults in SPECS/18 unless a criterion overrides them. "(property)" means a Hypothesis test.

## Capture

- **AC-CAP-01** Given a `VideoFileSource` with `realtime=False`, when read repeatedly, then frames arrive in index order with non-decreasing `t_capture`, and `read()` returns `None` at the end.
- **AC-CAP-02** Given a consumer slower than capture, when it calls `take_latest()`, then it gets the newest frame and `frames_dropped` increases by the number of overwritten frames.
- **AC-CAP-03** Given `read()` starts failing, when the source is polled with a `FakeClock`, then `SourceStatus(ok=False)` is published once and retries happen at 0.5, 1, 2, 5 s offsets.
- **AC-CAP-04** Given no calibration file, width 1280 and `hfov_deg = 70`, then `fx = fy = 914.0 ± 0.5`, `cx = 640`, `cy = 360`.

## Perception

- **AC-PER-01** Given a frontal-face fixture image, when processed, then exactly one observation with `iod_px > 0` and both blink values below 0.5.
- **AC-PER-02** Given a fixture with three faces, when processed with `max_faces = 6`, then three observations with bboxes inside the frame.
- **AC-PER-03** Given an empty-scene fixture, when processed, then no observations.
- **AC-PER-04** (integration) Given consented clips of a frontal face at 0.5, 1.0, 1.5 and 2.0 m, when processed, then at least 95% of frames in each clip yield exactly one observation (NFR-ROB-03, D2).
- **AC-PER-05** Given a frontal fixture of a person looking into the camera, when processed, then the head forward axis derived per SPECS/13 step 2 is within 15° of the face-to-camera direction, and the iris and eye-corner index table in SPECS/11 puts each iris between its own eye's corners.

## Tracking

- **AC-TRK-01** Given two faces moving at most 5% of frame width per frame, when tracked for 100 frames, then each keeps a single ID.
- **AC-TRK-02** Given a face missing for 0.5 s, when it reappears near its predicted position, then it keeps its ID.
- **AC-TRK-03** Given a face missing longer than `max_coast_s`, when it reappears, then it gets a new ID never used before in the run.
- **AC-TRK-04** Given a new face seen for fewer than `confirm_hits` frames, then the track is unconfirmed and produces no attention events.

- **AC-TRK-05** (D12) Given a face that never blinks and never moves (a poster), when it appears to look at the camera and then away, then no attention or head events are produced and the camera view shows it as static.
- **AC-TRK-06** (D12) Given a track that blinks, or whose centre moves at least `liveness_move_px`, then it becomes live and behaves normally from then on; it stays live if it later holds still.

## Attention scoring

- **AC-ATT-01** Given a synthetic frontal face at the image centre looking at the camera, then `angle_to_cam < 5°` and `raw_score > 0.9`.
- **AC-ATT-02** Given a synthetic face at the image centre with head yaw 40° and centred irises, then `raw_score < 0.1`.
- **AC-ATT-03** Given a synthetic face near the image edge whose head is turned to face the camera, then `raw_score > 0.8`.
- **AC-ATT-04** Given a frontal head at the image centre, `iod_px >= 45`, eyes open, and an iris offset equal to 25° of eye yaw under the configured gains, then `raw_score < 0.2`.
- **AC-ATT-05** Given `iod_px <= 15`, then the eye term has zero weight and the score equals the head-pose-only score.
- **AC-ATT-06** Given both blink values at 0.8, then `eyes_closed = true`.
- **AC-ATT-07** (property) For fixed position and eye state, `raw_score` is non-increasing as head yaw moves away from facing the camera.

## Attention state machine

- **AC-SM-01** Given a LOOKING track, when the score stays below `t_off` for at least `away_confirm_s`, then exactly one `GazeLost`.
- **AC-SM-02** Given a LOOKING track, when the score dips below `t_off` for less than `away_confirm_s` and recovers above `t_on`, then no event other than `TrackUpdated`.
- **AC-SM-03** Given a LOOKING track, when `eyes_closed` is true for 300 ms with low scores, then no `GazeLost`.
- **AC-SM-04** Given an AWAY track, when it looks back for at least `look_confirm_s` and then away again after the cooldown, then `GazeRegained` followed by a second `GazeLost`.
- **AC-SM-05** Given two LOOKING to AWAY transitions 0.5 s apart, then only the first emits `GazeLost` and `suppressed_triggers` increments.
- **AC-SM-06** Given a track first seen looking away with `trigger_on_first_seen_away = false`, then no `GazeLost`.
- **AC-SM-07** Given a LOOKING track unobserved for `missing_as_away_s`, then `GazeLost` with its last bearing and zone; after `track_timeout_s`, `TrackLost`; afterwards nothing.
- **AC-SM-08** (property) Invariants I1 to I6 of SPECS/14 hold for arbitrary sample sequences.
- **AC-SM-09** Given 13 cooldown-respecting LOOKING to AWAY cycles within 60 s, then exactly 12 `GazeLost` events.

## Zones

- **AC-ZONE-01** Given default boundaries, when a new track's centroid is at audience-frame x = W/6, then it is owned by zone 0.
- **AC-ZONE-02** Given a track oscillating ±10 px across a boundary for 3 s, then its zone never changes.
- **AC-ZONE-03** Given a track that crosses a boundary by more than `margin_px` and stays for at least `switch_s`, then its zone changes exactly once.
- **AC-ZONE-04** (property) `az_rad` is strictly decreasing in raw pixel x, equals 0 at `cx`, and pixel to bearing to pixel round-trips within 1e-6 px.
- **AC-ZONE-05** (property, D3) For any sequence of track positions, every confirmed track has exactly one owning zone at every step. ("Every `GazeLost` is handled by exactly one head" moved to AC-ASSIGN-06 under D6.)

## Head controller

- **AC-HEAD-01** Given head 1 IDLE, when `GazeLost` arrives for zone 1 with `az_rel = +5°`, `el = 0°`, then head 1 enters ORIENT and reaches yaw 20° ± 2° and pitch 0° ± 2° within 0.6 s.
- **AC-HEAD-02** Given head 1 IDLE, when `GazeLost` arrives for zone 1 with `az_rel = 0°`, `el = +5°`, then pitch reaches 10° ± 2° within 0.6 s (D1).
- **AC-HEAD-03** Given head 1 in HOLD for 0.3 s, when `GazeLost` for another track in zone 1 arrives, then the target does not change and the new track is queued.
- **AC-HEAD-04** Given head 1 in HOLD, when `hold_s` elapses with no queued target, then head 1 is back at neutral within 1.0 s.
- **AC-HEAD-05** Given `GazeLost` for zone 0, then heads 1 and 2 do not change mode.
- **AC-HEAD-06** Given head 1 holding track 7, when `TrackUpdated` shows track 7 owned by zone 2, then head 1 enters RETURN and head 2 does not change mode.
- **AC-HEAD-07** Given head 1 holding a target whose `az_rel` moves from +2° to +6° over 1 s, then within 0.5 s after the move ends head 1's yaw is 24° ± 3°.
- **AC-HEAD-08** (property) For any event sequence, every `HeadCommand` satisfies the position, velocity and acceleration limits within 1e-6 rad tolerance.

- **AC-HEAD-09** (D7) Given head 1 IDLE and its person looking (recent LOOKING `TrackUpdated`), then the policy output has `wander = True` and the commanded yaw and pitch stay within `wander_*` limits while changing target over time. When the updates stop for `wander_looking_ttl_s`, then `wander = False`.
- **AC-HEAD-10** (D7) Given head 1 in HOLD, when `TrackUpdated` with state AWAY keeps arriving for longer than `hold_s`, then the head stays in HOLD; `hold_s` after the last one it leaves HOLD.

## Head assignment (D6)

- **AC-ASSIGN-01** Given one person in zone 1, then head 1 is assigned and their events reach head 1 with `zone_id = 1`.
- **AC-ASSIGN-02** Given two people in zone 1, then the second gets the nearest free head and their events carry that head's id.
- **AC-ASSIGN-03** Given three people in one zone, then three distinct heads are assigned. A fourth person gets no head until a `TrackLost` frees one.
- **AC-ASSIGN-04** Given an assigned person who moves into another zone, then they keep their head.
- **AC-ASSIGN-05** Bearings are re-referenced to the assigned head's zone centre.
- **AC-ASSIGN-06** (property) For any event sequence, every `GazeLost` yields at most one retargeted `GazeLost`, no two live tracks share a head, and every retargeted event names a valid head.

## Renderer

- **AC-REN-01** Given a client connects, then its first message is `snapshot`, before any `head_state`.
- **AC-REN-02** Given the client disconnects mid-run, then the perception loop keeps its frame rate and no exception escapes.
- **AC-REN-03** Given `web/pose.js`, when yaw = 0.5 and pitch = 0.3, then `rotation.y = 0.5`, `rotation.x = -0.3`, `rotation.order = "YXZ"` (`node --test web/`).

- **AC-REN-04** Given `render.camera_view = true` and a connected client, then binary JPEG messages arrive after the `snapshot`, at most `camera_view_fps` per second, and none are sent when no client is connected.
- **AC-REN-05** Given `render.camera_view = true` and `render.allow_lan = true`, then the config is rejected.
- **AC-OBS-01** Given a track with a head direction and gaze direction, then the overlay draws a head arrow, a gaze arrow and the iris points on it, and draws nothing extra for a coasting track.

## System

- **AC-SYS-01** (integration) Given labelled consented clips (single look-away, phone glance down, two people, boundary walker), when run headless, then each labelled look-away yields `GazeLost` handled by the correct head within [onset + 0.15 s, onset + 0.6 s], with at most one false trigger per minute.
- **AC-SYS-02** Given installation mode, when the pipeline runs for 60 s on a video source, then no file writes happen except log output, and no log line contains a list longer than 8 numbers.
- **AC-SYS-03** (manual/nightly) Given `lookaway bench` on the reference laptop, then NFR-PERF-01 and NFR-PERF-02 hold.
- **AC-SYS-04** Given the same landmark JSONL replayed twice with `FakeClock`, then the event sequences are identical.
