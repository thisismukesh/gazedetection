from __future__ import annotations

import math

import pytest

from lookaway.attention.one_euro import OneEuroFilter


def test_first_sample_passes_through() -> None:
    f = OneEuroFilter(min_cutoff=1.0, beta=0.05, d_cutoff=1.0)
    assert f.filter(0.0, 0.7) == 0.7


def test_constant_input_is_constant() -> None:
    f = OneEuroFilter(1.0, 0.05, 1.0)
    out = [f.filter(i / 30, 0.4) for i in range(60)]
    assert all(o == pytest.approx(0.4) for o in out)


def test_attenuates_noise() -> None:
    f = OneEuroFilter(1.0, 0.0, 1.0)
    raw = [0.5 + (0.2 if i % 2 else -0.2) for i in range(90)]
    out = [f.filter(i / 30, x) for i, x in enumerate(raw)]
    assert max(out[30:]) - min(out[30:]) < 0.1 * (max(raw) - min(raw))


def test_beta_reduces_lag_on_step() -> None:
    slow = OneEuroFilter(1.0, 0.0, 1.0)
    fast = OneEuroFilter(1.0, 5.0, 1.0)
    for f in (slow, fast):
        for i in range(30):
            f.filter(i / 30, 0.0)
    a = [slow.filter((30 + i) / 30, 1.0) for i in range(5)]
    b = [fast.filter((30 + i) / 30, 1.0) for i in range(5)]
    assert b[-1] > a[-1]
    assert all(math.isfinite(x) for x in a + b)


def test_reset_forgets_history() -> None:
    f = OneEuroFilter(1.0, 0.05, 1.0)
    f.filter(0.0, 0.0)
    f.filter(0.1, 0.0)
    f.reset()
    assert f.filter(0.2, 0.9) == 0.9


def test_non_increasing_time_is_safe() -> None:
    f = OneEuroFilter(1.0, 0.05, 1.0)
    f.filter(1.0, 0.2)
    assert math.isfinite(f.filter(1.0, 0.8))
