from __future__ import annotations

import math

import pytest

from lookaway.zones.zone_map import SectorZoneMap, bearing_to_pixel_x, pixel_x_to_bearing
from tests.fixtures.synth import intrinsics

W = 1280
INTR = intrinsics()
B = [0.3333333, 0.6666667]


def zm() -> SectorZoneMap:
    return SectorZoneMap(W, INTR, B, margin_px=24, switch_s=0.4)


def raw_x(x_aud: float) -> float:
    return (W - 1) - x_aud


def test_AC_ZONE_01_new_track_owned_by_containing_zone() -> None:
    assert zm().assign(1, (raw_x(W / 6), 360.0), 0.0) == 0
    assert zm().assign(1, (raw_x(W / 2), 360.0), 0.0) == 1
    assert zm().assign(1, (raw_x(5 * W / 6), 360.0), 0.0) == 2


def test_audience_frame_is_mirrored() -> None:
    # raw image-left (small x) is the audience's right -> zone 2
    assert zm().assign(1, (50.0, 360.0), 0.0) == 2


def test_AC_ZONE_02_oscillation_inside_margin_never_switches() -> None:
    z = zm()
    edge = B[0] * W
    zone0 = z.assign(1, (raw_x(edge - 5), 360.0), 0.0)
    for i in range(1, 91):
        x_aud = edge + (10 if i % 2 else -10)
        assert z.assign(1, (raw_x(x_aud), 360.0), i / 30) == zone0


def test_AC_ZONE_03_crossing_past_margin_switches_once_after_dwell() -> None:
    z = zm()
    edge = B[0] * W
    z.assign(1, (raw_x(edge - 5), 360.0), 0.0)
    zones = []
    for i in range(1, 61):
        zones.append(z.assign(1, (raw_x(edge + 40), 360.0), i / 30))
    assert zones[0] == 0  # dwell not yet satisfied
    assert zones[-1] == 1
    assert sum(1 for a, b in zip(zones, zones[1:], strict=False) if a != b) == 1


def test_switch_timer_resets_when_back_inside_margin() -> None:
    z = zm()
    edge = B[0] * W
    z.assign(1, (raw_x(edge - 5), 360.0), 0.0)
    z.assign(1, (raw_x(edge + 40), 360.0), 0.1)
    z.assign(1, (raw_x(edge + 5), 360.0), 0.3)  # back within margin: reset
    assert z.assign(1, (raw_x(edge + 40), 360.0), 0.6) == 0
    assert z.assign(1, (raw_x(edge + 40), 360.0), 1.1) == 1


def test_forget_drops_state() -> None:
    z = zm()
    z.assign(1, (raw_x(100), 360.0), 0.0)
    z.forget(1)
    assert z.assign(1, (raw_x(1000), 360.0), 1.0) == 2


def test_AC_ZONE_04_bearing_properties() -> None:
    xs = [0.0, 100.0, 640.0, 900.0, 1279.0]
    az = [pixel_x_to_bearing(x, INTR) for x in xs]
    assert all(a > b for a, b in zip(az, az[1:], strict=False))
    assert pixel_x_to_bearing(INTR.cx, INTR) == 0.0
    for x in xs:
        assert bearing_to_pixel_x(pixel_x_to_bearing(x, INTR), INTR) == pytest.approx(x, abs=1e-6)


def test_zone_relative_bearing_zero_at_zone_centre() -> None:
    z = zm()
    for k in range(3):
        centre_aud = W * ((0 if k == 0 else B[k - 1]) + (1 if k == 2 else B[k])) / 2
        az, el = z.bearing(k, (raw_x(centre_aud), INTR.cy))
        assert az == pytest.approx(0.0, abs=1e-3)
        assert el == pytest.approx(0.0)


def test_elevation_positive_above_axis() -> None:
    _, el = zm().bearing(1, (640.0, 100.0))
    assert el == pytest.approx(math.atan((INTR.cy - 100.0) / INTR.fy))
