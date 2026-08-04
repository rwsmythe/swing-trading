"""D29 -- the FOUR cohort readers apply the intent-facet predicate.

A partial fix is the defect: a two-site fix leaves H1 evidence
contradicting itself across surfaces with one of the unfixed pair driving
TRIPWIRE arithmetic. So all four readers are pinned in ONE file, each
against the SAME seeded shape, plus the discriminating non-H1 half that a
blanket single-authority filter would fail.

Seeded H1 shape (mirrors the live defect: 2 standard + 1 pre-epoch
by_design):
  * ``AAA`` standard, +1R (pnl +$100), closed 2026-04-01
  * ``BBB`` standard, +1R (pnl +$100), closed 2026-04-02
  * ``ZZZ`` hypothesis_test_by_design, -3R (pnl -$300), closed 2026-04-03

Pre-fix vs post-fix, computed under BOTH paths so the assertions
distinguish:
  * n_closed / current_sample: 3  ->  2
  * mean R:                (1 + 1 - 3) / 3 = -0.3333  ->  +1.0
  * cumulative P&L:        -$100  ->  +$200
  * consecutive-loss streak (walks entry_date DESC): 1  ->  0
"""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest

from swing.config import load as load_config
from swing.data.db import ensure_schema
from swing.journal.stats import compute_hypothesis_progress_breakdown
from swing.metrics.cohort import list_closed_trades_for_cohort
from swing.metrics.cohort_intent import (
    cohort_entry_intent,
    trade_counts_toward_cohort,
)
from swing.metrics.tier import APLUS_COHORT, compute_tier_comparison
from swing.recommendations.hypothesis import compute_tripwire_status
from swing.web.view_models.metrics.hypothesis_progress_card import (
    build_hypothesis_progress_card_vm,
)

_H2_COHORT = "Near-A+ defensible: extension test"


@pytest.fixture
def cfg(tmp_path: Path):
    db_path = tmp_path / "d29_readers.db"
    ensure_schema(db_path).close()
    base_cfg = load_config(Path("swing.config.toml"))
    return dc_replace(
        base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path),
    )


@pytest.fixture
def conn(cfg) -> sqlite3.Connection:
    return sqlite3.connect(cfg.paths.db_path)


def _seed(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str,
    label: str,
    entry_intent: str | None,
    pnl: float,
    entry_date: str,
    state: str = "closed",
) -> None:
    """entry=$10, stop=$9, 100 shares => risk_budget $100, so R = pnl/100."""
    exit_price = 10.0 + (pnl / 100.0)
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "hypothesis_label, entry_intent, risk_policy_id_at_lock, "
        "last_fill_at) VALUES (?, ?, ?, 10.0, 100, 9.0, 9.0, ?, 'S', 'I', "
        "'manual_off_pipeline', ?, 100, ?, ?, 1, ?)",
        (
            trade_id, ticker, entry_date, state,
            entry_date + "T09:30:00", label, entry_intent,
            entry_date + "T15:30:00",
        ),
    )
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
        "price, reconciliation_status) VALUES "
        "(?, ?, 'entry', 100, 10.0, 'unreconciled')",
        (trade_id, entry_date + "T09:30:00"),
    )
    if state in ("closed", "reviewed"):
        conn.execute(
            "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
            "price, reconciliation_status) VALUES "
            "(?, ?, 'exit', 100, ?, 'unreconciled')",
            (trade_id, entry_date + "T15:30:00", exit_price),
        )
    conn.commit()


def _seed_h1_shape(conn: sqlite3.Connection) -> None:
    _seed(conn, trade_id=1, ticker="AAA", label=APLUS_COHORT,
          entry_intent="standard", pnl=100.0, entry_date="2026-04-01")
    _seed(conn, trade_id=2, ticker="BBB", label=APLUS_COHORT,
          entry_intent="standard", pnl=100.0, entry_date="2026-04-02")
    _seed(conn, trade_id=3, ticker="ZZZ", label=APLUS_COHORT,
          entry_intent="hypothesis_test_by_design", pnl=-300.0,
          entry_date="2026-04-03")


def _h1_id(conn: sqlite3.Connection) -> int:
    (hid,) = conn.execute(
        "SELECT id FROM hypothesis_registry WHERE name = ?", (APLUS_COHORT,),
    ).fetchone()
    return int(hid)


# ---------------------------------------------------------------------------
# Reader 1 -- swing/metrics/tier.py (tier-comparison + deviation-outcome)
# ---------------------------------------------------------------------------

def test_tier_comparison_excludes_by_design_from_h1(conn: sqlite3.Connection):
    _seed_h1_shape(conn)
    result = compute_tier_comparison(conn)
    aplus = next(c for c in result.cohorts if c.cohort_name == APLUS_COHORT)
    assert aplus.n_closed == 2  # pre-fix: 3
    assert aplus.n_wins == 2
    assert aplus.n_losses == 0  # pre-fix: 1 (the -3R by_design trade)
    assert sorted(aplus.samples_R) == [1.0, 1.0]  # pre-fix includes -3.0


