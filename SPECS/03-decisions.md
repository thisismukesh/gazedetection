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
