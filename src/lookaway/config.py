"""Configuration models and loader. Implements SPECS/18 (layering, validation, hash)."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt, model_validator

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "default.toml"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Capture(_Model):
    source: str
    width: PositiveInt
    height: PositiveInt
    fps: PositiveInt
    hfov_deg: PositiveFloat
    calibration_file: str
    mirror_display: bool

    @property
    def hfov_rad(self) -> float:
        return math.radians(self.hfov_deg)


class Zones(_Model):
    count: PositiveInt
    boundaries: list[float]
    margin_px: PositiveInt
    switch_s: PositiveFloat

    @model_validator(mode="after")
    def _check(self) -> Zones:
        b = self.boundaries
        if len(b) != self.count - 1:
            raise ValueError("zones.boundaries must have length zones.count - 1")
        if any(not 0.0 < x < 1.0 for x in b) or any(b[i] >= b[i + 1] for i in range(len(b) - 1)):
            raise ValueError("zones.boundaries must be strictly increasing inside (0, 1)")
        return self


class Perception(_Model):
    backend: str
    model_path: str
    max_faces: PositiveInt
    min_detection_confidence: float = Field(ge=0.0, le=1.0)
    min_presence_confidence: float = Field(ge=0.0, le=1.0)
    min_tracking_confidence: float = Field(ge=0.0, le=1.0)


class Tracking(_Model):
    iou_gate: float = Field(gt=0.0, le=1.0)
    high_conf: float = Field(ge=0.0, le=1.0)
    confirm_hits: PositiveInt
    max_coast_s: PositiveFloat


class OneEuro(_Model):
    min_cutoff: PositiveFloat
    beta: float = Field(ge=0.0)
    d_cutoff: PositiveFloat


class Attention(_Model):
    scorer: str
    ipd_m: PositiveFloat
    k_yaw_deg: PositiveFloat
    k_pitch_deg: PositiveFloat
    eye_weight_iod_min_px: PositiveFloat
    eye_weight_iod_full_px: PositiveFloat
    look_target_pitch_deg: float
    cone_deg: PositiveFloat
    softness_deg: PositiveFloat
    blink_thresh: float = Field(ge=0.0, le=1.0)
    t_on: float = Field(ge=0.0, le=1.0)
    t_off: float = Field(ge=0.0, le=1.0)
    away_confirm_s: PositiveFloat
    look_confirm_s: PositiveFloat
    retrigger_cooldown_s: PositiveFloat
    missing_as_away_s: PositiveFloat
    track_timeout_s: PositiveFloat
    trigger_on_first_seen_away: bool
    max_triggers_per_min: PositiveInt
    one_euro: OneEuro

    @model_validator(mode="after")
    def _check(self) -> Attention:
        if not self.t_off < self.t_on:
            raise ValueError("attention.t_off must be < attention.t_on")
        if not self.eye_weight_iod_min_px < self.eye_weight_iod_full_px:
            raise ValueError("attention.eye_weight_iod_min_px must be < eye_weight_iod_full_px")
        return self

    @property
    def cone_rad(self) -> float:
        return math.radians(self.cone_deg)

    @property
    def look_target_pitch_rad(self) -> float:
        return math.radians(self.look_target_pitch_deg)

    @property
    def softness_rad(self) -> float:
        return math.radians(self.softness_deg)

    @property
    def k_yaw_rad(self) -> float:
        return math.radians(self.k_yaw_deg)

    @property
    def k_pitch_rad(self) -> float:
        return math.radians(self.k_pitch_deg)


class Limits(_Model):
    yaw_deg: PositiveFloat
    pitch_deg: PositiveFloat
    vel_deg_s: PositiveFloat
    acc_deg_s2: PositiveFloat

    @property
    def yaw_rad(self) -> float:
        return math.radians(self.yaw_deg)

    @property
    def pitch_rad(self) -> float:
        return math.radians(self.pitch_deg)

    @property
    def vel_rad_s(self) -> float:
        return math.radians(self.vel_deg_s)

    @property
    def acc_rad_s2(self) -> float:
        return math.radians(self.acc_deg_s2)


class Control(_Model):
    rate_hz: PositiveInt
    yaw_scale: PositiveFloat
    pitch_scale: PositiveFloat
    pitch_offset_deg: float
    arrive_tol_deg: PositiveFloat
    hold_s: PositiveFloat
    min_hold_s: PositiveFloat
    next_target_ttl_s: PositiveFloat
    release_on_regain: bool
    regain_release_s: PositiveFloat
    idle_sway_deg: float = Field(ge=0.0)
    idle_sway_period_s: PositiveFloat
    wander_yaw_deg: float = Field(ge=0.0)
    wander_pitch_deg: float = Field(ge=0.0)
    wander_min_dwell_s: PositiveFloat
    wander_max_dwell_s: PositiveFloat
    wander_looking_ttl_s: PositiveFloat
    target_one_euro: OneEuro
    limits: Limits

    @model_validator(mode="after")
    def _check(self) -> Control:
        if self.wander_min_dwell_s > self.wander_max_dwell_s:
            raise ValueError("control.wander_min_dwell_s must be <= wander_max_dwell_s")
        return self


class Render(_Model):
    host: str
    port: PositiveInt
    rate_hz: PositiveInt
    debug_rate_hz: PositiveInt
    allow_lan: bool


class Observability(_Model):
    log_level: str
    overlay: bool
    metrics_window_s: PositiveFloat


class Privacy(_Model):
    mode: Literal["installation", "development"]
    allow_restricted_models: bool
    restricted_license_ref: str

    @model_validator(mode="after")
    def _check(self) -> Privacy:
        if (
            self.mode == "installation"
            and self.allow_restricted_models
            and not self.restricted_license_ref
        ):
            raise ValueError("installation mode needs privacy.restricted_license_ref")
        return self


class Config(_Model):
    capture: Capture
    zones: Zones
    perception: Perception
    tracking: Tracking
    attention: Attention
    control: Control
    render: Render
    observability: Observability
    privacy: Privacy


def _merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)  # pyright: ignore[reportUnknownArgumentType]
        else:
            out[k] = v
    return out


def _env_overrides() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, raw in os.environ.items():
        if not key.startswith("LOOKAWAY__"):
            continue
        parts = [p.lower() for p in key.split("__")[1:]]
        try:
            value: Any = json.loads(raw)
        except ValueError:
            value = raw
        node = out
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = value
    return out


def load_config(path: Path | str | None = None, source: str | None = None) -> Config:
    """Layer default.toml, --config file, LOOKAWAY__ env vars, then CLI --source."""
    data = tomllib.loads(DEFAULT_PATH.read_text())
    if path is not None:
        data = _merge(data, tomllib.loads(Path(path).read_text()))
    data = _merge(data, _env_overrides())
    if source is not None:
        data = _merge(data, {"capture": {"source": source}})
    return Config.model_validate(data)


def config_sha256(cfg: Config) -> str:
    """Hash of the resolved config, logged at startup."""
    return hashlib.sha256(cfg.model_dump_json().encode()).hexdigest()
