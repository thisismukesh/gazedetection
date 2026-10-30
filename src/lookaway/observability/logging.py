"""structlog setup. Implements SPECS/19 Logs and AC-SYS-02 (no arrays in log lines)."""

from __future__ import annotations

import logging
import logging.handlers
import sys
from collections.abc import Mapping, MutableMapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np
import structlog

_MAX_NUMBERS = 8
_REDACTED = "<array redacted>"


def _scrub(v: Any) -> Any:
    if isinstance(v, np.ndarray):
        return _REDACTED if v.size > _MAX_NUMBERS else v.tolist()
    if isinstance(v, Mapping):
        return {k: _scrub(x) for k, x in cast(Mapping[str, Any], v).items()}
    if isinstance(v, list | tuple):
        seq = cast(Sequence[Any], v)
        if len(seq) > _MAX_NUMBERS and all(isinstance(x, int | float) for x in seq):
            return _REDACTED
        return [_scrub(x) for x in seq]
    return v


def scrub_arrays(
    _logger: object, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Never let images, landmark arrays or embeddings reach a log line."""
    return {k: _scrub(v) for k, v in event_dict.items()}


def configure_logging(level: str, development: bool, log_dir: Path | None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if development and log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(
            logging.handlers.RotatingFileHandler(
                log_dir / "lookaway.log", maxBytes=2_000_000, backupCount=3
            )
        )
    for h in handlers:
        h.setFormatter(logging.Formatter("%(message)s"))
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO), handlers=handlers, force=True
    )
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", key="t"),
            scrub_arrays,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
