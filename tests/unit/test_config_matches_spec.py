"""Guardrail: config/default.toml equals the canonical block in SPECS/18 (CLAUDE.md §3)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_default_toml_matches_spec_block() -> None:
    spec = (ROOT / "SPECS" / "18-config.md").read_text()
    block = re.search(r"```toml\n(.*?)```", spec, re.S)
    assert block is not None
    expected = tomllib.loads(block.group(1))
    actual = tomllib.loads((ROOT / "config" / "default.toml").read_text())
    assert actual == expected
