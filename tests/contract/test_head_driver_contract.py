"""Shared HeadDriver contract suite (SPECS/40 Contract). Every implementation must pass."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from lookaway.control.drivers.serial_stub import JointCal, SerialHeadDriver
from lookaway.control.drivers.simulated import RecordingHeadDriver, SimulatedHeadDriver
from lookaway.types import HeadCommand, HeadDriver


class FakePort:
    def __init__(self) -> None:
        self.data: list[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> int:
        self.data.append(data)
        return len(data)

    def close(self) -> None:
        self.closed = True


def _serial() -> HeadDriver:
    cal = JointCal(1500, 400, 1, 1000, 2000)
    return SerialHeadDriver(FakePort(), cal, cal, rate_hz=100)


FACTORIES: dict[str, Callable[[], HeadDriver]] = {
    "recording": RecordingHeadDriver,
    "simulated": lambda: SimulatedHeadDriver(lambda _c: None),
    "serial": _serial,
}


@pytest.fixture(params=sorted(FACTORIES))
def driver(request: pytest.FixtureRequest) -> HeadDriver:
    return FACTORIES[request.param]()


def test_state_is_none_before_first_command(driver: HeadDriver) -> None:
    assert driver.state() is None


def test_state_returns_last_command(driver: HeadDriver) -> None:
    driver.send(HeadCommand(1, 0.0, 0.1, 0.2))
    last = HeadCommand(1, 0.01, 0.3, -0.1)
    driver.send(last)
    assert driver.state() == last


def test_close_is_safe_to_call_twice(driver: HeadDriver) -> None:
    driver.close()
    driver.close()


def test_serial_line_format_and_rate_limit() -> None:
    port = FakePort()
    cal = JointCal(1500, 400, 1, 1000, 2000)
    inv = JointCal(1500, 400, -1, 1000, 2000)
    d = SerialHeadDriver(port, cal, inv, rate_hz=50)
    d.send(HeadCommand(2, 0.000, 0.5, 0.5))
    d.send(HeadCommand(2, 0.005, 0.6, 0.6))  # < 1/50 s later: dropped
    d.send(HeadCommand(2, 0.020, 9.0, 9.0))  # clamped
    assert port.data == [b"H2 1700 1300\n", b"H2 2000 1000\n"]
    d.close()
    assert port.closed