# ---------------------------------------------------------------------------
# Reader 2 -- swing/web/view_models/metrics/hypothesis_progress_card.py
# ---------------------------------------------------------------------------

def test_progress_card_excludes_by_design_from_h1(
    conn: sqlite3.Connection, cfg,
):
    _seed_h1_shape(conn)
    vm = build_hypothesis_progress_card_vm(cfg=cfg, conn=conn)
    aplus = next(c for c in vm.cohorts if c.cohort_name == APLUS_COHORT)
    assert aplus.n_closed == 2  # pre-fix: 3
    # cumulative_R_pct_of_capital sums net_pnl / at-trade-time capital
    # floor: pre-fix (100 + 100 - 300) = -$100 -> negative; post-fix
    # (100 + 100) = +$200 -> positive.
    assert aplus.cumulative_R_pct_of_capital > 0
    # The by_design loser was the most recent close, so pre-fix the
    # consecutive-loss run is 1; post-fix it is 0.
    assert aplus.consecutive_loss_run == 0


# ---------------------------------------------------------------------------
# Reader 3 -- swing/recommendations/hypothesis.py (sample + TRIPWIRE math)
# ---------------------------------------------------------------------------

def test_tripwire_status_excludes_by_design_from_h1(conn: sqlite3.Connection):
    _seed_h1_shape(conn)
    tw = compute_tripwire_status(
        conn, hypothesis_id=_h1_id(conn), starting_equity=7500.0,
    )
    assert tw.current_sample == 2  # pre-fix: 3 -- the live `swing
    #                                 hypothesis list` 3/20 vs 2/20 defect
    assert tw.cumulative_loss == pytest.approx(200.0)  # pre-fix: -100.0
    assert tw.consecutive_max_loss_streak == 0  # pre-fix: 1


# ---------------------------------------------------------------------------
# Reader 4 -- swing/journal/stats.py (journal / dashboard n, mean R, win rate)
# ---------------------------------------------------------------------------

def test_journal_progress_breakdown_excludes_by_design_from_h1(
    conn: sqlite3.Connection,
):
    _seed_h1_shape(conn)
    rows = compute_hypothesis_progress_breakdown(conn, starting_equity=7500.0)
    aplus = next(r for r in rows if r.name == APLUS_COHORT)
    assert aplus.current_sample == 2  # pre-fix: 3
    assert aplus.mean_r_multiple == pytest.approx(1.0)  # pre-fix: -0.33333
    # win_rate suppresses below n=3; pre-fix n was 3 and would have
    # reported 2/3 -- post-fix n=2 suppresses.
    assert aplus.win_rate is None


def test_journal_in_flight_count_excludes_by_design_from_h1(
    conn: sqlite3.Connection,
):
    """Codex R7: seeds BOTH intents. With only the excluded trade present,
    an implementation that dropped every open H1 trade would also have
    passed -- the assertion has to separate the two, not just count zero."""
    _seed(conn, trade_id=10, ticker="OPN", label=APLUS_COHORT,
          entry_intent="hypothesis_test_by_design", pnl=0.0,
          entry_date="2026-04-05", state="managing")
    _seed(conn, trade_id=11, ticker="OPS", label=APLUS_COHORT,
          entry_intent="standard", pnl=0.0,
          entry_date="2026-04-06", state="managing")
    rows = compute_hypothesis_progress_breakdown(conn, starting_equity=7500.0)
    aplus = next(r for r in rows if r.name == APLUS_COHORT)
    assert aplus.in_flight_sample == 1  # pre-fix: 2


# ---------------------------------------------------------------------------
# The discriminating half -- a BLANKET single-authority filter fails these
# ---------------------------------------------------------------------------

def test_non_h1_cohorts_still_count_their_by_design_program_fires(
    conn: sqlite3.Connection, cfg,
):
    """The epoch contract's forward intent clause names H2/H4 by_design
    fires as legitimate program samples. A blanket ``standard``-only
    filter would zero them (and retroactively un-achieve H3's
    closed-target-met status)."""
    _seed(conn, trade_id=20, ticker="H2A", label=_H2_COHORT,
          entry_intent="hypothesis_test_by_design", pnl=50.0,
          entry_date="2026-04-01")
    _seed(conn, trade_id=21, ticker="H2B", label=_H2_COHORT,
          entry_intent=None, pnl=50.0, entry_date="2026-04-02")

    (h2_id,) = conn.execute(
        "SELECT id FROM hypothesis_registry WHERE name = ?", (_H2_COHORT,),
    ).fetchone()
    tw = compute_tripwire_status(
        conn, hypothesis_id=int(h2_id), starting_equity=7500.0,
    )
    assert tw.current_sample == 2

    rows = compute_hypothesis_progress_breakdown(conn, starting_equity=7500.0)
    h2 = next(r for r in rows if r.name == _H2_COHORT)
    assert h2.current_sample == 2

    tier = compute_tier_comparison(conn)
    h2_tier = next(c for c in tier.cohorts if c.cohort_name == _H2_COHORT)
    assert h2_tier.n_closed == 2

    vm = build_hypothesis_progress_card_vm(cfg=cfg, conn=conn)
    h2_card = next(c for c in vm.cohorts if c.cohort_name == _H2_COHORT)
    assert h2_card.n_closed == 2


