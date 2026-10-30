"""Test helpers that build module params from the canonical config."""

from __future__ import annotations

from dataclasses import replace

from lookaway.attention.factory import sm_params_from_config
from lookaway.attention.state_machine import SMParams
from lookaway.config import load_config


def default_sm_params(**overrides: float | bool | int) -> SMParams:
    return replace(sm_params_from_config(load_config().attention), **overrides)
