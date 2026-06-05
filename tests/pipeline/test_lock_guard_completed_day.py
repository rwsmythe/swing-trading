# tests/pipeline/test_lock_guard_completed_day.py
from datetime import date

import pytest

import swing.pipeline.runner as runner
from tests.pipeline.conftest_temporal import _cfg


def runner_cfg_stub(tmp_path):
    """Minimal cfg exposing paths.prices_cache_dir (+ db_path), reusing the
    project's temporal-test cfg factory."""
    return _cfg(tmp_path, tmp_path / "swing.db")


def test_bar_for_date_rejects_current_day(monkeypatch, tmp_path):
    """L3 date-only guard: _bar_for_date must refuse an observation_date that
    is not <= last_completed_session(now). Catches a wiring regression that
    would lock a partial/in-progress bar."""
    monkeypatch.setattr(runner, "last_completed_session",
                        lambda *_a, **_k: date(2026, 6, 4))

    class _Cache:
        def get_or_fetch(self, **k):
            raise AssertionError("must raise BEFORE any fetch")

    cfg = runner_cfg_stub(tmp_path)  # minimal cfg with paths.prices_cache_dir
    with pytest.raises(ValueError, match="not a completed session"):
        runner._bar_for_date(cfg, _Cache(), "AAPL", "2026-06-05")


def test_bar_for_date_allows_completed_day(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "last_completed_session",
                        lambda *_a, **_k: date(2026, 6, 4))
    # A completed-day observation_date passes the guard (then proceeds to the
    # normal archive read, which returns None for an empty cache -> acceptable).
    cfg = runner_cfg_stub(tmp_path)

    class _Cache:
        def get_or_fetch(self, **k):
            return None
    assert runner._bar_for_date(cfg, _Cache(), "AAPL", "2026-06-04") is None
