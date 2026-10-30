# 03 Decision Log

Each decision records context, choice, and consequences. Changing one requires a new entry that supersedes it.

## D1 Head motion is yaw + pitch toward the person (2026-10-29)

**Context.** "Tilt toward" was ambiguous: a roll head-cock, or a full turn to face the person.

**Decision.** The head turns itself toward the person, adjusting horizontal (yaw) and vertical (pitch) position. No roll.

**Consequences.**
- `HeadCommand` carries `yaw_rad` and `pitch_rad` only.
- Physical heads are 2-DOF pan/tilt.
- While holding, the head keeps following the person's updated bearing.

## D2 Viewers stand a few feet away (2026-10-29)

**Context.** MediaPipe's short-range BlazeFace detector, which the Face Landmarker uses, is documented as working best within about 2 m. A longer range would need a separate detector.

**Decision.** Design envelope is 0.5 m to 2.0 m. Use the Face Landmarker as-is. No far-range detector.

**Consequences.**
- At 1280x720 and about 70° HFOV, inter-ocular distance is roughly 115 px at 0.5 m, 58 px at 1.0 m and 29 px at 2.0 m. Iris cues are usable across the whole envelope, so the eye term stays weighted in most cases.
- `FacePerception` remains an interface, so a detector stage can be added later if the venue changes.

## D3 One person triggers one head (2026-10-29)

**Context.** In the physical rig, a person near the boundary of two 120° cameras may be seen by both.

**Decision.** Just one camera, and so one head, responds to a given person. In the demo, each track is owned by exactly one zone at a time, and only that zone's head reacts.

**Consequences.**
- `ZoneMap.assign` returns exactly one zone per confirmed track, with boundary hysteresis.
- If a held target moves into another zone, the holding head releases it. The new zone's head does not react until a new `GazeLost`.
- For the physical rig, overlapping detections are resolved by a rule in `CameraZoneMap` (proposed: the camera whose optical axis is closest to the person's bearing). See SPECS/60 Q5.

## D4 Angles are scaled for expression (2026-10-29)

**Context.** A laptop webcam covers about 70°, so each zone spans about 23°. Mapping bearings 1:1 would barely move the on-screen heads.

**Decision.** Head yaw = `control.yaw_scale` x zone-relative bearing. Head pitch = `control.pitch_scale` x (elevation - `control.pitch_offset_deg`). Both clamped to limits.

**Consequences.** Head direction is exaggerated rather than geometrically exact. The physical rig sets both scales to 1.0.

## D5 Python core, browser renderer (2026-10-29)

**Context.** A browser-only build (MediaPipe JS + Three.js) is simpler to install but weaker for TDD, property testing, and the Python path to real actuators.

**Decision.** Python 3.12 core with a Three.js renderer over a localhost WebSocket.

**Consequences.** Pure logic stays dependency-free so it could be ported to TypeScript later if a kiosk build is needed.

## D6 Heads are assigned to people, not zones (2026-10-29)

**Context.** The demo has one webcam, so several people may stand in the same zone, or all three
in front of one camera. A pure zone-to-head rule leaves heads idle while one head fights over
several people. The project lead asked that each person get a head.

**Decision.** Supersedes the zone-ownership part of D3 for the laptop demo. A `HeadAssigner`
gives each confirmed person one head and keeps that pairing until the person is lost.
Preference order: the head of the person's zone, then the nearest free head (ties to the lower
id). If every head is taken, extra people are ignored until a head frees. A head only ever reacts
to its own person, so one person still triggers exactly one head. Zones remain as a bearing
reference and a first-choice hint.

**Consequences.**
- Events handed to heads are retargeted: `zone_id` becomes the assigned head id and `az_rel_rad`
  is re-referenced to that head's zone centre (`SPECS/16` Assignment).
- A person who walks into another zone keeps their head. Policy rule 6 stays as a safety net.
- The physical rig (one camera per head) still uses D3 through `CameraZoneMap`; the assigner is
  the identity mapping there.

## D7 Heads wander while watched, stare when looked away from (2026-10-29)

**Context.** Heads sat still unless triggered. The project lead wants them alive while someone is
looking at them, and fixed on the person once that person looks away.

