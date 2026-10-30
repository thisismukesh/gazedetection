# 00 Overview

## Purpose

A laptop demo of **Look Away**: three on-screen mannequin heads, each bound to one zone of a single webcam's view. When a person in a zone stops looking at the piece, that zone's head turns toward them (yaw and pitch) and follows them for a while, then returns to neutral. It repeats every time someone looks away.

The demo is built so the physical version (three outward-facing 120° cameras, three actuated 2-DOF heads) reuses all perception, attention and control logic.

## Concept mapping

| Physical piece                          | Laptop demo                                        |
|-----------------------------------------|----------------------------------------------------|
| Camera k, 120° HFOV, mounted at yaw 120°·k | Zone k: one third of the webcam frame            |
| Head k bound to camera k                | On-screen head k bound to zone k                   |
| Pan/tilt servo head                     | `SimulatedHeadDriver` -> Three.js head             |
| "Looking at the piece"                  | Gaze ray within a cone around the camera           |
| Person seen by camera k                 | Track owned by zone k (exactly one owner, D3)      |

## Demo setup assumptions

- Laptop webcam, 1280x720, roughly 70° horizontal FOV.
- Viewers stand 0.5 m to 2.0 m away (a few feet). Three people side by side fit only at roughly 1.0 m to 1.5 m; at 1.0 m the frame is about 1.4 m wide.
- The heads are shown on a display placed directly below or around the webcam, so "turning toward the person" reads correctly. Head angles are scaled for expressiveness, not geometrically exact (D4).

## Glossary

- **Track:** a face with an ephemeral integer ID that persists across frames.
- **Zone:** one of three horizontal regions of the frame, in the audience frame. Owns tracks.
- **Attention score:** s in [0, 1], how likely the person is looking at the camera.
- **GazeLost:** event emitted when a LOOKING track becomes AWAY.
- **Audience frame:** the horizontally mirrored image, so left means the audience's left. Defined in SPECS/15.
- **Head pose (of a rendered head):** yaw and pitch in radians. Yaw positive turns the face toward the audience's right. Pitch positive tilts the face up.

## Out of scope (now)

Physical cameras, servos, sound, multiple laptops, identity recognition, far-range detection.

## Document map

| File | Content |
|---|---|
| 01 | Functional and non-functional requirements |
| 02 | Architecture, concurrency, dependency rules, licenses |
| 03 | Decision log |
| 10 to 19 | Module specs |
| 20 | Interfaces, value types, events |
| 21 | Privacy and ethics |
| 30 | Acceptance criteria |
| 40 | Test plan |
| 50 | Roadmap |
| 60 | Open questions and risks |
