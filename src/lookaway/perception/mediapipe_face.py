# pyright: basic
# MediaPipe ships no type stubs, so this one module opts out of strict checking.
"""MediaPipe Face Landmarker backend. Implements SPECS/11 Default. AC-PER-01..03."""

from __future__ import annotations

from pathlib import Path

import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

from lookaway.config import Perception
from lookaway.perception.landmarks import observation_from_landmarks
from lookaway.types import FaceObservation, Frame

ROOT = Path(__file__).resolve().parents[3]


def resolve_model_path(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else ROOT / path


def _blink_scores(categories) -> tuple[float, float]:  # noqa: ANN001
    by_name = {c.category_name: c.score for c in categories}
    # MediaPipe names blendshapes from the subject's view: "Left" is the image-right eye.
    return float(by_name.get("eyeBlinkRight", 0.0)), float(by_name.get("eyeBlinkLeft", 0.0))


class MediaPipeFacePerception:
    def __init__(self, cfg: Perception) -> None:
        path = resolve_model_path(cfg.model_path)
        if not path.exists():
            raise FileNotFoundError(f"{path} missing. Run: uv run lookaway fetch-models")
        options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(path)),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=cfg.max_faces,
            min_face_detection_confidence=cfg.min_detection_confidence,
            min_face_presence_confidence=cfg.min_presence_confidence,
            min_tracking_confidence=cfg.min_tracking_confidence,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
        )
        self._lm = vision.FaceLandmarker.create_from_options(options)
        self._last_ms = -1

    def process(self, frame: Frame) -> list[FaceObservation]:
        h, w = frame.image.shape[:2]
        rgb = np.ascontiguousarray(frame.image[:, :, ::-1])
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        ms = max(int(frame.t_capture * 1000), self._last_ms + 1)
        self._last_ms = ms
        res = self._lm.detect_for_video(image, ms)
        out: list[FaceObservation] = []
        for i, lms in enumerate(res.face_landmarks):
            pts = np.array([[p.x, p.y] for p in lms], dtype=np.float64)
            blink = _blink_scores(res.face_blendshapes[i])
            matrix = np.asarray(res.facial_transformation_matrixes[i], dtype=np.float64)
            out.append(observation_from_landmarks(pts, blink, matrix, frame.t_capture, w, h))
        return out

    def close(self) -> None:
        self._lm.close()
