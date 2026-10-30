"""Cross-module value types. Implements SPECS/20."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

Vec2 = tuple[float, float]
Box = tuple[float, float, float, float]
Mat3 = tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]


@dataclass(frozen=True, slots=True)
class Intrinsics:
    fx: float
    fy: float
    cx: float
    cy: float
    dist: tuple[float, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceInfo:
    source_id: str
    width: int
    height: int
    fps_nominal: float
    intrinsics: Intrinsics


@dataclass(frozen=True, slots=True)
class Frame:
    source_id: str
    index: int
    t_capture: float
    image: NDArray[np.uint8]  # HxWx3 BGR; empty array in replay


class CameraSource(Protocol):
    @property
    def info(self) -> SourceInfo: ...
    def open(self) -> None: ...
    def read(self) -> Frame | None: ...
    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class FaceObservation:
    t: float
    bbox_px: Box
    centroid_px: Vec2
    confidence: float
    iod_px: float
    R_cam_head: Mat3
    iris_px: tuple[Vec2, Vec2]  # (image-left eye, image-right eye)
    eye_corners_px: tuple[tuple[Vec2, Vec2], tuple[Vec2, Vec2]]
    eye_lids_px: tuple[tuple[Vec2, Vec2], tuple[Vec2, Vec2]]
    blink: tuple[float, float]


class FacePerception(Protocol):
    def process(self, frame: Frame) -> list[FaceObservation]: ...


@dataclass(frozen=True, slots=True)
class Track:
    id: int
    bbox_px: Box
    centroid_px: Vec2
    created_t: float
    last_seen_t: float
    hits: int
    misses: int
    confirmed: bool
    last_obs: FaceObservation | None


class Tracker(Protocol):
    def update(self, obs: list[FaceObservation], t: float) -> list[Track]: ...


class ZoneMap(Protocol):
    def assign(self, track_id: int, centroid_px: Vec2, t: float) -> int: ...
    def forget(self, track_id: int) -> None: ...
    def center_bearing(self, zone_id: int) -> float: ...
    def bearing(self, zone_id: int, centroid_px: Vec2) -> tuple[float, float]: ...


@dataclass(frozen=True, slots=True)
class AttentionSample:
    angle_to_cam_rad: float
    raw_score: float
    eyes_closed: bool
    quality: float


class AttentionScorer(Protocol):
    def score(self, obs: FaceObservation, intrinsics: Intrinsics) -> AttentionSample: ...


@dataclass(frozen=True, slots=True)
class ScoredSample:
    score: float
    eyes_closed: bool
    zone_id: int
    az_rel_rad: float
    el_rad: float


class AttentionState(Enum):
    UNKNOWN = auto()
    LOOKING = auto()
    AWAY_PENDING = auto()
    AWAY = auto()
    LOOKING_PENDING = auto()
    LOST = auto()


class HeadMode(Enum):
    IDLE = auto()
    ORIENT = auto()
    HOLD = auto()
    RETURN = auto()


@dataclass(frozen=True, slots=True)
class HeadCommand:
    head_id: int
    t: float
    yaw_rad: float
    pitch_rad: float


class HeadDriver(Protocol):
    def send(self, cmd: HeadCommand) -> None: ...
    def state(self) -> HeadCommand | None: ...
    def close(self) -> None: ...
