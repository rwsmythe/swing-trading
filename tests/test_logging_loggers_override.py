from __future__ import annotations

import logging

from swing.config import _parse_logging_config


def test_happy_path_resolves_logger_levels():
    cfg = _parse_logging_config({
        "level": "INFO",
        "loggers": {"httpx": "WARNING", "yfinance": "ERROR"},
    })
    levels = cfg.resolved_logger_levels()
    assert levels == {"httpx": logging.WARNING, "yfinance": logging.ERROR}
    assert cfg.warnings == ()  # no diagnostics on a clean table


def test_malformed_entry_skipped_with_diagnostic():
    cfg = _parse_logging_config({
        "loggers": {"httpx": "WARNING", "bad": "LOUD", "alsobad": 5},
    })
    levels = cfg.resolved_logger_levels()
    assert levels == {"httpx": logging.WARNING}  # bad entries skipped
    joined = " ".join(cfg.warnings)
    assert "'bad'" in joined and "LOUD" in joined
    assert "'alsobad'" in joined


def test_non_table_loggers_value_diagnostic():
    cfg = _parse_logging_config({"loggers": "not-a-table"})
    assert cfg.resolved_logger_levels() == {}
    assert any("loggers" in w and "table" in w for w in cfg.warnings)


def test_absent_loggers_table_is_empty_no_warning():
    cfg = _parse_logging_config({"level": "INFO"})
    assert cfg.resolved_logger_levels() == {}
    assert cfg.warnings == ()


def test_resolved_logger_levels_returns_copy():
    cfg = _parse_logging_config({"loggers": {"httpx": "WARNING"}})
    m = cfg.resolved_logger_levels()
    m["httpx"] = logging.DEBUG  # mutate the returned dict
    assert cfg.resolved_logger_levels() == {"httpx": logging.WARNING}  # source intact
