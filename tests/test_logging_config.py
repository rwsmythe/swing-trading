# tests/test_logging_config.py
from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler

import pytest

from swing.logging_config import DEFAULT_LOG_FORMAT, configure_logging


@pytest.fixture
def clean_root():
    root = logging.getLogger()
    saved = list(root.handlers)
    saved_level = root.level
    for h in list(root.handlers):
        root.removeHandler(h)
    yield root
    for h in list(root.handlers):
        if isinstance(h, TimedRotatingFileHandler):
            h.close()
        root.removeHandler(h)
    for h in saved:
        root.addHandler(h)
    root.setLevel(saved_level)


def _file_handlers(root, target):
    return [
        h for h in root.handlers
        if isinstance(h, TimedRotatingFileHandler) and h.baseFilename == str(target)
    ]


def test_pipeline_surface_attaches_named_handler(clean_root, tmp_path):
    configure_logging(tmp_path, surface="pipeline")
    target = tmp_path / "pipeline.log"
    handlers = _file_handlers(clean_root, target)
    assert len(handlers) == 1
    assert handlers[0].backupCount == 7
    assert clean_root.level == logging.INFO


def test_web_surface_matches_legacy_filename(clean_root, tmp_path):
    configure_logging(tmp_path, surface="web")
    assert _file_handlers(clean_root, tmp_path / "web.log")


def test_invalid_surface_rejected(clean_root, tmp_path):
    with pytest.raises(ValueError):
        configure_logging(tmp_path, surface="bogus")


def test_idempotent_dedup_by_basefilename(clean_root, tmp_path):
    configure_logging(tmp_path, surface="pipeline")
    configure_logging(tmp_path, surface="pipeline")
    assert len(_file_handlers(clean_root, tmp_path / "pipeline.log")) == 1


def test_dedup_path_still_sets_root_level(clean_root, tmp_path):
    # A same-file handler already exists AND root is at WARNING (e.g. attached by a
    # prior call / another lib). The dedup early-return MUST still lower root to INFO,
    # else pipeline INFO per-step lines stay suppressed.
    configure_logging(tmp_path, surface="pipeline")
    clean_root.setLevel(logging.WARNING)  # simulate a stale/raised level
    configure_logging(tmp_path, surface="pipeline")  # hits the dedup path
    assert clean_root.level == logging.INFO


def test_supplied_formatter_installs_on_preexisting_handler(clean_root, tmp_path):
    # First call: default formatter, no override.
    configure_logging(tmp_path, surface="pipeline")
    target = tmp_path / "pipeline.log"
    handler = _file_handlers(clean_root, target)[0]
    assert handler.formatter._fmt == DEFAULT_LOG_FORMAT

    # Second call supplies a distinct formatter: R2-Major-2 — must setFormatter,
    # not silently return with the old default in place.
    marker = logging.Formatter("REDACTED %(message)s")
    configure_logging(tmp_path, surface="pipeline", formatter=marker)
    assert len(_file_handlers(clean_root, target)) == 1  # still deduped
    assert handler.formatter is marker
