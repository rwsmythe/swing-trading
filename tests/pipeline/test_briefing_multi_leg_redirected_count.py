"""Phase 12.5 #1 T-1.11 — briefing.md "Reconciliation status" widening
for the multi-leg auto-redirect counter.

Plan §A T-1.11 + spec §11.2 + F22 LOCK. Three changes land together:

  * ``BriefingInputs`` gains
    ``reconciliation_tier1_multi_leg_redirected_count: int = 0``.
  * ``BriefingViewModel`` gains the same field threaded through
    ``build_briefing_view_model``.
  * ``render_briefing_md`` widens the section-emit predicate to include
    the new counter AND inserts the new line **"- Multi-leg
    auto-redirects applied this run: K"** IMMEDIATELY BEFORE the
    existing tier-1-recent line WHEN K > 0.

F22 binding wording: "applied this run" verbatim — NOT "(last 7 days)".

The runner-side wiring is exercised via the existing T-1.7 helper
``count_recent_multi_leg_auto_corrections`` (DISTINCT-discrepancy
semantic per F18).
"""
from __future__ import annotations

import dataclasses
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.reconciliation import insert_discrepancy, insert_run
from swing.metrics.discrepancies import count_recent_multi_leg_auto_corrections
from swing.rendering.briefing import BriefingInputs, build_briefing_view_model
from swing.rendering.briefing_md import render_briefing_md
from swing.rendering.view_models import (
    AccountTileVM,
    BriefingViewModel,
    PipelineTileVM,
    StatusStripVM,
    WeatherTileVM,
)


def _make_vm(
    *,
    reconciliation_pending_count: int = 0,
    reconciliation_tier1_recent_count: int = 0,
    reconciliation_tier1_multi_leg_redirected_count: int = 0,
) -> BriefingViewModel:
    return BriefingViewModel(
        action_session_date="2026-05-16",
        data_asof_date="2026-05-15",
        generated_at="2026-05-16T08:00:00",
        status_strip=StatusStripVM(
            weather=WeatherTileVM(
                status="Bullish",
                rationale="clear",
                sizing_implication="full sizing OK",
            ),
            account=AccountTileVM(
                equity=2000.0, open_count=0, soft_warn=4, hard_cap=6,
            ),
            pipeline=PipelineTileVM(
                last_run_ts="2026-05-15T17:00:00",
                is_stale=False,
                current_session_match=True,
            ),
        ),
        reconciliation_pending_count=reconciliation_pending_count,
        reconciliation_tier1_recent_count=reconciliation_tier1_recent_count,
        reconciliation_tier1_multi_leg_redirected_count=(
            reconciliation_tier1_multi_leg_redirected_count
        ),
    )


def test_briefing_inputs_has_new_counter_field() -> None:
    """``BriefingInputs.reconciliation_tier1_multi_leg_redirected_count``
    exists with safe default 0."""
    names = {f.name for f in dataclasses.fields(BriefingInputs)}
    assert "reconciliation_tier1_multi_leg_redirected_count" in names


def test_briefing_view_model_has_new_counter_field() -> None:
    """``BriefingViewModel`` mirrors the new counter field."""
    names = {f.name for f in dataclasses.fields(BriefingViewModel)}
    assert "reconciliation_tier1_multi_leg_redirected_count" in names


def test_briefing_md_emits_multi_leg_line_when_count_gt_zero() -> None:
    """F22 LOCK — verbatim wording "applied this run" (NOT "last 7 days").

    Line placement: IMMEDIATELY BEFORE the tier-1-recent line.
    """
    md = render_briefing_md(
        _make_vm(reconciliation_tier1_multi_leg_redirected_count=3)
    )
    assert "## Reconciliation status" in md
    assert "- Multi-leg auto-redirects applied this run: 3" in md
    # F22 wording check — must NOT paraphrase to "last 7 days" on the
    # multi-leg line.
    multi_leg_line_idx = md.index("Multi-leg auto-redirects")
    multi_leg_line_end = md.index("\n", multi_leg_line_idx)
    multi_leg_line = md[multi_leg_line_idx:multi_leg_line_end]
    assert "last 7 days" not in multi_leg_line
    assert "(this run)" not in multi_leg_line  # NOT the brief's paraphrase
    # Placement: the multi-leg line appears BEFORE the existing tier-1
    # auto-corrected (last 7 days) line.
    tier1_idx = md.index("Tier-1 auto-corrected (last 7 days)")
    assert multi_leg_line_idx < tier1_idx


