"""Neutral logging seam shared by the web app and the pipeline CLI subprocess.

Top-level (not under swing.web or swing.cli) so neither importer pulls in the
other. Schwab-agnostic by construction: it imports nothing from
swing.integrations.schwab -- the secret-bearing CLI surface injects a
RedactingFormatter via the `formatter` parameter (see Arc-1 spec §4.2).
"""
from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def configure_logging(
    logs_dir: Path,
    *,
    surface: str,
    level: int = logging.INFO,
    formatter: logging.Formatter | None = None,
) -> None:
    """Attach a TimedRotatingFileHandler writing ``{surface}.log`` to the root logger.

    Idempotent (dedup by baseFilename). ``surface`` in {'web', 'pipeline'}.
    When ``formatter`` is supplied AND a same-file handler already exists, the
    formatter is installed onto that handler (R2-Major-2) -- never silently
    skipped. The formatter is set on the handler BEFORE it is added to root, so
    there is no unredacted window. ``level`` exists for Arc-2a to wire a knob
    later without changing the signature; default stays INFO.
    """
    if surface not in {"web", "pipeline"}:
        raise ValueError(f"surface must be 'web' or 'pipeline', got {surface!r}")
    logs_dir.mkdir(parents=True, exist_ok=True)
    target = str(Path(logs_dir) / f"{surface}.log")
    root = logging.getLogger()
    # Set the level on EVERY path (including dedup) -- if a prior handler was
    # attached while root was at WARNING, the pipeline surface's INFO per-step lines
    # would otherwise stay suppressed.
    root.setLevel(level)
    for h in root.handlers:
        if isinstance(h, TimedRotatingFileHandler) and h.baseFilename == target:
            if formatter is not None:
                h.setFormatter(formatter)
            return
    handler = TimedRotatingFileHandler(
        filename=target, when="D", interval=1, backupCount=7, encoding="utf-8",
    )
    handler.setFormatter(
        formatter if formatter is not None else logging.Formatter(DEFAULT_LOG_FORMAT)
    )
    root.addHandler(handler)
