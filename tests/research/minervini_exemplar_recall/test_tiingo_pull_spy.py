# tests/research/minervini_exemplar_recall/test_tiingo_pull_spy.py
from __future__ import annotations

from research.harness.minervini_exemplar_recall.tiingo_pull import unique_symbols


def test_spy_always_included_even_when_no_exemplar_carries_it():
    rows = [
        {"exemplar_id": "a", "ticker": "CRUS", "entry_date": "2010-03-30"},
        {"exemplar_id": "b", "ticker": "EMEX", "entry_date": "2001"},  # -> ELX
    ]
    syms = unique_symbols(rows)
    # WRONG-PATH (no SPY injection): {'CRUS', 'ELX'}.  RIGHT-PATH: SPY present.
    assert "SPY" in syms
    assert "CRUS" in syms and "ELX" in syms
    assert syms == sorted(syms)  # stable deterministic ordering
