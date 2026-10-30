"""Builds module params from the validated config (keeps pure modules free of pydantic)."""

from __future__ import annotations

from lookaway.attention.geometric import GeometricScorer, GeoParams
from lookaway.attention.state_machine import SMParams
from lookaway.config import Attention


def sm_params_from_config(a: Attention) -> SMParams:
    return SMParams(
        t_on=a.t_on,
        t_off=a.t_off,
        away_confirm_s=a.away_confirm_s,
        look_confirm_s=a.look_confirm_s,
        retrigger_cooldown_s=a.retrigger_cooldown_s,
        missing_as_away_s=a.missing_as_away_s,
        track_timeout_s=a.track_timeout_s,
        trigger_on_first_seen_away=a.trigger_on_first_seen_away,
        max_triggers_per_min=a.max_triggers_per_min,
    )


def scorer_from_config(a: Attention) -> GeometricScorer:
    return GeometricScorer(
        GeoParams(
            ipd_m=a.ipd_m,
            eye_radius_ratio=a.eye_radius_ratio,
            eye_weight_iod_min_px=a.eye_weight_iod_min_px,
            eye_weight_iod_full_px=a.eye_weight_iod_full_px,
            look_target_pitch_rad=a.look_target_pitch_rad,
            cone_rad=a.cone_rad,
            softness_rad=a.softness_rad,
            blink_thresh=a.blink_thresh,
        )
    )
