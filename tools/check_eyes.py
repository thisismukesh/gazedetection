"""Optional live check of the eye term against MediaPipe's own eye blendshapes (D13).

Run: uv run python tools/check_eyes.py   (look around the screen naturally for 25 s)
Prints the correlation between our iris-based eye yaw/pitch and the blendshape gaze estimate;
both should be strongly positive. Frames stay in memory; only scalars are printed.
"""

from __future__ import annotations

import math
import time

import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

from lookaway.capture.webcam import WebcamSource
from lookaway.clock import MonotonicClock
from lookaway.config import load_config
from lookaway.perception.geometry import eye_offsets
from lookaway.perception.landmarks import observation_from_landmarks
from lookaway.perception.mediapipe_face import resolve_model_path

SECONDS = 25.0
W, H = 1280, 720


def corr(a: np.ndarray, b: np.ndarray) -> float:
    if a.std() < 1e-9 or b.std() < 1e-9:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def main() -> int:
    cfg = load_config()
    src = WebcamSource(0, W, H, 30, cfg.capture.hfov_rad, MonotonicClock())
    src.open()
    options = vision.FaceLandmarkerOptions(
        base_options=BaseOptions(
            model_asset_path=str(resolve_model_path(cfg.perception.model_path))
        ),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=True,
    )
    landmarker = vision.FaceLandmarker.create_from_options(options)
    rows: list[tuple[float, float, float, float]] = []
    end, ms = time.time() + SECONDS, 0
    while time.time() < end:
        frame = src.read()
        ms += 33
        rgb = np.ascontiguousarray(frame.image[:, :, ::-1]) if frame else None
        if rgb is None:
            continue
        res = landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ms)
        if not res.face_landmarks:
            continue
        pts = np.array([[p.x, p.y] for p in res.face_landmarks[0]])
        bl = {c.category_name: c.score for c in res.face_blendshapes[0]}
        matrix = np.asarray(res.facial_transformation_matrixes[0])
        obs = observation_from_landmarks(pts, (0.0, 0.0), matrix, 0.0, W, H)
        yaw, pitch = eye_offsets(obs, cfg.attention.eye_radius_ratio)
        # The subject's right eye is the image-left eye; "In" means toward the nose, which is
        # toward image-right for that eye and toward image-left for the other.
        bs_yaw = (
            (bl["eyeLookInRight"] - bl["eyeLookOutRight"])
            + (bl["eyeLookOutLeft"] - bl["eyeLookInLeft"])
        ) / 2
        bs_pitch = (
            (bl["eyeLookDownRight"] - bl["eyeLookUpRight"])
            + (bl["eyeLookDownLeft"] - bl["eyeLookUpLeft"])
        ) / 2
        rows.append((math.degrees(yaw), math.degrees(pitch), bs_yaw, bs_pitch))
    src.close()
    if len(rows) < 30:
        print(f"only {len(rows)} frames with a face; sit in front of the camera and retry")
        return 1
    a = np.array(rows)
    yaw_c, pitch_c = corr(a[:, 0], a[:, 2]), corr(a[:, 1], a[:, 3])
    print(f"frames {len(a)}")
    print(f"eye yaw   corr with blendshapes = {yaw_c:+.2f}  (expect strongly positive)")
    print(f"eye pitch corr with blendshapes = {pitch_c:+.2f}  (expect strongly positive)")
    ok = yaw_c > 0.5 and pitch_c > 0.5
    print("PASS" if ok else "CHECK: the eye term disagrees with MediaPipe's own gaze estimate")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
