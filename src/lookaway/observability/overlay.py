"""Debug overlay. Implements SPECS/19 Debug overlay. The frame is never written to disk.

``draw_overlay`` is pure drawing; ``OverlayWindow`` owns the OpenCV window and must be used from
the main thread (macOS requires GUI calls there).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import cv2
import numpy as np
from numpy.typing import NDArray

from lookaway.pipeline import DebugTrack
from lookaway.types import AttentionState

_STATE_BGR = {
    AttentionState.LOOKING: (80, 200, 80),
    AttentionState.AWAY_PENDING: (0, 190, 255),
    AttentionState.LOOKING_PENDING: (0, 190, 255),
    AttentionState.AWAY: (60, 60, 230),
    AttentionState.UNKNOWN: (150, 150, 150),
    AttentionState.LOST: (150, 150, 150),
}
_FONT = cv2.FONT_HERSHEY_SIMPLEX
_HEAD_BGR = (255, 255, 0)  # cyan: where the head points
_GAZE_BGR = (0, 255, 255)  # yellow: where the eyes plus head point
_ARROW_IOD = 4.0  # arrow length in inter-ocular distances per unit of sideways direction


@dataclass(frozen=True, slots=True)
class OverlayInfo:
    tracks: list[DebugTrack]
    boundaries: list[float]
    head_modes: dict[int, str]
    head_targets: dict[int, int | None]
    fps: float
    p95_ms: float
    mirror: bool
    assignments: dict[int, int] = field(default_factory=dict[int, int])
    shared: frozenset[int] = frozenset()  # tracks that own every head (a lone person)


def _fs(w: int) -> float:
    """Font scale that stays readable from a 480 px camera view up to full resolution."""
    return max(0.55, min(1.0, w / 700))


def _text(
    out: NDArray[np.uint8], text: str, org: tuple[int, int], color: tuple[int, int, int], fs: float
) -> None:
    """Text on a translucent dark box: legible on any background and at any size."""
    (tw, th), base = cv2.getTextSize(text, _FONT, fs, 1)
    org = (max(3, min(org[0], out.shape[1] - tw - 4)), org[1])  # keep labels inside the frame
    x0, y0 = max(org[0] - 3, 0), max(org[1] - th - 3, 0)
    x1, y1 = min(org[0] + tw + 3, out.shape[1]), min(org[1] + base + 2, out.shape[0])
    if x1 > x0 and y1 > y0:
        roi = out[y0:y1, x0:x1]
        out[y0:y1, x0:x1] = cv2.addWeighted(roi, 0.4, np.zeros_like(roi), 0.6, 0)
    cv2.putText(out, text, org, _FONT, fs, color, 1, cv2.LINE_AA)


def scale_info(info: OverlayInfo, s: float) -> OverlayInfo:
    """Scale pixel coordinates when the image was resized by ``s`` before drawing."""

    def p(v: tuple[float, float]) -> tuple[float, float]:
        return (v[0] * s, v[1] * s)

    tracks = [
        replace(
            t,
            bbox_px=(t.bbox_px[0] * s, t.bbox_px[1] * s, t.bbox_px[2] * s, t.bbox_px[3] * s),
            centroid_px=p(t.centroid_px),
            iod_px=t.iod_px * s,
            iris_px=None if t.iris_px is None else (p(t.iris_px[0]), p(t.iris_px[1])),
        )
        for t in info.tracks
    ]
    return replace(info, tracks=tracks)


def _x(x: float, w: int, mirror: bool) -> int:
    return int(round(w - 1 - x)) if mirror else int(round(x))


def draw_overlay(image: NDArray[np.uint8], info: OverlayInfo) -> NDArray[np.uint8]:
    # Mirror the picture itself, not just the coordinates, or every box lands on the wrong side.
    out = np.ascontiguousarray(image[:, ::-1]) if info.mirror else image.copy()
    h, w = out.shape[:2]
    for b in info.boundaries:  # boundaries are fractions in the audience frame
        x_aud = b * w
        x = int(round(x_aud)) if info.mirror else int(round(w - 1 - x_aud))
        cv2.line(out, (x, 0), (x, h), (120, 120, 120), 1)
    for t in info.tracks:
        x0, y0, x1, y1 = t.bbox_px
        xa, xb = sorted((_x(x0, w, info.mirror), _x(x1, w, info.mirror)))
        if not t.live:  # a still, never-blinking face (poster, mask): shown, never acted on
            cv2.rectangle(out, (xa, int(y0)), (xb, int(y1)), (130, 130, 130), 1)
            _text(out, "static?", (xa, max(int(y0) - 8, 14)), (160, 160, 160), _fs(w))
            continue
        color = _STATE_BGR[t.state]
        cv2.rectangle(out, (xa, int(y0)), (xb, int(y1)), color, 2)
        head = info.assignments.get(t.id)
        label = f"#{t.id} {t.state.name.lower()} {t.score:.2f}" + (
            (" -> all heads" if t.id in info.shared else f" -> head {head}")
            if head is not None
            else ""
        )
        _text(out, label, (xa, max(int(y0) - 8, 14)), color, _fs(w))
        bar_w = int((xb - xa) * max(0.0, min(1.0, t.score)))
        cv2.rectangle(out, (xa, int(y1) + 4), (xa + bar_w, int(y1) + 10), color, -1)
        _draw_vectors(out, t, info.mirror)
    for k, mode in sorted(info.head_modes.items()):
        tgt = info.head_targets.get(k)
        text = f"head {k}: {mode}" + (f" (#{tgt})" if tgt is not None else "")
        step = int(34 * _fs(w))
        _text(
            out, text, (10, h - 12 - step * (len(info.head_modes) - 1 - k)), (230, 230, 230), _fs(w)
        )
    _text(
        out,
        f"{info.fps:.0f} fps  p95 {info.p95_ms:.0f} ms",
        (10, int(24 * _fs(w))),
        (230, 230, 230),
        _fs(w),
    )
    return out


def _draw_vectors(out: NDArray[np.uint8], t: DebugTrack, mirror: bool) -> None:
    """Head direction (cyan, from the face) and gaze direction (yellow, from each iris)."""
    if t.head_dir is None or t.gaze_dir is None or t.iris_px is None:
        return
    w = out.shape[1]
    thick = max(2, w // 320)
    length = _ARROW_IOD * max(t.iod_px, 20.0)
    sign = -1.0 if mirror else 1.0  # a mirrored view flips left and right

    def tip(origin: tuple[float, float], d: tuple[float, float, float]) -> tuple[int, int]:
        return int(round(origin[0] + sign * d[0] * length)), int(round(origin[1] + d[1] * length))

    cx, cy = t.centroid_px
    start = (_x(cx, w, mirror), int(round(cy)))
    cv2.arrowedLine(out, start, tip(start, t.head_dir), _HEAD_BGR, thick, tipLength=0.25)
    for ix, iy in t.iris_px:
        p = (_x(ix, w, mirror), int(round(iy)))
        cv2.circle(out, p, max(2, thick), _GAZE_BGR, -1)
        cv2.arrowedLine(out, p, tip(p, t.gaze_dir), _GAZE_BGR, thick, tipLength=0.25)


class OverlayWindow:
    """OpenCV window with the D (toggle) and Q (quit) keys. Main thread only."""

    NAME = "Look Away debug"

    def __init__(self) -> None:
        self.visible = True

    def show(self, image: NDArray[np.uint8], info: OverlayInfo) -> bool:
        """Draw and poll keys. Returns False when the user pressed Q."""
        if self.visible:
            cv2.imshow(self.NAME, draw_overlay(image, info))
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            return False
        if key == ord("d"):
            self.visible = not self.visible
            if not self.visible:
                cv2.destroyWindow(self.NAME)
        return True

    def close(self) -> None:
        cv2.destroyAllWindows()
