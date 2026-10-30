from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from lookaway.models import ChecksumError, fetch_model

DATA = b"model-bytes"
SHA = hashlib.sha256(DATA).hexdigest()


def fake_download(url: str, dest: Path) -> None:
    dest.write_bytes(DATA)


def test_downloads_and_verifies(tmp_path: Path) -> None:
    dest = tmp_path / "m" / "x.task"
    assert fetch_model(dest, "u", SHA, fake_download) is True
    assert dest.read_bytes() == DATA


def test_skips_when_present_and_valid(tmp_path: Path) -> None:
    dest = tmp_path / "x.task"
    dest.write_bytes(DATA)
    calls: list[str] = []
    assert fetch_model(dest, "u", SHA, lambda u, d: calls.append(u)) is False
    assert calls == []


def test_mismatch_raises_and_leaves_no_file(tmp_path: Path) -> None:
    dest = tmp_path / "x.task"
    with pytest.raises(ChecksumError):
        fetch_model(dest, "u", "0" * 64, fake_download)
    assert not dest.exists() and not list(tmp_path.glob("*.part"))


def test_corrupt_existing_file_is_replaced(tmp_path: Path) -> None:
    dest = tmp_path / "x.task"
    dest.write_bytes(b"corrupt")
    assert fetch_model(dest, "u", SHA, fake_download) is True
    assert dest.read_bytes() == DATA
