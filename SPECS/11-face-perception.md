# 11 Face Perception

## Interface

`FacePerception.process(frame: Frame) -> list[FaceObservation]` (SPECS/20).

## Default: `MediaPipeFacePerception`

Uses the MediaPipe Tasks Face Landmarker (`perception.model_path`).

Options:
- `running_mode = VIDEO`, timestamps from `frame.t_capture` converted to integer milliseconds, strictly increasing.
- `num_faces = perception.max_faces`.
- `output_face_blendshapes = True`.
- `output_facial_transformation_matrixes = True`.
- Confidence thresholds from `perception.min_*`.

MediaPipe applies its own landmark smoothing only when `num_faces = 1`. We set `num_faces > 1`, so all smoothing is ours (SPECS/13).

Per detected face, build a `FaceObservation`:

| Field | Source |
|---|---|
| `bbox_px` | min/max of the 478 landmarks in pixels |
| `centroid_px` | mean of landmarks 33, 263 (outer eye corners), 1 (nose tip) |
| `iod_px` | distance between iris centres (468, 473) |
| `iris_px` | iris centres 468 and 473 |
| `eye_corners_px` | corners (33, 133) and (362, 263) |
| `eye_lids_px` | upper/lower lids (159, 145) and (386, 374) |
| `R_cam_head` | rotation part of the facial transformation matrix, converted to the OpenCV camera frame (below) |
| `blink` | blendshapes `eyeBlinkLeft`, `eyeBlinkRight` |

All per-eye pairs are stored in (image-left eye, image-right eye) order. MediaPipe names blendshapes from the subject's point of view, so `eyeBlinkLeft` is expected to belong to the image-right eye. Which index set and which blendshape belongs to which image side is pinned by AC-PER-05, not assumed.
| `confidence` | detection/presence score when exposed, else 1.0 |

Landmark index assignments must be checked against the MediaPipe canonical model in a unit test with a frontal fixture (AC-PER-05). If the check fails, fix the table here first.

### Frame conversion

MediaPipe face geometry uses an OpenGL-style camera frame (x right, y up, camera looking down -z). The OpenCV frame is x right, y down, z forward. With `C = diag(1, -1, -1)`, `R_cv = C · R_gl · C`. The direction that means "face looking at the camera" must be pinned by AC-PER-05 using a frontal fixture rather than assumed.

## Replay: `ReplayPerception(jsonl_path)`

Reads one JSON object per frame: `{"index", "t", "faces": [<FaceObservation fields>]}` and returns the faces for the matching frame index. Used by golden tests and `lookaway replay`.

## Out of scope (D2)

No far-range detector. The interface allows adding a detector-then-landmarker implementation later if the viewing distance grows beyond 2 m.

## Acceptance

AC-PER-01 to AC-PER-05.