def test_h1_unclassified_intent_does_not_count_at_ANY_of_the_four(  # noqa: N802
    conn: sqlite3.Connection, cfg,
):
    """NULL entry_intent is a distinct third facet, never coerced to
    'standard' -- so it is not a STANDARD-intent trade under the
    criterion's cohort clause.

    Codex R1 Minor 4: asserted at ALL FOUR readers, not just the tripwire
    one. The repaired fixtures default to 'standard', so this is where the
    NULL case keeps its coverage at each surface.
    """
    _seed(conn, trade_id=30, ticker="NUL", label=APLUS_COHORT,
          entry_intent=None, pnl=100.0, entry_date="2026-04-01")

    tw = compute_tripwire_status(
        conn, hypothesis_id=_h1_id(conn), starting_equity=7500.0,
    )
    assert tw.current_sample == 0  # pre-fix: 1

    tier = compute_tier_comparison(conn)
    aplus = next(c for c in tier.cohorts if c.cohort_name == APLUS_COHORT)
    assert aplus.n_closed == 0  # pre-fix: 1

    rows = compute_hypothesis_progress_breakdown(conn, starting_equity=7500.0)
    journal_aplus = next(r for r in rows if r.name == APLUS_COHORT)
    assert journal_aplus.current_sample == 0  # pre-fix: 1

    vm = build_hypothesis_progress_card_vm(cfg=cfg, conn=conn)
    card_aplus = next(c for c in vm.cohorts if c.cohort_name == APLUS_COHORT)
    assert card_aplus.n_closed == 0  # pre-fix: 1


def test_tier_applies_no_narrowing_when_the_h1_row_is_not_registered(
    conn: sqlite3.Connection,
):
    """Codex R5 -- `tier.py` is the one reader iterating a FIXED cohort tuple
    rather than live registry rows, so it is the only place the criterion
    mapping could outlive the row that justifies it.

    A criterion is a property of a registry ROW. With the row gone the
    criterion is gone with it and no narrowing applies -- the same answer
    `cohort_intent_authority` gives for an unregistered name. Unreachable
    through any production write path (the sole runtime writer,
    `swing/trades/hypothesis.py:270`, UPDATEs status columns only), so the
    row is removed here by RAW SQL, exactly as a detection test plants
    historical bad data.
    """
    _seed_h1_shape(conn)
    conn.execute(
        "DELETE FROM hypothesis_registry WHERE name = ?", (APLUS_COHORT,),
    )
    conn.commit()

    result = compute_tier_comparison(conn)
    aplus = next(c for c in result.cohorts if c.cohort_name == APLUS_COHORT)
    # All three labeled trades count: with no registry row there is no
    # criterion, so nothing mandates the standard-only cohort clause.
    assert aplus.n_closed == 3
    assert aplus.decision_criteria == ""


def test_sql_and_in_memory_predicates_select_the_SAME_trades(  # noqa: N802
    conn: sqlite3.Connection,
):
    """Codex R7 -- parity asserted through the PRODUCTION SELECT, not just
    between two policy return values.

    Two readers narrow in SQL (``list_closed_trades_for_cohort``) and two
    narrow in Python (``trade_counts_toward_cohort``). The module claims
    they cannot drift; this runs both over the same seeded rows and
    compares trade ids, in BOTH the registered and unregistered states.
    """
    _seed_h1_shape(conn)
    _seed(conn, trade_id=4, ticker="NUL", label=APLUS_COHORT,
          entry_intent=None, pnl=50.0, entry_date="2026-04-04")

    all_labeled = list_closed_trades_for_cohort(
        conn, hypothesis_label=APLUS_COHORT,
    )
    assert len(all_labeled) == 4  # standard x2, by_design, unclassified

    for registered in ([APLUS_COHORT], []):
        sql_selected = {
            t.id for t in list_closed_trades_for_cohort(
                conn,
                hypothesis_label=APLUS_COHORT,
                entry_intent=cohort_entry_intent(
                    APLUS_COHORT, registered_names=registered,
                ),
            )
        }
        python_selected = {
            t.id for t in all_labeled
            if trade_counts_toward_cohort(
                entry_intent=t.entry_intent,
                hypothesis_name=APLUS_COHORT,
                registered_names=registered,
            )
        }
        assert sql_selected == python_selected, registered

    # And the two states are genuinely DIFFERENT, so the parity above is
    # not two identical trivial answers.
    registered_ids = {
        t.id for t in list_closed_trades_for_cohort(
            conn,
            hypothesis_label=APLUS_COHORT,
            entry_intent=cohort_entry_intent(
                APLUS_COHORT, registered_names=[APLUS_COHORT],
            ),
        )
    }
    assert len(registered_ids) == 2
