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
from swing.log_correlation import CorrelationFilter, reset_correlation_from_env
from swing.logging_config import (
    CORRELATION_LOG_DEFAULTS,
    DEFAULT_LOG_FORMAT,
    configure_logging,
)


def install_logging(cfg: Config, *, surface: str) -> None:
    from swing.integrations.schwab.client import (
        RedactingFormatter,
        ensure_schwab_log_redaction_factory_installed,
    )

    # Reset BEFORE seeding (spec R3-minor-3): clears any stale pipeline_run_id and
    # re-reads + validates SWING_WEB_REQUEST_ID for this process.
    reset_correlation_from_env()
    log_cfg = cfg.logging
    configure_logging(
        cfg.paths.logs_dir,
        surface=surface,
        level=log_cfg.level,
        # Belt B carries the SAME defaults= so the correlation fields are always
        # present even on a record that bypasses the filter.
        formatter=RedactingFormatter(DEFAULT_LOG_FORMAT, defaults=CORRELATION_LOG_DEFAULTS),
        max_bytes=log_cfg.max_bytes,
        backup_count=log_cfg.backup_count,
        install_record_factory=ensure_schwab_log_redaction_factory_installed,  # Belt A
        logger_levels=log_cfg.resolved_logger_levels(),                        # 2f overrides
        record_filter=CorrelationFilter(),                                     # 2d correlation
    )
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
    # Require the SWING-tagged handler for THIS surface (Codex R1 MAJOR): a foreign
    # RotatingFileHandler sharing the same baseFilename must never intercept the
    # replay -- routing through it could bypass Belt B (RedactingFormatter) or be
    # swallowed by a non-NOTSET foreign handler level. The seam tags only its own.
    handler = next(
        (
            h for h in logging.getLogger().handlers
            if isinstance(h, RotatingFileHandler)
            and getattr(h, "_swing_surface", None) == surface
            and h.baseFilename == target
        ),
        None,
    )
    if handler is None:
        return
    # Idempotent (Codex R1 MINOR): the dedup-refresh path returns the SAME handler
    # object across repeated install_logging calls, so guard against re-emitting the
    # same parse diagnostics. (Config is read once per process, so this is belt-and-
    # suspenders against a config-reload / test re-install.)
    if getattr(handler, "_swing_diagnostics_replayed", False):
        return
    for msg in warnings:
        record = logging.LogRecord(
            name="swing.logging_config", level=logging.WARNING,
            pathname=__file__, lineno=0, msg="%s", args=(msg,), exc_info=None,
        )
        handler.handle(record)
    handler._swing_diagnostics_replayed = True  # type: ignore[attr-defined]
