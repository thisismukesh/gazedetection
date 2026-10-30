"""Serial servo driver stub, tested against a fake port. Implements SPECS/16 Drivers (FR-15).

Writes ASCII lines ``H<id> <yaw_us> <pitch_us>\\n``, at most ``rate_hz`` per second. Not used by
the demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from lookaway.control.drivers.base import LastCommandMixin
from lookaway.types import HeadCommand


class SerialPort(Protocol):
    def write(self, data: bytes) -> int: ...
    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class JointCal:
    center_us: float
    us_per_rad: float
    sign: int
    min_us: float
    max_us: float

    def to_us(self, rad: float) -> int:
        us = self.center_us + self.sign * self.us_per_rad * rad
        return round(max(self.min_us, min(self.max_us, us)))


class SerialHeadDriver(LastCommandMixin):
    def __init__(self, port: SerialPort, yaw: JointCal, pitch: JointCal, rate_hz: float) -> None:
        super().__init__()
        self._port = port
        self._yaw = yaw
        self._pitch = pitch
        self._min_gap = 1.0 / rate_hz
        self._last_write_t: float | None = None

    def send(self, cmd: HeadCommand) -> None:
        self._last = cmd
        if self._last_write_t is not None and cmd.t - self._last_write_t < self._min_gap - 1e-9:
            return
        self._last_write_t = cmd.t
        line = f"H{cmd.head_id} {self._yaw.to_us(cmd.yaw_rad)} {self._pitch.to_us(cmd.pitch_rad)}\n"
        self._port.write(line.encode("ascii"))

    def close(self) -> None:
        self._port.close()
