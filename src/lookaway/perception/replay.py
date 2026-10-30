"""Landmark-stream replay and JSONL codec. Implements SPECS/11 Replay."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from lookaway.types import FaceObservation, Frame, Mat3


def obs_to_dict(o: FaceObservation) -> dict[str, Any]:
    return asdict(o)


def _p(v: Any) -> tuple[float, float]:
    return (float(v[0]), float(v[1]))


def obs_from_dict(d: dict[str, Any]) -> FaceObservation:
    r = d["R_cam_head"]
    return FaceObservation(
        t=float(d["t"]),
        bbox_px=cast("tuple[float, float, float, float]", tuple(float(x) for x in d["bbox_px"])),
        centroid_px=_p(d["centroid_px"]),
        confidence=float(d["confidence"]),
        iod_px=float(d["iod_px"]),
        R_cam_head=cast(
            "Mat3",
            tuple(tuple(float(x) for x in row) for row in r),
        ),
        iris_px=(_p(d["iris_px"][0]), _p(d["iris_px"][1])),
        eye_corners_px=tuple(  # pyright: ignore[reportArgumentType]
            (_p(e[0]), _p(e[1])) for e in d["eye_corners_px"]
        ),
        eye_lids_px=tuple(  # pyright: ignore[reportArgumentType]
            (_p(e[0]), _p(e[1])) for e in d["eye_lids_px"]
        ),
        blink=(float(d["blink"][0]), float(d["blink"][1])),
    )


def write_jsonl(path: Path, records: list[tuple[int, float, list[FaceObservation]]]) -> None:
    with path.open("w") as f:
        for index, t, faces in records:
            rec = {"index": index, "t": t, "faces": [obs_to_dict(o) for o in faces]}
            f.write(json.dumps(rec) + "\n")


def read_jsonl(path: Path) -> list[tuple[int, float, list[FaceObservation]]]:
    out: list[tuple[int, float, list[FaceObservation]]] = []
    for line in path.read_text().splitlines():
        if line.strip():
            rec = json.loads(line)
            faces = [obs_from_dict(d) for d in rec["faces"]]
            out.append((int(rec["index"]), float(rec["t"]), faces))
    return out


class ReplayPerception:
    """Returns the recorded faces for the frame index. No camera, no model."""

    def __init__(self, path: Path | str) -> None:
        self._by_index = {i: faces for i, _t, faces in read_jsonl(Path(path))}

    def process(self, frame: Frame) -> list[FaceObservation]:
        return list(self._by_index.get(frame.index, []))
