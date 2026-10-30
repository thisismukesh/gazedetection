"""Builds control params from the validated config."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from lookaway.config import Control
from lookaway.control.head_controller import HeadController
from lookaway.control.policy import HeadPolicy, PolicyParams
from lookaway.control.targeting import TargetParams
from lookaway.control.wander import Wander, WanderParams
from lookaway.events import EventBus
from lookaway.types import HeadDriver


@dataclass(frozen=True, slots=True)
class MotionLimits:
    yaw_rad: float
    pitch_rad: float
    vel_rad_s: float
    acc_rad_s2: float


def limits_from_config(c: Control) -> MotionLimits:
    return MotionLimits(
        c.limits.yaw_rad, c.limits.pitch_rad, c.limits.vel_rad_s, c.limits.acc_rad_s2
    )


def target_params_from_config(c: Control) -> TargetParams:
    return TargetParams(
        c.yaw_scale,
        c.pitch_scale,
        math.radians(c.pitch_offset_deg),
        c.limits.yaw_rad,
        c.limits.pitch_rad,
    )


def policy_params_from_config(c: Control, zone_id: int) -> PolicyParams:
    return PolicyParams(
        zone_id=zone_id,
        hold_s=c.hold_s,
        min_hold_s=c.min_hold_s,
        next_target_ttl_s=c.next_target_ttl_s,
        release_on_regain=c.release_on_regain,
        regain_release_s=c.regain_release_s,
        idle_sway_rad=math.radians(c.idle_sway_deg),
        idle_sway_period_s=c.idle_sway_period_s,
        wander_looking_ttl_s=c.wander_looking_ttl_s,
    )


def build_head_controller(
    c: Control,
    head_id: int,
    driver: HeadDriver,
    bus: EventBus,
    rng: random.Random | None = None,
) -> HeadController:
    """One controller per head; head k serves zone k."""
    lim = limits_from_config(c)
    e = c.target_one_euro
    return HeadController(
        head_id,
        HeadPolicy(policy_params_from_config(c, head_id)),
        target_params_from_config(c),
        (lim.yaw_rad, lim.pitch_rad, lim.vel_rad_s, lim.acc_rad_s2),
        math.radians(c.arrive_tol_deg),
        float(c.rate_hz),
        (e.min_cutoff, e.beta, e.d_cutoff),
        driver,
        bus,
        Wander(
            WanderParams(
                math.radians(c.wander_yaw_deg),
                math.radians(c.wander_pitch_deg),
                c.wander_min_dwell_s,
                c.wander_max_dwell_s,
            ),
            rng or random.Random(),
        ),
    )
