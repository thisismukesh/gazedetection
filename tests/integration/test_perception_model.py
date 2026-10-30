"""Needs the model file (uv run lookaway fetch-models). AC-PER-03 without any face fixture."""

from __future__ import annotations

import numpy as np
import pytest

from lookaway.config import load_config
from lookaway.models import FACE_LANDMARKER_SHA256, sha256_file
from lookaway.perception.mediapipe_face import MediaPipeFacePerception, resolve_model_path
from lookaway.types import Frame

pytestmark = pytest.mark.integration


def test_AC_PER_03_empty_scene_has_no_observations() -> None:
    cfg = load_config()
    model = resolve_model_path(cfg.perception.model_path)
    if not model.exists() or sha256_file(model) != FACE_LANDMARKER_SHA256:
        pytest.skip("run `uv run lookaway fetch-models` first")
    p = MediaPipeFacePerception(cfg.perception)
    blank = np.full((720, 1280, 3), 40, np.uint8)
    for i in range(5):
        assert p.process(Frame("blank", i, i / 30, blank)) == []