**Decision.** In IDLE, a head whose assigned person is currently LOOKING wanders: smooth random
glances within a small yaw/pitch range with random dwell times. On `GazeLost` the head orients to
the person and stares, following them for as long as they stay away, and lingers `hold_s` after
the last away sample (or releases early on regain).

**Consequences.** New config keys `control.wander_*` (SPECS/18). `PolicyOutput.wander` flag.

## D8 Debug overlay runs on the main thread (2026-10-29)

**Context.** SPECS/02 and SPECS/19 placed the overlay in the perception thread. On macOS, AppKit
windows must be created and driven from the main thread, so OpenCV GUI calls from a worker thread
crash or hang.

**Decision.** The perception thread publishes the latest processed frame and track state into a
single slot. A main-thread asyncio task draws and shows it at about 30 Hz and polls the keys.

**Consequences.** All OpenCV GUI calls stay on one thread (the main thread). Overlay drawing is a
pure function (`draw_overlay`) and is unit-tested. The overlay shows the latest frame, which may
lag perception by up to one overlay period.

## D9 Replay loops as the fallback demo source (2026-10-29)

**Context.** A demo-day camera or lighting failure needs a fallback (SPECS/60 R9). Recording a
video of real people needs consent.

**Decision.** The fallback is a landmark replay (`--source replay:<jsonl>`), which loops in live
runs and needs no camera, model or video of anyone. Synthetic scenarios ship in
`tests/fixtures/landmarks/`. A consented video can be used the same way via `--source video:`.

## D10 Provisional look target and cone for the laptop (2026-10-29)

**Context.** The first live runs on a MacBook showed people looking at the screen sit about 17 to
31 degrees (median about 23) off the camera axis, outside the 14 degree cone, so nobody was ever
classified as looking. The heads are drawn on that screen, below the lens (SPECS/60 R5).

**Decision.** Score against a look target `attention.look_target_pitch_deg = 8` degrees below the
camera, and widen the cone to 18 degrees with softness 4. These are provisional guesses from ten
live samples; the M0 tuning study (SPECS/40) replaces them.

**Consequences.** `angle_to_cam_rad` stays the true angle to the camera; only the score uses the
offset target. The physical rig uses offset 0. A real look-away needs roughly 28 degrees or more
off the display to trigger, which is the trade-off the tuning study should settle.

## D11 Camera view in the browser, localhost only (2026-10-29)

**Context.** The project lead wants to see what the camera sees, with the head and gaze vectors
being tracked, on the same page as the heads.

**Decision.** The app can stream a small JPEG of the camera frame, with the overlay drawn on it,
to the browser over the loopback WebSocket (`render.camera_view`, on by default in the demo).
Frames are encoded in memory, sent to connected clients and dropped. They are never written to
disk or sent anywhere else. The option is refused when `render.allow_lan = true`.

**Consequences.** SPECS/21 P1 and P2 gain this exception. `render.camera_view = false` restores
the old behaviour. The camera view is a debugging and demo aid, not part of the installation.

## D12 Static faces are not people (2026-10-29)

**Context.** The first run in a real room detected a face on a poster behind the viewer (the
Landmarker finds masks and printed faces). The poster was tracked, assigned a head and stared at
whenever its apparent pose flickered.

**Decision.** A confirmed track must prove it is alive before it takes part in attention, zones or
head assignment: it must blink (either eye above `tracking.liveness_blink`) or move its face
centre by at least `tracking.liveness_move_px` in x or y since the track began. Once alive a track
stays alive. Non-live tracks are drawn greyed out as `static?` in the camera view and produce no
events.

**Consequences.** A new person's head starts reacting after their first blink or small movement
(normally well under two seconds). A truly motionless, never-blinking person is ignored until they
do either. Printed faces, masks and screens showing a still picture are ignored.

## D13 Eye angle from eyeball geometry, measured against the corner line (2026-10-29)

**Context.** Live use showed the gaze arrows disagreeing with where the eyes were looking,
especially vertically. The old term measured the iris against the eyelid midpoint (the lids move
with the eye, so the reference moves) and used a linear gain of 55 and 40 degrees per eye width,
about 2.5 times too small for a real eyeball.

**Decision.** Measure the iris against the eye-corner line in the eye's own rotated axes,
normalised by eye width on both axes, and convert with `asin(offset / eye_radius_ratio)`.
`k_yaw_deg` and `k_pitch_deg` are replaced by `attention.eye_radius_ratio` (0.40).

