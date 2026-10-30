"""AC-SYS-06 (D16) and AC-MASK-05 (D17): whenever a person is marked away, their heads react."""

from __future__ import annotations

import random
from pathlib import Path

from lookaway.capture.replay import ReplaySource
from lookaway.config import load_config
from lookaway.control.assigner import HeadAssigner
from lookaway.control.drivers.simulated import RecordingHeadDriver
from lookaway.control.factory import build_head_controller
from lookaway.events import (
    EventBus,
    GazeAcquired,
    GazeLost,
    GazeRegained,
    HeadModeChanged,
    TrackLost,
    TrackUpdated,
)
from lookaway.perception.replay import ReplayPerception, write_jsonl
from lookaway.pipeline import build_pipeline
from lookaway.types import AttentionState, HeadMode
from tests.fixtures import scenarios
from tests.fixtures.scenarios import sway
from tests.fixtures.synth import make_obs


def _run(
    recs: list[scenarios.Record], tmp_path: Path, behaviour: str = "stare"
) -> list[tuple[float, set[int], bool]]:
    """Replay through pipeline -> assigner -> 3 heads; per frame: (t, staring heads, away?)."""
    path = tmp_path / "r.jsonl"
    write_jsonl(path, recs)
    cfg = load_config()
    ctl = cfg.control.model_copy(update={"behaviour": behaviour})
    cfg = cfg.model_copy(update={"control": ctl})
    raw, bus = EventBus(), EventBus()
    src = ReplaySource(path, 1280, 720, cfg.capture.hfov_rad, 30)
    pipe = build_pipeline(cfg, src.info, ReplayPerception(path), raw)
    assigner = HeadAssigner([pipe.zone_center(k) for k in range(3)])
    for et in (GazeAcquired, GazeLost, GazeRegained, TrackUpdated, TrackLost):
        raw.subscribe(et, lambda e: bus.publish_all(assigner.on_event(e)))
    staring: set[int] = set()

    def on_mode(e: HeadModeChanged) -> None:
        if e.mode in (HeadMode.ORIENT, HeadMode.HOLD, HeadMode.MASK):
            staring.add(e.head_id)
        else:
            staring.discard(e.head_id)

    bus.subscribe(HeadModeChanged, on_mode)
    heads = [
        build_head_controller(cfg.control, k, RecordingHeadDriver(), bus, random.Random(k))
        for k in range(3)
    ]
    out: list[tuple[float, set[int], bool]] = []
    src.open()
    t = 0.0
    while (f := src.read()) is not None:
        pipe.process(f)
        while t < f.t_capture:
            t += 0.01
            for h in heads:
                h.tick(t)
        away = any(d.state is AttentionState.AWAY for d in pipe.debug)
        out.append((f.t_capture, set(staring), away))
    return out


def _settled(trace: list[tuple[float, set[int], bool]]) -> bool:
    """Every frame marked away for 0.3 s or more has all three heads staring."""
    run = 0.0
    prev = None
    for t, staring, away in trace:
        run = run + (t - prev) if (away and prev is not None) else 0.0
        prev = t
        if away and run >= 0.3 and staring != {0, 1, 2}:
            return False
    return True


def test_AC_SYS_06_first_seen_away_is_stared_at(tmp_path: Path) -> None:
    recs: list[scenarios.Record] = []
    for i in range(30 * 6):  # turned away from the very first frame
        t = i / 30
        recs.append(
            (i, t, [make_obs(t=t, x_px=520 + sway(t), distance_m=1.2, head_yaw_deg=40.0,
                             head_pitch_deg=0.0)])
        )  # fmt: skip
    trace = _run(recs, tmp_path)
    assert any(away for _, _, away in trace)
    assert _settled(trace)


def test_AC_SYS_06_look_away_inside_the_cooldown_is_stared_at(tmp_path: Path) -> None:
    recs: list[scenarios.Record] = []
    for i in range(30 * 8):
        t = i / 30
        away = 3.0 <= t < 3.5 or 3.9 <= t < 6.0  # second look-away 0.4 s after the first ends
        kw: dict[str, float] = {"head_yaw_deg": 40.0, "head_pitch_deg": 0.0} if away else {}
        recs.append((i, t, [make_obs(t=t, x_px=520 + sway(t), distance_m=1.2, **kw)]))
    trace = _run(recs, tmp_path)
    late = [s for t, s, a in trace if 4.6 <= t < 6.0]
    assert late and all(s == {0, 1, 2} for s in late)


def _away_rec(seconds: float, away: tuple[float, float]) -> list[scenarios.Record]:
    recs: list[scenarios.Record] = []
    for i in range(round(30 * seconds)):
        t = i / 30
        is_away = away[0] <= t < away[1]
        kw: dict[str, float] = {"head_yaw_deg": 40.0, "head_pitch_deg": 0.0} if is_away else {}
        recs.append((i, t, [make_obs(t=t, x_px=520 + sway(t), distance_m=1.2, **kw)]))
    return recs


def test_AC_MASK_05_lone_person_looking_away_masks_all_three(tmp_path: Path) -> None:
    trace = _run(_away_rec(7.0, (3.0, 5.0)), tmp_path, behaviour="mask")
    assert _settled(trace)
    after = [s for t, s, _ in trace if t >= 6.2]
    assert after and all(s == set() for s in after)  # masks off once they look back
