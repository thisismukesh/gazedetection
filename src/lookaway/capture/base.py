"""Capture helpers. Implements SPECS/10 (intrinsics, source selection)."""

from __future__ import annotations

import math

from lookaway.types import Intrinsics


class SourceError(Exception):
    """Raised by CameraSource.read() on a hard read failure (None means no new frame)."""


def intrinsics_from_hfov(width: int, height: int, hfov_rad: float) -> Intrinsics:
    """Implements SPECS/10 §4. AC-CAP-04."""
    f = (width / 2) / math.tan(hfov_rad / 2)
    return Intrinsics(f, f, width / 2, height / 2)


def parse_source(spec: str) -> tuple[str, str]:
    """Split ``webcam:<index> | video:<path> | replay:<path>`` into (kind, arg)."""
    kind, sep, arg = spec.partition(":")
    if not sep or kind not in ("webcam", "video", "replay"):
        raise ValueError(f"bad source spec: {spec!r}")
    return kind, arg