def test_briefing_md_omits_multi_leg_line_when_count_zero() -> None:
    """K=0 → no multi-leg line emitted; section still emits because
    pending > 0."""
    md = render_briefing_md(
        _make_vm(
            reconciliation_pending_count=2,
            reconciliation_tier1_multi_leg_redirected_count=0,
        )
    )
    assert "## Reconciliation status" in md
    assert "Multi-leg auto-redirects" not in md


def test_briefing_md_omits_section_entirely_when_all_three_counters_zero() -> None:
    """All three counters zero → section header itself absent."""
    md = render_briefing_md(_make_vm())
    assert "## Reconciliation status" not in md
    assert "Multi-leg auto-redirects" not in md


def test_briefing_md_renders_section_when_only_multi_leg_count_nonzero() -> None:
    """Section MUST emit when the multi-leg counter is the ONLY non-zero
    counter — widens existing predicate to include the new counter."""
    md = render_briefing_md(
        _make_vm(reconciliation_tier1_multi_leg_redirected_count=2)
    )
    assert "## Reconciliation status" in md
    assert "- Multi-leg auto-redirects applied this run: 2" in md


def test_build_briefing_view_model_threads_new_counter() -> None:
    """View-model construction copies the new counter byte-for-byte from
    BriefingInputs → BriefingViewModel."""
    inputs = BriefingInputs(
        action_session_date="2026-05-16",
        data_asof_date="2026-05-15",
        generated_at="2026-05-16T08:00:00",
        weather=None,
        weather_is_stale=True,
        equity=2000.0,
        open_count=0,
        soft_warn=4,
        hard_cap=6,
        last_pipeline_ts="2026-05-15T17:00:00",
        pipeline_is_stale=False,
        current_session_match=True,
        recommendations=[],
        open_trades=[],
        reconciliation_tier1_multi_leg_redirected_count=5,
    )
    vm = build_briefing_view_model(inputs)
    assert vm.reconciliation_tier1_multi_leg_redirected_count == 5


# ---------------------------------------------------------------------------
# Runner integration — DISTINCT-discrepancy semantic (F18) via shared helper.
# Verifies the runner-style wiring of count_recent_multi_leg_auto_corrections
# into the BriefingInputs.reconciliation_tier1_multi_leg_redirected_count
# slot honors banner-clears semantic (only the LATEST completed run counts).
# ---------------------------------------------------------------------------


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "phase12_5_briefing_runner_count.db")


def _seed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str = "TST",
) -> None:
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "hypothesis_label) VALUES (?, ?, '2026-05-12', 10.0, 100, "
        "9.0, 9.0, 'entered', 'S', 'I', 'manual_off_pipeline', "
        "'2026-05-12T09:00:00.000', 100, 'A+ baseline')",
        (trade_id, ticker),
    )
    conn.commit()


