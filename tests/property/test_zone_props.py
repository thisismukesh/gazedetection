"""AC-ZONE-04 (round trip, monotonic) and AC-ZONE-05 (exactly one owner, D3)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from lookaway.zones.zone_map import SectorZoneMap, bearing_to_pixel_x, pixel_x_to_bearing
from tests.fixtures.synth import intrinsics

INTR = intrinsics()


@given(st.floats(0, 1279), st.floats(0, 1279))
def test_AC_ZONE_04_monotonic_and_round_trip(a: float, b: float) -> None:
    if a < b - 1e-9:
        assert pixel_x_to_bearing(a, INTR) > pixel_x_to_bearing(b, INTR)
    assert abs(bearing_to_pixel_x(pixel_x_to_bearing(a, INTR), INTR) - a) < 1e-6


@given(st.lists(st.tuples(st.floats(0, 1279), st.floats(0.0, 0.5)), min_size=1, max_size=200))
def test_AC_ZONE_05_always_exactly_one_valid_zone(path: list[tuple[float, float]]) -> None:
    z = SectorZoneMap(1280, INTR, [0.3333333, 0.6666667], 24, 0.4)
    t = 0.0
    for x, dt in path:
        t += dt
        zone = z.assign(1, (x, 360.0), t)
        assert zone in (0, 1, 2)
