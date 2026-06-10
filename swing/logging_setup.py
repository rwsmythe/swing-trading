"""Composition root for swing logging.

Unlike the swing.logging_config SEAM (Schwab-agnostic by construction), THIS
module is Schwab-AWARE: it wires the redaction belts (Belt A factory + Belt B
RedactingFormatter) by construction, so every surface routed through
``install_logging`` is redacted -- adding a surface cannot omit redaction. The
schwab import lives ONLY here, preserving seam purity.
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from swing.config import Config
from swing.logging_config import DEFAULT_LOG_FORMAT, configure_logging


def install_logging(cfg: Config, *, surface: str) -> None:
    from swing.integrations.schwab.client import (
        RedactingFormatter,
        ensure_schwab_log_redaction_factory_installed,
    )

    log_cfg = cfg.logging
    configure_logging(
        cfg.paths.logs_dir,
        surface=surface,
        level=log_cfg.level,
        formatter=RedactingFormatter(DEFAULT_LOG_FORMAT),     # Belt B, every surface
        max_bytes=log_cfg.max_bytes,
        backup_count=log_cfg.backup_count,
        install_record_factory=ensure_schwab_log_redaction_factory_installed,  # Belt A
    )
    # Slice 2 will add logger_levels=log_cfg.resolved_logger_levels() and
    # record_filter=_correlation_filter(surface) here; the seam already accepts both.
    _replay_logging_diagnostics(cfg, surface=surface)


def _replay_logging_diagnostics(cfg: Config, *, surface: str) -> None:
    """Replay COLLECTED config-parse diagnostics AFTER the redacted handler is
    attached (R1-major-4). Delivery bypasses the root level + any per-logger
    override by calling ``handler.handle`` DIRECTLY on the swing surface handler
    (the handler level is NOTSET, R4-major-1 / R2-major-2). The record still passes
    through Belt B (RedactingFormatter) on that handler, so diagnostics are redacted.
    """
    warnings = getattr(cfg.logging, "warnings", ())
    if not warnings:
        return
    target = os.path.abspath(cfg.paths.logs_dir / f"{surface}.log")  # match baseFilename
    handler = next(
        (
            h for h in logging.getLogger().handlers
            if isinstance(h, RotatingFileHandler) and h.baseFilename == target
        ),
        None,
    )
    if handler is None:
        return
    for msg in warnings:
        record = logging.LogRecord(
            name="swing.logging_config", level=logging.WARNING,
            pathname=__file__, lineno=0, msg="%s", args=(msg,), exc_info=None,
        )
        handler.handle(record)
