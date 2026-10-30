"""Perception -> tracking -> zones -> attention -> events per frame. Implements SPECS/02."""

from __future__ import annotations

from lookaway.attention.factory import scorer_from_config, sm_params_from_config
from lookaway.attention.one_euro import OneEuroFilter
from lookaway.attention.state_machine import AttentionStateMachine, SMParams
from lookaway.config import Config
from lookaway.events import Event, EventBus
from lookaway.tracking.iou_tracker import IouTracker, TrackerParams
from lookaway.types import (
    AttentionScorer,
    AttentionState,
    FacePerception,
    Frame,
    ScoredSample,
    SourceInfo,
    Track,
    Tracker,
    ZoneMap,
)
from lookaway.zones.zone_map import SectorZoneMap


class Pipeline:
    """Owns per-track state (filter, state machine); publishes every event on the bus."""

    def __init__(
        self,
        info: SourceInfo,
        perception: FacePerception,
        tracker: Tracker,
        zones: ZoneMap,
        scorer: AttentionScorer,
        sm_params: SMParams,
        filter_args: tuple[float, float, float],
        bus: EventBus,
    ) -> None:
        self._info = info
        self._perception = perception
        self._tracker = tracker
        self._zones = zones
        self._scorer = scorer
        self._sm_params = sm_params
        self._filter_args = filter_args
        self._bus = bus
        self._machines: dict[int, AttentionStateMachine] = {}
        self._filters: dict[int, OneEuroFilter] = {}
        self._last_zone: dict[int, int] = {}

    def process(self, frame: Frame) -> list[Event]:
        t = frame.t_capture
        obs = self._perception.process(frame)
        tracks = {tr.id: tr for tr in self._tracker.update(obs, t) if tr.confirmed}
        events: list[Event] = []
        for tid, tr in tracks.items():
            events += self._step_track(t, tid, tr)
        for tid in [i for i in self._machines if i not in tracks]:
            events += self._step_orphan(t, tid)
        self._bus.publish_all(events)
        return events

    def _step_track(self, t: float, tid: int, tr: Track) -> list[Event]:
        sm = self._machines.get(tid)
        if sm is None:
            sm = self._machines[tid] = AttentionStateMachine(tid, self._sm_params)
            self._filters[tid] = OneEuroFilter(*self._filter_args)
        zone = self._zones.assign(tid, tr.centroid_px, t)
        self._last_zone[tid] = zone
        if tr.last_obs is None:
            return sm.step(t, None)
        sample = self._scorer.score(tr.last_obs, self._info.intrinsics)
        score = self._filters[tid].filter(t, sample.raw_score)
        az, el = self._zones.bearing(zone, tr.centroid_px)
        return sm.step(t, ScoredSample(score, sample.eyes_closed, zone, az, el))

    def _step_orphan(self, t: float, tid: int) -> list[Event]:
        sm = self._machines[tid]
        events = sm.step(t, None)
        if sm.state is AttentionState.LOST:
            self._forget(tid)
        return events

    def _forget(self, tid: int) -> None:
        self._machines.pop(tid, None)
        self._filters.pop(tid, None)
        self._zones.forget(tid)
        self._last_zone.pop(tid, None)


def build_pipeline(
    cfg: Config, info: SourceInfo, perception: FacePerception, bus: EventBus
) -> Pipeline:
    t = cfg.tracking
    tracker = IouTracker(
        TrackerParams(t.iou_gate, t.high_conf, t.confirm_hits, t.max_coast_s),
        (info.width, info.height),
    )
    zones = SectorZoneMap(
        info.width, info.intrinsics, cfg.zones.boundaries, cfg.zones.margin_px, cfg.zones.switch_s
    )
    oe = cfg.attention.one_euro
    return Pipeline(
        info,
        perception,
        tracker,
        zones,
        scorer_from_config(cfg.attention),
        sm_params_from_config(cfg.attention),
        (oe.min_cutoff, oe.beta, oe.d_cutoff),
        bus,
    )