**Consequences.** Gaze reaches larger angles from the same iris offsets, so eye-only glances count
for more. The default is anthropometric, not tuned; the tuning study should refine it. SPECS/13
step 3 and SPECS/18 change; AC-ATT-04 still holds (25 degrees of eye yaw is scored away).

## D14 One person owns every head (2026-10-29)

**Context.** With a single viewer, two of three heads sat idle while one stared at them, and the
wander was too small to read as alive. The project lead wants all three heads on a lone viewer,
a quick snap to stare when they look away, and clearly visible random looking-about while watched.

**Decision.** Extends D6. When exactly one person has a head, that person owns all heads: each
head gets the events with its own bearing, so all three wander while the person looks and all
three stare when they look away. The moment a second person gets a head, the extra heads are
released (`TrackReleased`) and each person keeps exactly one head. When people leave and one
remains, the free heads rejoin them, staring at once if they are currently looking away.
Wander range grows to 40 degrees yaw and 14 pitch with shorter dwells. Head velocity and
acceleration limits rise to 360 deg/s and 2400 deg/s2, and `away_confirm_s` drops to 0.2.

**Consequences.** `TrackReleased` joins the event list. Exactly-one-head-per-person (D3) still holds
whenever two or more people are present; with one person all heads are theirs. The physical rig
will set the limits to what the servos allow.

## D15 Near-immediate reaction (2026-10-29)

**Context.** Live use showed too much lag between looking away and the heads reacting. Measured on
the synthetic look-away: 0.30 s to `GazeLost`, then head motion and browser smoothing on top.

**Decision.** `away_confirm_s` 0.1 (three frames at 30 fps); score filter `min_cutoff` 6 Hz,
`beta` 1.0; bearing filter `min_cutoff` 2 Hz, `beta` 0.1; head limits 540 deg/s and 4000 deg/s2;
browser smoothing time 30 ms. Detection lag drops to about 0.10 s with no extra triggers on the
blink scenario. Blinks still pause the timer; hysteresis and the cooldown still apply.

**Consequences.** More sensitive to brief glances and to landmark noise; the tuning study should
confirm the false-trigger rate stays at or below one per minute (AC-SYS-01). NFR-PERF-04 tightens
to 250 ms.

## D16 Away means stare (2026-10-30)

**Context.** Heads only reacted to the `GazeLost` transition event. A person could be marked away
(red in the camera view) while the heads ignored them: first seen already looking away, a second
look-away inside the cooldown or past the rate limit (no event by design), or a head that became
free while the person was already away.

**Decision.** Head behaviour follows the person's state, not only the transition event. A
`TrackUpdated` with state AWAY for a head's own person starts a stare exactly like `GazeLost`, and
keeps it going. A `TrackUpdated` with state LOOKING for the person being stared at releases the
head after `regain_release_s`, like `GazeRegained`. Cooldown and rate limit now only limit how
often `GazeLost` events are emitted and logged.

**Consequences.** Whenever the camera view marks a person away, their head(s) stare at them.

## D17 Masks instead of staring on a flat display (2026-10-30)

**Context.** On a 2D display a head turning "toward" a viewer does not read clearly. The project
lead wants a clearer reaction.

**Decision.** `control.behaviour` selects the reaction. `"mask"` (the laptop-demo default): while a
head's person looks at the piece the head wanders as before (D7); when the person is marked away
the head faces forward and wears a random emoji mask from `control.mask_emojis`, a new pick each
time, for at least `control.mask_min_s` and until `regain_release_s` after the person looks back.
`"stare"`: the D1/D7/D16 turn-and-stare behaviour, kept for the physical rig.

Assignment (extends D6, D14): one person owns all three heads; two or three people get one head
each. With more people than heads, the extra people wait. When a head has worn its mask for
`control.rotate_after_s` and someone is waiting, it lets go of its person (`TrackReleased`) and
takes the waiting person whose gaze was captured most recently (latest `GazeAcquired` or
`GazeRegained`) and who is looking now. The released person waits. A head never takes a person
another head holds.

**Consequences.** New `HeadMode.MASK`, an `expression` field on `HeadModeChanged` and a `mask`
field in `head_state`. The renderer draws the emoji on the head's face.
