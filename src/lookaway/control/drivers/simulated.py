"""Simulated and recording drivers. Implements SPECS/16 Drivers."""

from __future__ import annotations

from collections.abc import Callable

from lookaway.control.drivers.base import LastCommandMixin
from lookaway.types import HeadCommand


class SimulatedHeadDriver(LastCommandMixin):
    """Forwards commands to the render bridge (a callable sink)."""

    def __init__(self, sink: Callable[[HeadCommand], None]) -> None:
        super().__init__()
        self._sink = sink

    def send(self, cmd: HeadCommand) -> None:
        self._last = cmd
        self._sink(cmd)

    def close(self) -> None:
        return None


class RecordingHeadDriver(LastCommandMixin):
    """Stores every command (tests)."""

    def __init__(self) -> None:
        super().__init__()
        self.commands: list[HeadCommand] = []

    def send(self, cmd: HeadCommand) -> None:
        self._last = cmd
        self.commands.append(cmd)

    def close(self) -> None:
        return None
