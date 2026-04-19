"""JournalVM + builder."""
from __future__ import annotations


def test_build_journal_default_period_month(seeded_db):
    from swing.web.view_models.journal import JournalVM, build_journal
    cfg, _ = seeded_db
    vm = build_journal(cfg=cfg, period="month")
    assert isinstance(vm, JournalVM)
    assert vm.period == "month"
    # Empty DB -> stats show zeros.
    assert vm.stats.n_trades == 0


def test_build_journal_rejects_unknown_period(seeded_db):
    from swing.web.view_models.journal import build_journal
    import pytest
    cfg, _ = seeded_db
    with pytest.raises(ValueError, match="period"):
        build_journal(cfg=cfg, period="fortnight")