def _emit_multi_leg_discrepancy(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    trade_id: int,
    n_partials: int = 3,
) -> int:
    """Emit ONE discrepancy resolved via multi-leg auto-redirect with
    (1 anchor + n_partials) correction rows.  F18 LOCK: COUNT(DISTINCT
    discrepancy_id) must collapse the N+1 rows down to 1."""
    did = insert_discrepancy(
        conn,
        run_id=run_id,
        discrepancy_type="unmatched_open_fill",
        field_name="fill_match",
        material_to_review=1,
        created_at="2026-05-12T09:00:00.000",
        trade_id=trade_id,
        ticker="TST",
        resolution="unresolved",
    )
    conn.execute(
        "UPDATE reconciliation_discrepancies SET "
        "resolution = ?, ambiguity_kind = ?, "
        "resolved_by = ?, resolved_at = ? WHERE discrepancy_id = ?",
        (
            "operator_resolved_ambiguity",
            "multi_partial_vs_consolidated",
            "auto_tier1_multi_leg",
            "2026-05-12T09:00:00.500",
            did,
        ),
    )
    # 1 anchor (__delete__) + N partials (__insert__).
    conn.execute(
        "INSERT INTO reconciliation_corrections ("
        "discrepancy_id, correction_action, correction_choice, "
        "affected_table, affected_row_id, field_name, "
        "pre_correction_value_json, applied_value_json, applied_at, "
        "applied_by, reconciliation_run_id"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            did, "operator_resolved_ambiguity", "split_into_partials",
            "fills", 10, "__delete__",
            '{"price": 5.30}', '{"price": 5.30}',
            "2026-05-12T09:00:00.600", "auto", run_id,
        ),
    )
    for i in range(n_partials):
        conn.execute(
            "INSERT INTO reconciliation_corrections ("
            "discrepancy_id, correction_action, correction_choice, "
            "affected_table, affected_row_id, field_name, "
            "pre_correction_value_json, applied_value_json, applied_at, "
            "applied_by, reconciliation_run_id"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                did, "operator_resolved_ambiguity", "split_into_partials",
                "fills", 11 + i, "__insert__",
                '{"price": 5.30}', '{"price": 5.30}',
                "2026-05-12T09:00:00.600", "auto", run_id,
            ),
        )
    conn.commit()
    return did


def test_runner_reconciliation_tier1_multi_leg_redirected_count_distinct_semantics(
    conn: sqlite3.Connection,
) -> None:
    """Plant 1 multi-leg discrepancy with 4 correction rows on the LATEST
    completed run; counter == 1 (NOT 4) — F18 LOCK.

    Discriminating: plant a SECOND multi-leg discrepancy with 4 rows on a
    PRIOR completed run; counter STILL == 1 — banner-clears semantic per
    spec §8.4 + §11.2 LOCK; only the most-recent run counts.
    """
    _seed_trade(conn, trade_id=1)
    _seed_trade(conn, trade_id=2, ticker="TS2")

    # PRIOR run with its own multi-leg discrepancy (would inflate to 4 under
    # COUNT(*) on the latest-run query; but it lives on the prior run so
    # the banner-clears semantic suppresses it entirely).
    prior_run = insert_run(
        conn,
        source="manual",
        started_ts="2026-05-12T09:00:00.000",
        state="completed",
        finished_ts="2026-05-12T09:00:01.000",
    )
    conn.commit()
    _emit_multi_leg_discrepancy(conn, run_id=prior_run, trade_id=2)

    # LATEST run with 1 multi-leg discrepancy emitting 4 correction rows.
    latest_run = insert_run(
        conn,
        source="manual",
        started_ts="2026-05-12T10:00:00.000",
        state="completed",
        finished_ts="2026-05-12T10:00:01.000",
    )
    conn.commit()
    _emit_multi_leg_discrepancy(conn, run_id=latest_run, trade_id=1)

    # F18 DISTINCT semantic: 1 (NOT 4 — would inflate if COUNT(*)).
    # Banner-clears semantic: 1 (NOT 2 — prior run's multi-leg suppressed).
    count = count_recent_multi_leg_auto_corrections(conn)
    assert count == 1

    # Build BriefingInputs the way the runner does at swing/pipeline/runner.py.
    inputs = BriefingInputs(
        action_session_date="2026-05-13",
        data_asof_date="2026-05-12",
        generated_at="2026-05-13T08:00:00",
        weather=None,
        weather_is_stale=True,
        equity=2000.0,
        open_count=2,
        soft_warn=4,
        hard_cap=6,
        last_pipeline_ts="2026-05-12T17:00:00",
        pipeline_is_stale=False,
        current_session_match=True,
        recommendations=[],
        open_trades=[],
        reconciliation_tier1_multi_leg_redirected_count=count,
    )
    vm = build_briefing_view_model(inputs)
    md = render_briefing_md(vm)
    assert "## Reconciliation status" in md
    assert "- Multi-leg auto-redirects applied this run: 1" in md
