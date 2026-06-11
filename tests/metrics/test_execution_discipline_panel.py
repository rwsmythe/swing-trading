"""Task 6 — the always-on execution-discipline panel orthogonality guarantee.

Spec §7.1 binding contract: the execution-discipline panel is computed over
the cohort's reviewed trades WITHOUT the intent filter applied, restricted to
the risk + reconciliation mistake-tag categories (genuine slips). Toggling the
intent facet MUST NOT change the panel — that is what makes a genuine
risk/reconciliation slip impossible to hide behind an intent facet.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.metrics.process import compute_trade_process_metrics


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "exec_discipline.db")


def _seed_reviewed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str,
    entry_intent: str | None,
    mistake_tags: list[str],
) -> None:
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "hypothesis_label, last_fill_at, reviewed_at, mistake_tags, "
        "entry_intent) VALUES "
        "(?, ?, '2026-04-01', 10.0, 100, 9.0, 9.0, 'closed', 'S', 'I', "
        "'manual_off_pipeline', '2026-04-01T09:30:00', 100, NULL, "
        "'2026-04-08T15:30:00', '2026-04-10T09:00:00', ?, ?)",
        (trade_id, ticker, json.dumps(mistake_tags), entry_intent),
    )
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
        "price, reconciliation_status) VALUES "
        "(?, '2026-04-01T09:30:00', 'entry', 100, 10.0, 'unreconciled')",
        (trade_id,),
    )
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
        "price, reconciliation_status) VALUES "
        "(?, '2026-04-08T15:30:00', 'exit', 100, 12.0, 'unreconciled')",
        (trade_id,),
    )
    conn.commit()


def test_execution_discipline_panel_is_intent_independent(
    conn: sqlite3.Connection,
) -> None:
    """The panel + its denominator are byte-identical across every intent
    filter state (None / standard / hypothesis_test_by_design)."""
    # A by_design VIR-like trade carrying genuine risk + reconciliation slips.
    _seed_reviewed_trade(
        conn, trade_id=1, ticker="VIR",
        entry_intent="hypothesis_test_by_design",
        mistake_tags=["NO_STOP", "STOP_NOT_PLACED"],
    )
    # Two standard trades carrying CHASED (an entry-category tuition tag).
    _seed_reviewed_trade(
        conn, trade_id=2, ticker="STD1",
        entry_intent="standard", mistake_tags=["CHASED"],
    )
    _seed_reviewed_trade(
        conn, trade_id=3, ticker="STD2",
        entry_intent="standard", mistake_tags=["CHASED"],
    )

    base = compute_trade_process_metrics(conn, hypothesis_label=None)
    std = compute_trade_process_metrics(
        conn, hypothesis_label=None, entry_intent="standard")
    bd = compute_trade_process_metrics(
        conn, hypothesis_label=None,
        entry_intent="hypothesis_test_by_design")

    # The panel + its denominator are IDENTICAL across every filter state.
    for m in (std, bd):
        assert (
            m.execution_discipline_n_reviewed
            == base.execution_discipline_n_reviewed
        )
        assert (
            set(m.execution_discipline_tag_frequency)
            == set(base.execution_discipline_tag_frequency)
        )
        for tag, cell in base.execution_discipline_tag_frequency.items():
            assert m.execution_discipline_tag_frequency[tag].sample_n == cell.sample_n
            assert (
                m.execution_discipline_tag_frequency[tag].events_k
                == cell.events_k
            )

    # The genuine risk/reconciliation slips are present...
    assert "NO_STOP" in base.execution_discipline_tag_frequency
    assert "STOP_NOT_PLACED" in base.execution_discipline_tag_frequency
    # ...and the entry-category tuition tag is NOT (panel = risk/reconciliation).
    assert "CHASED" not in base.execution_discipline_tag_frequency

    # The panel denominator is the intent-UNFILTERED reviewed count.
    # All 3 trades are reviewed → panel n == 3.
    assert base.execution_discipline_n_reviewed == 3
    # No filter → panel denominator equals n_reviewed.
    assert base.execution_discipline_n_reviewed == base.n_reviewed
    # Filtering shrinks n_reviewed only; the panel denominator stays whole.
    assert std.execution_discipline_n_reviewed >= std.n_reviewed
    assert std.n_reviewed == 2  # only the 2 standard reviewed trades
    assert bd.n_reviewed == 1  # only the by_design reviewed trade


def test_execution_discipline_panel_excludes_management_and_psych_tags(
    conn: sqlite3.Connection,
) -> None:
    """The panel is restricted to risk + reconciliation categories ONLY;
    management/psychology/entry tuition tags do not appear."""
    _seed_reviewed_trade(
        conn, trade_id=1, ticker="A", entry_intent="standard",
        mistake_tags=["OVERSIZED", "SOLD_TOO_EARLY", "FOMO", "NO_SETUP"],
    )
    base = compute_trade_process_metrics(conn, hypothesis_label=None)
    freq = base.execution_discipline_tag_frequency
    assert "OVERSIZED" in freq  # risk category -> present
    assert "SOLD_TOO_EARLY" not in freq  # management -> excluded
    assert "FOMO" not in freq  # psychology -> excluded
    assert "NO_SETUP" not in freq  # entry tuition -> excluded
