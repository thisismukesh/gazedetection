"""Guided webcam check for AC-PER-05 (manual): head axes, iris/eye pairing, wink side.

Run: uv run python tools/check_orientation.py [camera_index]
Frames stay in memory; only scalar results are printed. Follow the prompts for 3 s each.
"""

from __future__ import annotations

import statistics
import sys
import time
from collections.abc import Callable

import numpy as np

from lookaway.capture.webcam import WebcamSource
from lookaway.clock import MonotonicClock
from lookaway.config import load_config
from lookaway.perception.geometry import face_position, forward_axis
from lookaway.perception.mediapipe_face import MediaPipeFacePerception
from lookaway.types import FaceObservation

Sample = dict[str, float]


def _sample(obs: FaceObservation, intr, ipd_m: float) -> Sample:  # noqa: ANN001
    f = forward_axis(obs.R_cam_head)
    pos = face_position(obs.centroid_px, obs.iod_px, intr, ipd_m)
    to_cam = -pos / np.linalg.norm(pos)
    (l0, l1), (r0, r1) = obs.eye_corners_px
    inside_l = min(l0[0], l1[0]) < obs.iris_px[0][0] < max(l0[0], l1[0])
    inside_r = min(r0[0], r1[0]) < obs.iris_px[1][0] < max(r0[0], r1[0])
    return {
        "fx": float(f[0]),
        "fy": float(f[1]),
        "fz": float(f[2]),
        "ang": float(np.degrees(np.arccos(np.clip(f @ to_cam, -1, 1)))),
        "blink_l": obs.blink[0],
        "blink_r": obs.blink[1],
        "iris_ok": float(inside_l and inside_r),
    }


def _collect(src: WebcamSource, perc: MediaPipeFacePerception, ipd_m: float, secs: float = 3.0):
    out: list[Sample] = []
    end = time.monotonic() + secs
    while time.monotonic() < end:
        frame = src.read()
        if frame is None:
            continue
        faces = perc.process(frame)
        if faces:
            biggest = max(faces, key=lambda o: o.iod_px)
            out.append(_sample(biggest, src.info.intrinsics, ipd_m))
    return out


def _step(name: str, prompt: str, check: Callable[[Sample], str | None], src, perc, ipd) -> bool:  # noqa: ANN001
    print(f"\n>> {prompt}  (starting in 3 s)")
    time.sleep(3)
    samples = _collect(src, perc, ipd)
    if len(samples) < 10:
        print(f"   FAIL {name}: only {len(samples)} frames with a face")
        return False
    med = {k: statistics.median(s[k] for s in samples) for k in samples[0]}
    problem = check(med)
    print(
        f"   {'PASS' if problem is None else 'FAIL'} {name}: "
        + (problem or "ok")
        + f"  [fx={med['fx']:+.2f} fy={med['fy']:+.2f} fz={med['fz']:+.2f} ang={med['ang']:.0f}deg"
        + f" blinkL={med['blink_l']:.2f} blinkR={med['blink_r']:.2f}]"
    )
    return problem is None


def main() -> int:
    cfg = load_config()
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    src = WebcamSource(
        idx,
        cfg.capture.width,
        cfg.capture.height,
        cfg.capture.fps,
        cfg.capture.hfov_rad,
        MonotonicClock(),
    )
    src.open()
    perc = MediaPipeFacePerception(cfg.perception)
    ipd = cfg.attention.ipd_m
    steps: list[tuple[str, str, Callable[[Sample], str | None]]] = [
        (
            "frontal",
            "Look straight INTO the camera lens",
            lambda m: (
                None
                if m["fz"] < -0.9 and m["ang"] < 15 and m["iris_ok"] > 0.9
                else "forward axis within 15 deg of the camera, irises between corners"
            ),
        ),
        (
            "turn-left",
            "Turn your head to YOUR LEFT (about 30 deg), keep your eyes on the screen",
            lambda m: None if m["fx"] > 0.25 else "expected forward.x > +0.25 (image right)",
        ),
        (
            "turn-right",
            "Turn your head to YOUR RIGHT (about 30 deg)",
            lambda m: None if m["fx"] < -0.25 else "expected forward.x < -0.25 (image left)",
        ),
        (
            "look-up",
            "Tilt your head UP (chin raised, about 20 deg)",
            lambda m: None if m["fy"] < -0.2 else "expected forward.y < -0.2 (up is -y in OpenCV)",
        ),
        (
            "look-down",
            "Tilt your head DOWN (about 20 deg)",
            lambda m: None if m["fy"] > 0.2 else "expected forward.y > +0.2 (down is +y)",
        ),
        (
            "wink-right",
            "Close ONLY YOUR RIGHT eye, keep the other open",
            lambda m: (
                None
                if m["blink_l"] > m["blink_r"] + 0.3
                else "expected blink[0] (image-left = your right eye) to be the high one"
            ),
        ),
    ]
    ok = [_step(n, p, c, src, perc, ipd) for n, p, c in steps]
    src.close()
    print(
        "\nALL PASS"
        if all(ok)
        else "\nSOME CHECKS FAILED: fix SPECS/11 tables before trusting scores"
    )
    return 0 if all(ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
