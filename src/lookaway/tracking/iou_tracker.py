"""IoU + Hungarian tracker with alpha-beta prediction. Implements SPECS/12. AC-TRK-01..04."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import cast

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import linear_sum_assignment  # pyright: ignore

from lookaway.types import Box, FaceObservation, Track

# Alpha-beta gains and coast-time velocity decay are tracker internals, not behaviour knobs.
_ALPHA = 0.7
_BETA = 0.3
_COAST_DECAY = 0.9


@dataclass(frozen=True, slots=True)
class TrackerParams:
    iou_gate: float
    high_conf: float
    confirm_hits: int
    max_coast_s: float


@dataclass(slots=True)
class _State:
    id: int
    z: NDArray[np.float64]  # [cx, cy, w, h]
    v: NDArray[np.float64]
    created_t: float
    last_seen_t: float
    last_t: float
    hits: int = 1
    misses: int = 0
    confirmed: bool = False
    obs: FaceObservation | None = None


def _to_z(b: Box) -> NDArray[np.float64]:
    return np.array([(b[0] + b[2]) / 2, (b[1] + b[3]) / 2, b[2] - b[0], b[3] - b[1]])


def _to_box(z: NDArray[np.float64]) -> Box:
    return (
        float(z[0] - z[2] / 2),
        float(z[1] - z[3] / 2),
        float(z[0] + z[2] / 2),
        float(z[1] + z[3] / 2),
    )


def _iou(a: NDArray[np.float64], b: NDArray[np.float64]) -> float:
    ax0, ay0, ax1, ay1 = _to_box(a)
    bx0, by0, bx1, by1 = _to_box(b)
    iw = min(ax1, bx1) - max(ax0, bx0)
    ih = min(ay1, by1) - max(ay0, by0)
    if iw <= 0 or ih <= 0:
        return 0.0
    inter = iw * ih
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


class IouTracker:
    """Tracks faces over the full frame; zones are assigned downstream."""

    def __init__(self, params: TrackerParams, frame_size: tuple[int, int]) -> None:
        self._p = params
        self._diag = math.hypot(*frame_size)
        self._tracks: list[_State] = []
        self._next_id = 1

    def update(self, obs: list[FaceObservation], t: float) -> list[Track]:
        preds = [self._predict(s, t) for s in self._tracks]
        matches: dict[int, int] = {}  # track idx -> obs idx
        high = [j for j, o in enumerate(obs) if o.confidence >= self._p.high_conf]
        self._match(preds, obs, list(range(len(preds))), high, matches)
        free_t = [i for i in range(len(preds)) if i not in matches]
        free_o = [j for j in range(len(obs)) if j not in matches.values()]
        self._match(preds, obs, free_t, free_o, matches)
        used = set(matches.values())
        for i, s in enumerate(self._tracks):
            if i in matches:
                self._hit(s, preds[i], obs[matches[i]], t)
            else:
                self._miss(s, preds[i], t)
        self._tracks = [s for s in self._tracks if self._alive(s, t)]
        for j, o in enumerate(obs):
            if j not in used:
                self._spawn(o, t)
        return [self._export(s) for s in self._tracks]

    # -- internals --------------------------------------------------------------------------

    def _predict(self, s: _State, t: float) -> NDArray[np.float64]:
        dt = max(t - s.last_t, 0.0)
        return s.z + s.v * dt

    def _cost(self, pred: NDArray[np.float64], o: FaceObservation) -> float:
        iou = _iou(pred, _to_z(o.bbox_px))
        if iou > 0:
            return 1.0 - iou
        d = math.hypot(pred[0] - _to_z(o.bbox_px)[0], pred[1] - _to_z(o.bbox_px)[1])
        return 1.0 + d / self._diag

    def _match(
        self,
        preds: list[NDArray[np.float64]],
        obs: list[FaceObservation],
        ti: list[int],
        oj: list[int],
        out: dict[int, int],
    ) -> None:
        if not ti or not oj:
            return
        cost = np.array([[self._cost(preds[i], obs[j]) for j in oj] for i in ti])
        rows, cols = cast("tuple[list[int], list[int]]", linear_sum_assignment(cost))
        for r, c in zip(rows, cols, strict=True):
            i, j = ti[r], oj[c]
            if _iou(preds[i], _to_z(obs[j].bbox_px)) >= self._p.iou_gate:
                out[i] = j

    def _hit(self, s: _State, pred: NDArray[np.float64], o: FaceObservation, t: float) -> None:
        z = _to_z(o.bbox_px)
        dt = max(t - s.last_t, 1e-6)
        r = z - pred
        s.z = pred + _ALPHA * r
        s.v = s.v + _BETA * r / dt
        s.last_t = s.last_seen_t = t
        s.hits += 1
        s.misses = 0
        s.obs = o
        if s.hits >= self._p.confirm_hits:
            s.confirmed = True

    def _miss(self, s: _State, pred: NDArray[np.float64], t: float) -> None:
        s.z = pred
        s.v = s.v * _COAST_DECAY
        s.last_t = t
        s.misses += 1
        s.obs = None

    def _alive(self, s: _State, t: float) -> bool:
        if s.misses == 0:
            return True
        if not s.confirmed:
            return False
        return t - s.last_seen_t <= self._p.max_coast_s

    def _spawn(self, o: FaceObservation, t: float) -> None:
        z = _to_z(o.bbox_px)
        s = _State(self._next_id, z, np.zeros(4), t, t, t, obs=o)
        s.confirmed = self._p.confirm_hits <= 1
        self._tracks.append(s)
        self._next_id += 1

    def _export(self, s: _State) -> Track:
        centroid = s.obs.centroid_px if s.obs is not None else (float(s.z[0]), float(s.z[1]))
        return Track(
            id=s.id,
            bbox_px=_to_box(s.z),
            centroid_px=centroid,
            created_t=s.created_t,
            last_seen_t=s.last_seen_t,
            hits=s.hits,
            misses=s.misses,
            confirmed=s.confirmed,
            last_obs=s.obs,
        )
