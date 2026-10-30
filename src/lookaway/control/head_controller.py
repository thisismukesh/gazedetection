"""One head: bus events -> policy -> targeting -> motion -> driver. Implements SPECS/16.

AC-HEAD-01..07. Publishes HeadModeChanged on mode or target changes.
"""

from __future__ import annotations

from lookaway.attention.one_euro import OneEuroFilter
from lookaway.control.motion import AxisMotion
from lookaway.control.policy import HeadPolicy, PolicyOutput
from lookaway.control.targeting import TargetParams, target_pose
from lookaway.events import (
    EventBus,
    GazeLost,
    GazeRegained,
    HeadModeChanged,
    TrackLost,
    TrackUpdated,
)
from lookaway.types import HeadCommand, HeadDriver, HeadMode


class HeadController:
    def __init__(
        self,
        head_id: int,
        policy: HeadPolicy,
        targeting: TargetParams,
        motion_limits: tuple[float, float, float, float],
        arrive_tol_rad: float,
        rate_hz: float,
        target_filter: tuple[float, float, float],
        driver: HeadDriver,
        bus: EventBus,
    ) -> None:
        yaw_lim, pitch_lim, v_max, a_max = motion_limits
        self._id = head_id
        self._policy = policy
        self._tp = targeting
        self._yaw = AxisMotion(yaw_lim, v_max, a_max)
        self._pitch = AxisMotion(pitch_lim, v_max, a_max)
        self._tol = arrive_tol_rad
        self._dt = 1.0 / rate_hz
        self._driver = driver
        self._bus = bus
        self._f_az = OneEuroFilter(*target_filter)
        self._f_el = OneEuroFilter(*target_filter)
        self._mode = HeadMode.IDLE
        self._track: int | None = None
        for et in (GazeLost, GazeRegained, TrackUpdated, TrackLost):
            bus.subscribe(et, policy.on_event)

    @property
    def mode(self) -> HeadMode:
        return self._mode

    def _pose(self, t: float, out: PolicyOutput) -> tuple[float, float]:
        if out.target_track is None:
            return out.sway_yaw_rad, 0.0
        if out.target_track != self._track:
            self._f_az.reset()
            self._f_el.reset()
        az = self._f_az.filter(t, out.az_rel_rad)
        el = self._f_el.filter(t, out.el_rad)
        return target_pose(self._tp, az, el)

    def _arrived(self, pose: tuple[float, float]) -> bool:
        return (
            abs(pose[0] - self._yaw.pos) <= self._tol
            and abs(pose[1] - self._pitch.pos) <= self._tol
        )

    def tick(self, t: float) -> HeadCommand:
        out = self._policy.output(t)
        arrived = self._arrived(self._preview(out))
        out = self._policy.tick(t, arrived)
        pose = self._pose(t, out)
        self._announce(t, out)
        self._track = out.target_track
        cmd = HeadCommand(
            self._id, t, self._yaw.step(pose[0], self._dt), self._pitch.step(pose[1], self._dt)
        )
        self._driver.send(cmd)
        return cmd

    def _preview(self, out: PolicyOutput) -> tuple[float, float]:
        """Target pose for arrival checks, without advancing the target filters."""
        if out.target_track is None:
            return out.sway_yaw_rad, 0.0
        return target_pose(self._tp, out.az_rel_rad, out.el_rad)

    def _announce(self, t: float, out: PolicyOutput) -> None:
        if out.mode is not self._mode or out.target_track != self._track:
            self._mode = out.mode
            self._bus.publish(HeadModeChanged(t, self._id, out.mode, out.target_track))
