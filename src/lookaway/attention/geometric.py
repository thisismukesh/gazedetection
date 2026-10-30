"""Geometric attention scorer. Implements SPECS/13 Default. AC-ATT-01..07."""

from __future__ import annotations

import math
from dataclasses import dataclass

from lookaway.perception import geometry as geo
from lookaway.types import AttentionSample, FaceObservation, Intrinsics


@dataclass(frozen=True, slots=True)
class GeoParams:
    ipd_m: float
    k_yaw_rad: float
    k_pitch_rad: float
    eye_weight_iod_min_px: float
    eye_weight_iod_full_px: float
    look_target_pitch_rad: float
    cone_rad: float
    softness_rad: float
    blink_thresh: float


class GeometricScorer:
    """Stateless head-pose + iris scorer; smoothing happens per track in the pipeline."""

    def __init__(self, params: GeoParams) -> None:
        self._p = params

    def score(self, obs: FaceObservation, intrinsics: Intrinsics) -> AttentionSample:
        p = self._p
        pos = geo.face_position(obs.centroid_px, obs.iod_px, intrinsics, p.ipd_m)
        span = p.eye_weight_iod_full_px - p.eye_weight_iod_min_px
        w_dist = min(1.0, max(0.0, (obs.iod_px - p.eye_weight_iod_min_px) / span))
        w_eye = w_dist * (1.0 - (obs.blink[0] + obs.blink[1]) / 2.0)
        eye_yaw, eye_pitch = geo.eye_offsets(obs, p.k_yaw_rad, p.k_pitch_rad)
        g = geo.gaze_direction(obs.R_cam_head, w_eye * eye_yaw, w_eye * eye_pitch)
        to_cam = -pos
        theta_cam = geo.angle_between(g, to_cam)
        target = geo.pitch_down(to_cam, p.look_target_pitch_rad)
        theta = geo.angle_between(g, target)
        x = (p.cone_rad - theta) / p.softness_rad
        raw = 1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, x))))
        closed = obs.blink[0] > p.blink_thresh and obs.blink[1] > p.blink_thresh
        quality = min(1.0, obs.iod_px / p.eye_weight_iod_full_px) * obs.confidence
        return AttentionSample(theta_cam, raw, closed, quality)
