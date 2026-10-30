from __future__ import annotations

import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from lookaway.config import Config, config_sha256, load_config

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / "config" / "default.toml"


def test_default_loads() -> None:
    cfg = load_config()
    assert cfg.zones.count == 3
    assert cfg.attention.t_off < cfg.attention.t_on


def test_degrees_converted_to_radians() -> None:
    cfg = load_config()
    assert cfg.attention.cone_rad == pytest.approx(math.radians(cfg.attention.cone_deg))
    assert cfg.control.limits.yaw_rad == pytest.approx(math.radians(60.0))
    assert cfg.capture.hfov_rad == pytest.approx(math.radians(70.0))


def test_overrides_merge(tmp_path: Path) -> None:
    f = tmp_path / "o.toml"
    f.write_text("[observability]\noverlay = true\n")
    cfg = load_config(f)
    assert cfg.observability.overlay is True
    assert cfg.zones.count == 3


def test_shipped_overrides_load() -> None:
    assert load_config(ROOT / "config" / "demo.toml").observability.overlay is True
    dev = load_config(ROOT / "config" / "dev.toml")
    assert dev.privacy.mode == "development"
    assert dev.observability.log_level == "DEBUG"


def test_unknown_key_rejected(tmp_path: Path) -> None:
    f = tmp_path / "o.toml"
    f.write_text("[zones]\nbogus = 1\n")
    with pytest.raises(ValidationError):
        load_config(f)


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOOKAWAY__ZONES__SWITCH_S", "0.9")
    assert load_config().zones.switch_s == 0.9


def test_cli_source_override() -> None:
    assert load_config(source="video:x.mp4").capture.source == "video:x.mp4"


@pytest.mark.parametrize(
    "toml",
    [
        "[attention]\nt_off = 0.7\n",
        "[zones]\nboundaries = [0.6, 0.3]\n",
        "[zones]\nboundaries = [0.5]\n",
        "[zones]\nboundaries = [0.0, 0.5]\n",
        "[attention]\neye_weight_iod_min_px = 50.0\n",
        "[control]\nhold_s = 0.0\n",
        "[control.limits]\nvel_deg_s = -1.0\n",
        '[privacy]\nmode = "installation"\nallow_restricted_models = true\n',
    ],
)
def test_cross_field_checks(tmp_path: Path, toml: str) -> None:
    f = tmp_path / "o.toml"
    f.write_text(toml)
    with pytest.raises(ValidationError):
        load_config(f)


def test_restricted_with_license_ref_ok(tmp_path: Path) -> None:
    f = tmp_path / "o.toml"
    f.write_text(
        '[privacy]\nmode = "installation"\nallow_restricted_models = true\n'
        'restricted_license_ref = "LIC-1"\n'
    )
    assert load_config(f).privacy.allow_restricted_models is True


def test_hash_stable_and_sensitive() -> None:
    a, b = load_config(), load_config()
    assert config_sha256(a) == config_sha256(b)
    assert config_sha256(a) != config_sha256(load_config(source="video:x.mp4"))
    assert isinstance(a, Config)


def test_AC_REN_05_camera_view_refused_on_lan(tmp_path: Path) -> None:
    f = tmp_path / "o.toml"
    f.write_text("[render]\nallow_lan = true\n")
    with pytest.raises(ValidationError):
        load_config(f)
    f.write_text("[render]\nallow_lan = true\ncamera_view = false\n")
    assert load_config(f).render.allow_lan is True
