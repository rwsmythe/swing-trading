"""Neutral logging seam shared by the web app and the pipeline CLI subprocess.

Top-level (not under swing.web or swing.cli) so neither importer pulls in the
other. Schwab-agnostic by construction: it imports nothing from
swing.integrations.schwab -- the secret-bearing composition root
(swing/logging_setup.py) injects the RedactingFormatter via `formatter` and the
record-factory installer via `install_record_factory`.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path

DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# Slice-2 widens the live routing to all three; the seam accepts "cli" now so
# the signature is forward-stable (no Slice-2 seam re-touch).
_SWING_SURFACES = frozenset({"web", "pipeline", "cli"})


def _replace_swing_filter(
    handler: logging.Handler, record_filter: logging.Filter,
) -> None:
    """Install ``record_filter`` as the SINGLE swing-tagged filter on ``handler``.

    ``Handler.addFilter`` APPENDS, so a naive re-install on the dedup path would
    accumulate duplicate filters (R5-minor-1). Tag the swing filter, remove any
    prior swing-tagged filter, then add the fresh one. Foreign filters (a
    library's own) are never touched.
    """
    record_filter._swing_correlation = True  # type: ignore[attr-defined]
    for existing in list(handler.filters):
        if getattr(existing, "_swing_correlation", False):
            handler.removeFilter(existing)
    handler.addFilter(record_filter)


def configure_logging(
    logs_dir: Path,
    *,
    surface: str,
    level: int = logging.INFO,
    formatter: logging.Formatter | None = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    install_record_factory: Callable[[], None] | None = None,
    logger_levels: dict[str, int] | None = None,
    record_filter: logging.Filter | None = None,
) -> None:
    """Attach a size-based ``RotatingFileHandler`` writing ``{surface}.log`` to root.

    Idempotent (dedup by baseFilename). ``surface`` in {'web','pipeline','cli'}.
    Belt A (the process-global LogRecord factory) is INJECTED via
    ``install_record_factory`` and CALLED here -- the seam never imports it, so it
    stays Schwab-agnostic. ``formatter`` (Belt B) is set on the handler BEFORE it
    joins root (no unredacted window). The handler threshold stays NOTSET (0):
    thresholding is owned by the root logger + per-logger overrides, never the
    handler (R4-major-1). On the dedup path the supplied ``formatter`` /
    ``record_filter`` / ``logger_levels`` / ``level`` are refreshed, but the
    already-attached handler's maxBytes/backupCount are NOT mutated
    (R1-minor-1) -- a rotation-param change takes effect on the next process start.
    Single surface per process (§3.4): swing handlers are tagged ``_swing_surface``;
    attaching a NEW surface removes AND closes any prior swing handler so a process
    writes exactly one surface file (foreign handlers are never touched).
    """
    if surface not in _SWING_SURFACES:
        raise ValueError(
            f"surface must be one of {sorted(_SWING_SURFACES)}, got {surface!r}"
        )
    # Belt A first: install (idempotently) BEFORE any handler emits.
    if install_record_factory is not None:
        install_record_factory()
    logs_dir.mkdir(parents=True, exist_ok=True)
    # Absolutize to match FileHandler.baseFilename (which stores os.path.abspath),
    # so a relative logs_dir still dedups correctly (R2-major-4) rather than
    # close-and-recreating an "already attached" handler.
    target = os.path.abspath(Path(logs_dir) / f"{surface}.log")
    root = logging.getLogger()
    # Level is owned by the ROOT logger; set on EVERY path (incl. dedup).
    root.setLevel(level)
    if logger_levels:
        for name, lvl in logger_levels.items():
            logging.getLogger(name).setLevel(lvl)
    # Swing-managed handlers are TAGGED with `_swing_surface` so we find ours
    # without ever touching a foreign library's handler.
    swing_handlers = [
        h for h in root.handlers
        if isinstance(h, RotatingFileHandler)
        and getattr(h, "_swing_surface", None) is not None
    ]
    for h in swing_handlers:
        if h.baseFilename == target:
            # Same surface+file: idempotent dedup-refresh (R1-minor-1). Refresh
            # formatter / filter only; NEVER mutate maxBytes / backupCount.
            if formatter is not None:
                h.setFormatter(formatter)
            if record_filter is not None:
                _replace_swing_filter(h, record_filter)
            return
    # A genuinely new surface (or a new logs_dir for the same surface): enforce
    # ONE swing handler per process (§3.4). Remove AND close every prior swing
    # handler -- removeHandler alone leaves the file descriptor open, which on
    # Windows blocks rotation/rename + the cleanup (R2-major-4). Foreign handlers
    # are never removed/closed.
    for h in swing_handlers:
        root.removeHandler(h)
        h.close()
    handler = RotatingFileHandler(
        filename=target,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
        delay=True,  # open on first emit -> smaller Windows rename-on-rollover window
    )
    handler._swing_surface = surface  # type: ignore[attr-defined]  # tag (§3.4)
    handler.setLevel(logging.NOTSET)  # R4-major-1: thresholding lives on root, not here
    # Formatter BEFORE addHandler -> no unredacted window.
    handler.setFormatter(
        formatter if formatter is not None else logging.Formatter(DEFAULT_LOG_FORMAT)
    )
    if record_filter is not None:
        _replace_swing_filter(handler, record_filter)
    root.addHandler(handler)
