"""Debug overlay. Implements SPECS/19 Debug overlay. The frame is never written to disk.

``draw_overlay`` is pure drawing; ``OverlayWindow`` owns the OpenCV window and must be used from
the main thread (macOS requires GUI calls there).
"""

from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True, slots=True)
class OverlayInfo:
    tracks: list[DebugTrack]
    boundaries: list[float]
    head_modes: dict[int, str]
    head_targets: dict[int, int | None]
    fps: float
    p95_ms: float
    mirror: bool


def _x(x: float, w: int, mirror: bool) -> int:
    return int(round(w - 1 - x)) if mirror else int(round(x))


def draw_overlay(image: NDArray[np.uint8], info: OverlayInfo) -> NDArray[np.uint8]:
    out = image.copy()
    h, w = out.shape[:2]
    for b in info.boundaries:  # boundaries are fractions in the audience frame
        x_aud = b * w
        x = int(round(x_aud)) if info.mirror else int(round(w - 1 - x_aud))
        cv2.line(out, (x, 0), (x, h), (120, 120, 120), 1)
    for t in info.tracks:
        x0, y0, x1, y1 = t.bbox_px
        xa, xb = sorted((_x(x0, w, info.mirror), _x(x1, w, info.mirror)))
        color = _STATE_BGR[t.state]
        cv2.rectangle(out, (xa, int(y0)), (xb, int(y1)), color, 2)
        head = next((k for k, v in info.head_targets.items() if v == t.id), None)
        label = f"#{t.id} z{t.zone}" + (f" -> head {head}" if head is not None else "")
        cv2.putText(out, label, (xa, max(int(y0) - 8, 12)), _FONT, 0.5, color, 1, cv2.LINE_AA)
        bar_w = int((xb - xa) * max(0.0, min(1.0, t.score)))
        cv2.rectangle(out, (xa, int(y1) + 4), (xa + bar_w, int(y1) + 10), color, -1)
    for k, mode in sorted(info.head_modes.items()):
        tgt = info.head_targets.get(k)
        text = f"head {k}: {mode}" + (f" (#{tgt})" if tgt is not None else "")
        cv2.putText(out, text, (10, h - 12 - 20 * (len(info.head_modes) - 1 - k)), _FONT, 0.5,
                    (230, 230, 230), 1, cv2.LINE_AA)  # fmt: skip
    cv2.putText(out, f"{info.fps:.0f} fps  p95 {info.p95_ms:.0f} ms", (10, 22), _FONT, 0.55,
                (230, 230, 230), 1, cv2.LINE_AA)  # fmt: skip
    return out


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
