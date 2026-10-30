"""Shared driver helpers. HeadDriver protocol lives in lookaway.types (SPECS/20)."""

from __future__ import annotations

from lookaway.types import HeadCommand


class LastCommandMixin:
    """Remembers the last command for ``state()``."""

    def __init__(self) -> None:
        self._last: HeadCommand | None = None

    def state(self) -> HeadCommand | None:
        return self._last
