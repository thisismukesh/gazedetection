"""Event types and synchronous EventBus. Implements SPECS/20 (Events, Bus semantics)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

import structlog

from lookaway.types import AttentionState, HeadMode

_log = structlog.get_logger("lookaway.events")


@dataclass(frozen=True, slots=True)
class GazeAcquired:
    t: float
    track_id: int
    zone_id: int


@dataclass(frozen=True, slots=True)
class GazeLost:
    t: float
    track_id: int
    zone_id: int
    az_rel_rad: float
    el_rad: float
    distance_m: float | None


@dataclass(frozen=True, slots=True)
class GazeRegained:
    t: float
    track_id: int
    zone_id: int


@dataclass(frozen=True, slots=True)
class TrackUpdated:
    t: float
    track_id: int
    zone_id: int
    az_rel_rad: float
    el_rad: float
    score: float
    state: AttentionState


@dataclass(frozen=True, slots=True)
class TrackLost:
    t: float
    track_id: int
    zone_id: int


@dataclass(frozen=True, slots=True)
class TrackReleased:
    """A head stops following this track (D14). ``zone_id`` is the head that lets go."""

    t: float
    track_id: int
    zone_id: int


@dataclass(frozen=True, slots=True)
class SourceStatus:
    t: float
    source_id: str
    ok: bool
    detail: str


@dataclass(frozen=True, slots=True)
class HeadModeChanged:
    t: float
    head_id: int
    mode: HeadMode
    target_track: int | None
    expression: str | None = None  # the mask emoji while in MASK (D17)


Event = (
    GazeAcquired
    | GazeLost
    | GazeRegained
    | TrackUpdated
    | TrackLost
    | TrackReleased
    | SourceStatus
    | HeadModeChanged
)


class EventBus:
    """Synchronous fan-out in publish order; one failing handler never stops the rest."""

    def __init__(self) -> None:
        self._handlers: dict[type, list[Callable[[Any], None]]] = defaultdict(list)

    def subscribe[E](self, event_type: type[E], handler: Callable[[E], None]) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: Event) -> None:
        for handler in list(self._handlers.get(type(event), ())):
            try:
                handler(event)
            except Exception:
                _log.exception("handler_failed", event_type=type(event).__name__)

    def publish_all(self, events: Iterable[Event]) -> None:
        for e in events:
            self.publish(e)
