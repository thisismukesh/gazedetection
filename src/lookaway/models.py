"""Model download with SHA-256 verification. Implements CLAUDE.md §7 (fetch-models).

This is the only code that opens a network connection, and only when the user runs the command.
The hash was measured from the file downloaded from the URL below.
"""

from __future__ import annotations

import hashlib
import urllib.request
from collections.abc import Callable
from pathlib import Path

FACE_LANDMARKER_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/"
    "float16/1/face_landmarker.task"
)
FACE_LANDMARKER_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"


class ChecksumError(Exception):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url, timeout=60) as r, dest.open("wb") as f:
        f.write(r.read())


def fetch_model(
    dest: Path,
    url: str = FACE_LANDMARKER_URL,
    sha256: str = FACE_LANDMARKER_SHA256,
    download: Callable[[str, Path], None] = _download,
) -> bool:
    """Ensure ``dest`` exists with the pinned hash. Returns True if a download happened."""
    if dest.exists() and sha256_file(dest) == sha256:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    download(url, tmp)
    got = sha256_file(tmp)
    if got != sha256:
        tmp.unlink(missing_ok=True)
        raise ChecksumError(f"sha256 mismatch for {url}: expected {sha256}, got {got}")
    tmp.replace(dest)
    return True
