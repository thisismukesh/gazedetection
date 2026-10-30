"""Perception -> tracking -> zones -> attention -> events per frame. Implements SPECS/02."""

from __future__ import annotations

from dataclasses import dataclass

from lookaway.attention.factory import scorer_from_config, sm_params_from_config
from lookaway.attention.one_euro import OneEuroFilter
from lookaway.attention.state_machine import AttentionStateMachine, SMParams
from lookaway.clock import Clock
from lookaway.config import Config
from lookaway.events import Event, EventBus
from lookaway.observability.metrics import Metrics
from lookaway.tracking.iou_tracker import IouTracker, TrackerParams
from lookaway.types import (
    AttentionScorer,
    AttentionState,
    Box,
    FacePerception,
    Frame,
    ScoredSample,
    SourceInfo,
    Track,
    Tracker,
    ZoneMap,
)
from lookaway.zones.zone_map import SectorZoneMap


@dataclass(frozen=True, slots=True)
class DebugTrack:
    id: int
    zone: int
    score: float
    state: AttentionState
    bbox_px: Box


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
        clock: Clock | None = None,
        metrics: Metrics | None = None,
    ) -> None:
        self._clock = clock
        self._metrics = metrics
        self.debug: list[DebugTrack] = []
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

    def zone_center(self, zone_id: int) -> float:
        return self._zones.center_bearing(zone_id)

    def process(self, frame: Frame) -> list[Event]:
        t = frame.t_capture
        t_start = self._clock.now() if self._clock is not None else None
        obs = self._perception.process(frame)
        tracks = {tr.id: tr for tr in self._tracker.update(obs, t) if tr.confirmed}
        events: list[Event] = []
        scores: dict[int, float] = {}
        for tid, tr in tracks.items():
            events += self._step_track(t, tid, tr, scores)
        for tid in [i for i in self._machines if i not in tracks]:
            events += self._step_orphan(t, tid)
        self.debug = [
            DebugTrack(
                tid,
                self._last_zone[tid],
                scores.get(tid, 0.0),
                self._machines[tid].state,
                tr.bbox_px,
            )
            for tid, tr in tracks.items()
            if tid in self._machines
        ]
        self._bus.publish_all(events)
        self._record(frame, t_start, len(obs), len(tracks), events)
        return events

    def _record(
        self, frame: Frame, t_start: float | None, faces: int, confirmed: int, events: list[Event]
    ) -> None:
        m, c = self._metrics, self._clock
        if m is None or c is None or t_start is None:
            return
        now = c.now()
        m.tick("fps_perception", now)
        m.observe("lat.capture_to_perception", now, (t_start - frame.t_capture) * 1000.0)
        m.observe("lat.perception_to_score", now, (now - t_start) * 1000.0)
        m.observe("lat.total", now, (now - frame.t_capture) * 1000.0)
        m.gauge("faces", faces)
        m.gauge("confirmed_tracks", confirmed)
        m.gauge("suppressed_triggers", sum(s.suppressed_triggers for s in self._machines.values()))
        for e in events:
            m.incr(f"events_total.{type(e).__name__}")

    def _step_track(self, t: float, tid: int, tr: Track, scores: dict[int, float]) -> list[Event]:
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
        scores[tid] = score
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
    cfg: Config,
    info: SourceInfo,
    perception: FacePerception,
    bus: EventBus,
    clock: Clock | None = None,
    metrics: Metrics | None = None,
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
        clock,
        metrics,
    )
