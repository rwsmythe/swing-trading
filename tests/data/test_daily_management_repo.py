"""Daily Management repo tests (Phase 8 Task 2.0).

T2.0 covers ``insert_snapshot`` + ``insert_event_log`` only — pure INSERTs
keyed off the operator-validated field dicts. SELECT-side functions land in
T2.1+; UPSERT/tier-upgrade flows land in T2.3.

Per plan + CLAUDE.md gotcha (2026-05-06): ``INSERT OR REPLACE`` is forbidden
on this table because the audit-trail / FK-cascade semantics of REPLACE would
silently destroy linked event_log + audit chains. T2.0 confirms the simple
INSERT contract; T2.3 will use SELECT-then-UPDATE-or-INSERT for the UPSERT.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.daily_management import (
    SupersededRowImmutableException,
    TierOrderingError,
    has_update_today_for_trades,
    insert_event_log,
    insert_snapshot,
    list_for_trade_timeline,
    list_open_position_active_snapshots,
    select_active_snapshot,
    select_history,
    tier_upgrade_snapshot,
    upsert_snapshot,
)


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    db_path = tmp_path / "phase8.db"
    c = ensure_schema(db_path)
    c.execute("PRAGMA foreign_keys=ON")
    _seed_minimal_trade(c, trade_id=1)
    try:
        yield c
    finally:
        c.close()


def test_insert_snapshot_returns_management_record_id(
    conn: sqlite3.Connection,
) -> None:
    fields = _full_snapshot_fields(data_asof_session="2026-05-07")
    rec_id = insert_snapshot(conn, trade_id=1, snapshot_fields=fields)
    assert isinstance(rec_id, int) and rec_id > 0


def test_insert_snapshot_persists_all_columns(
    conn: sqlite3.Connection,
) -> None:
    """Spot-check a representative subset of the 24 INSERT-ed columns
    plus discriminator + audit defaults."""
    fields = _full_snapshot_fields(data_asof_session="2026-05-07")
    rec_id = insert_snapshot(conn, trade_id=1, snapshot_fields=fields)
    row = conn.execute(
        "SELECT current_price, current_stop, mfe_mae_precision_level, "
        "       trail_MA_period_days, is_superseded, record_type, "
        "       superseded_by_record_id, pipeline_run_id, "
        "       maturity_stage, trail_MA_eligibility_flag "
        "FROM daily_management_records WHERE management_record_id = ?",
        (rec_id,),
    ).fetchone()
    assert row[0] == fields["current_price"]
    assert row[1] == fields["current_stop"]
    assert row[2] == "daily_approximate"
    assert row[3] == 21
    assert row[4] == 0  # is_superseded default
    assert row[5] == "daily_snapshot"
    assert row[6] is None  # superseded_by_record_id default NULL
    assert row[7] == fields["pipeline_run_id"]
    assert row[8] == fields["maturity_stage"]
    assert row[9] == fields["trail_MA_eligibility_flag"]


def test_insert_snapshot_pipeline_run_id_optional(
    conn: sqlite3.Connection,
) -> None:
    """pipeline_run_id is nullable (FK ON DELETE SET NULL) — caller may omit."""
    fields = _full_snapshot_fields(data_asof_session="2026-05-07")
    fields.pop("pipeline_run_id", None)
    rec_id = insert_snapshot(conn, trade_id=1, snapshot_fields=fields)
    row = conn.execute(
        "SELECT pipeline_run_id FROM daily_management_records "
        "WHERE management_record_id = ?",
        (rec_id,),
    ).fetchone()
    assert row[0] is None


def test_insert_event_log_returns_id_with_record_type_event_log(
    conn: sqlite3.Connection,
) -> None:
    fields = _minimal_event_log_fields(data_asof_session="2026-05-07")
    rec_id = insert_event_log(conn, trade_id=1, event_log_fields=fields)
    rt = conn.execute(
        "SELECT record_type FROM daily_management_records "
        "WHERE management_record_id = ?",
        (rec_id,),
    ).fetchone()[0]
    assert rt == "event_log"


def test_insert_event_log_position_state_optional(
    conn: sqlite3.Connection,
) -> None:
    """event_log accepts NULL position-state per §3.1.1 R1 Critical 1 fix."""
    fields = _minimal_event_log_fields(data_asof_session="2026-05-07")
    fields.pop("current_price", None)  # explicit NULL
    rec_id = insert_event_log(conn, trade_id=1, event_log_fields=fields)
    row = conn.execute(
        "SELECT current_price FROM daily_management_records "
        "WHERE management_record_id = ?",
        (rec_id,),
    ).fetchone()
    assert row[0] is None


def test_insert_event_log_persists_operator_input_fields(
    conn: sqlite3.Connection,
) -> None:
    fields = _minimal_event_log_fields(data_asof_session="2026-05-07")
    fields.update(
        {
            "thesis_status": "intact",
            "stop_changed": 1,
            "prior_stop": 90.0,
            "new_stop": 95.0,
            "stop_change_reason": "trail to MA21",
            "action_taken": "move_stop",
            "action_reason": "stage 2 trail",
            "volume_behavior": "confirming",
            "relative_strength_status": "improving",
            "rule_violation_suspected": 0,
            "management_notes": "clean uptrend",
        }
    )
    rec_id = insert_event_log(conn, trade_id=1, event_log_fields=fields)
    row = conn.execute(
        "SELECT thesis_status, stop_changed, prior_stop, new_stop, "
        "       stop_change_reason, action_taken, action_reason, "
        "       volume_behavior, relative_strength_status, "
        "       rule_violation_suspected, management_notes "
        "FROM daily_management_records WHERE management_record_id = ?",
        (rec_id,),
    ).fetchone()
    assert row == (
        "intact", 1, 90.0, 95.0, "trail to MA21",
        "move_stop", "stage 2 trail", "confirming", "improving",
        0, "clean uptrend",
    )


def test_select_active_snapshot_returns_active_only(
    conn: sqlite3.Connection,
) -> None:
    fields_a = _full_snapshot_fields(data_asof_session="2026-05-07")
    insert_snapshot(conn, trade_id=1, snapshot_fields=fields_a)
    rec = select_active_snapshot(
        conn, trade_id=1, data_asof_session="2026-05-07"
    )
    assert rec is not None
    assert rec.is_superseded == 0
    assert rec.mfe_mae_precision_level == "daily_approximate"


def test_select_active_snapshot_returns_none_when_only_superseded(
    conn: sqlite3.Connection,
) -> None:
    fields = _full_snapshot_fields(data_asof_session="2026-05-07")
    rec_id = insert_snapshot(conn, trade_id=1, snapshot_fields=fields)
    conn.execute(
        "UPDATE daily_management_records SET is_superseded = 1 "
        "WHERE management_record_id = ?",
        (rec_id,),
    )
    rec = select_active_snapshot(
        conn, trade_id=1, data_asof_session="2026-05-07"
    )
    assert rec is None


def test_select_active_snapshot_returns_none_for_unknown_session(
    conn: sqlite3.Connection,
) -> None:
    rec = select_active_snapshot(
        conn, trade_id=1, data_asof_session="1999-01-01"
    )
    assert rec is None


# ---- T2.2: select_history + list_for_trade_timeline +
#           list_open_position_active_snapshots ------------------------------


def test_select_history_returns_chain_in_creation_order(
    conn: sqlite3.Connection,
) -> None:
    """Full chain incl. superseded; order: created_at ASC, precision_level ASC."""
    fields1 = _full_snapshot_fields(data_asof_session="2026-05-07")
    fields1["mfe_mae_precision_level"] = "daily_approximate"
    rec1 = insert_snapshot(conn, trade_id=1, snapshot_fields=fields1)
    conn.execute(
        "UPDATE daily_management_records SET is_superseded = 1 "
        "WHERE management_record_id = ?",
        (rec1,),
    )
    fields2 = _full_snapshot_fields(data_asof_session="2026-05-07")
    fields2["mfe_mae_precision_level"] = "intraday_estimated"
    rec2 = insert_snapshot(conn, trade_id=1, snapshot_fields=fields2)
    chain = select_history(
        conn, trade_id=1, data_asof_session="2026-05-07"
    )
    assert [r.management_record_id for r in chain] == [rec1, rec2]


def test_select_history_no_session_filter_returns_all_sessions(
    conn: sqlite3.Connection,
) -> None:
    """data_asof_session=None returns all rows for the trade."""
    fields_a = _full_snapshot_fields(data_asof_session="2026-05-06")
    rec_a = insert_snapshot(conn, trade_id=1, snapshot_fields=fields_a)
    fields_b = _full_snapshot_fields(data_asof_session="2026-05-07")
    rec_b = insert_snapshot(conn, trade_id=1, snapshot_fields=fields_b)
    chain = select_history(conn, trade_id=1, data_asof_session=None)
    ids = [r.management_record_id for r in chain]
    assert rec_a in ids and rec_b in ids


def test_list_for_trade_timeline_orders_chronologically_with_tiebreak(
    conn: sqlite3.Connection,
) -> None:
    """Spec §7.2: ORDER BY review_date ASC, created_at ASC, management_record_id ASC."""
    el_a = _minimal_event_log_fields(data_asof_session="2026-05-07")
    el_a["created_at"] = "2026-05-07T10:00:00"
    rec_a = insert_event_log(conn, trade_id=1, event_log_fields=el_a)
    el_b = _minimal_event_log_fields(data_asof_session="2026-05-07")
    el_b["created_at"] = "2026-05-07T10:00:00"  # same wall-clock!
    rec_b = insert_event_log(conn, trade_id=1, event_log_fields=el_b)
    timeline = list_for_trade_timeline(conn, trade_id=1)
    ids = [r.management_record_id for r in timeline]
    assert ids.index(rec_a) < ids.index(rec_b)


def test_list_for_trade_timeline_default_excludes_superseded(
    conn: sqlite3.Connection,
) -> None:
    fields = _full_snapshot_fields(data_asof_session="2026-05-07")
    rec_id = insert_snapshot(conn, trade_id=1, snapshot_fields=fields)
    conn.execute(
        "UPDATE daily_management_records SET is_superseded = 1 "
        "WHERE management_record_id = ?",
        (rec_id,),
    )
    timeline = list_for_trade_timeline(
        conn, trade_id=1, include_superseded=False
    )
    assert all(r.is_superseded == 0 for r in timeline)


def test_list_for_trade_timeline_include_superseded_returns_all(
    conn: sqlite3.Connection,
) -> None:
    fields = _full_snapshot_fields(data_asof_session="2026-05-07")
    rec_id = insert_snapshot(conn, trade_id=1, snapshot_fields=fields)
    conn.execute(
        "UPDATE daily_management_records SET is_superseded = 1 "
        "WHERE management_record_id = ?",
        (rec_id,),
    )
    timeline = list_for_trade_timeline(
        conn, trade_id=1, include_superseded=True
    )
    assert any(
        r.management_record_id == rec_id and r.is_superseded == 1
        for r in timeline
    )


def test_list_open_position_active_snapshots_returns_one_per_open_trade(
    conn: sqlite3.Connection,
) -> None:
    """Drives §7.1 dashboard tile."""
    _seed_minimal_trade(conn, trade_id=2)
    fields1 = _full_snapshot_fields(data_asof_session="2026-05-07")
    insert_snapshot(conn, trade_id=1, snapshot_fields=fields1)
    fields2 = _full_snapshot_fields(data_asof_session="2026-05-07")
    insert_snapshot(conn, trade_id=2, snapshot_fields=fields2)
    snaps = list_open_position_active_snapshots(conn)
    assert {s.trade_id for s in snaps} == {1, 2}


def test_list_open_position_active_snapshots_excludes_closed_trade(
    conn: sqlite3.Connection,
) -> None:
    """Closed trades must NOT appear in the dashboard tile feed."""
    _seed_minimal_trade(conn, trade_id=3)
    conn.execute(
        "UPDATE trades SET state = 'closed' WHERE id = ?", (3,)
    )
    fields = _full_snapshot_fields(data_asof_session="2026-05-07")
    insert_snapshot(conn, trade_id=3, snapshot_fields=fields)
    snaps = list_open_position_active_snapshots(conn)
    assert all(s.trade_id != 3 for s in snaps)


def test_list_open_position_active_snapshots_excludes_superseded(
    conn: sqlite3.Connection,
) -> None:
    fields = _full_snapshot_fields(data_asof_session="2026-05-07")
    rec_id = insert_snapshot(conn, trade_id=1, snapshot_fields=fields)
    conn.execute(
        "UPDATE daily_management_records SET is_superseded = 1 "
        "WHERE management_record_id = ?",
        (rec_id,),
    )
    snaps = list_open_position_active_snapshots(conn)
    assert all(s.management_record_id != rec_id for s in snaps)


def test_list_open_position_active_snapshots_excludes_event_log_rows(
    conn: sqlite3.Connection,
) -> None:
    """Only daily_snapshot rows feed the dashboard tile, not event_log rows."""
    el = _minimal_event_log_fields(data_asof_session="2026-05-07")
    insert_event_log(conn, trade_id=1, event_log_fields=el)
    snaps = list_open_position_active_snapshots(conn)
    assert all(s.record_type == "daily_snapshot" for s in snaps)


def test_list_open_position_active_snapshots_returns_only_latest_per_trade(
    conn: sqlite3.Connection,
) -> None:
    """Codex R1 Major 1 discriminator.

    Daily snapshots are NOT superseded across sessions (the partial unique
    index over (trade_id, data_asof_session, mfe_mae_precision_level)
    treats different sessions as different rows; both retain
    is_superseded=0). After multiple pipeline runs over multiple days, the
    dashboard-tile feed must return ONE row per open trade (the latest
    data_asof_session), not one row per (trade, session).

    Pre-fix: WHERE clause filters only by record_type + is_superseded +
    state — returns N rows per trade (one per session).
    Post-fix: correlated subquery clamps to MAX(data_asof_session) per
    trade — exactly one row per trade.
    """
    fields_d1 = _full_snapshot_fields(data_asof_session="2026-05-05")
    fields_d2 = _full_snapshot_fields(data_asof_session="2026-05-06")
    fields_d3 = _full_snapshot_fields(data_asof_session="2026-05-07")
    insert_snapshot(conn, trade_id=1, snapshot_fields=fields_d1)
    insert_snapshot(conn, trade_id=1, snapshot_fields=fields_d2)
    insert_snapshot(conn, trade_id=1, snapshot_fields=fields_d3)

    snaps = list_open_position_active_snapshots(conn)
    assert len(snaps) == 1, (
        f"expected exactly one active snapshot per trade (latest session); "
        f"got {len(snaps)} rows. Pre-fix: query returns one row per "
        f"(trade, session) — duplicate tile rendering on the dashboard."
    )
    assert snaps[0].trade_id == 1
    assert snaps[0].data_asof_session == "2026-05-07", (
        f"latest session must win; got {snaps[0].data_asof_session}"
    )


# ---- T2.3: upsert_snapshot + tier_upgrade_snapshot --------------------------


def test_upsert_snapshot_same_tier_reflow_preserves_PK(
    conn: sqlite3.Connection,
) -> None:
    """SELECT-then-UPDATE-or-INSERT: management_record_id PRESERVED on reflow.
    Discriminating against REPLACE which would mint a new PK."""
    fields = _full_snapshot_fields(data_asof_session="2026-05-07")
    fields["current_price"] = 100.0
    rec_id_first = upsert_snapshot(conn, trade_id=1, snapshot_fields=fields)

    # Same-tier reflow with new price:
    fields2 = dict(fields)
    fields2["current_price"] = 105.0
    rec_id_second = upsert_snapshot(conn, trade_id=1, snapshot_fields=fields2)

    # PK preserved (NOT a new row):
    assert rec_id_second == rec_id_first

    # Data updated:
    row = conn.execute(
        "SELECT current_price FROM daily_management_records "
        "WHERE management_record_id = ?",
        (rec_id_first,),
    ).fetchone()
    assert row[0] == 105.0


def test_upsert_snapshot_against_superseded_raises(
    conn: sqlite3.Connection,
) -> None:
    """SupersededRowImmutableException when only superseded rows exist."""
    fields = _full_snapshot_fields(data_asof_session="2026-05-07")
    rec_id = upsert_snapshot(conn, trade_id=1, snapshot_fields=fields)
    conn.execute(
        "UPDATE daily_management_records SET is_superseded = 1 "
        "WHERE management_record_id = ?",
        (rec_id,),
    )

    with pytest.raises(SupersededRowImmutableException):
        upsert_snapshot(conn, trade_id=1, snapshot_fields=fields)


def test_tier_upgrade_3_tier_chain(conn: sqlite3.Connection) -> None:
    """Synthetic 3-tier sequence: daily_approximate → intraday_estimated → intraday_exact.
    Discriminating: at every transaction boundary, exactly one active row;
    audit chain threaded via superseded_by_record_id."""
    # Step 1: daily_approximate
    f1 = _full_snapshot_fields(data_asof_session="2026-05-07")
    f1["mfe_mae_precision_level"] = "daily_approximate"
    rec1 = upsert_snapshot(conn, trade_id=1, snapshot_fields=f1)

    # Step 2: tier-upgrade to intraday_estimated
    f2 = _full_snapshot_fields(data_asof_session="2026-05-07")
    f2["mfe_mae_precision_level"] = "intraday_estimated"
    rec2 = tier_upgrade_snapshot(
        conn,
        trade_id=1,
        data_asof_session="2026-05-07",
        new_precision_level="intraday_estimated",
        snapshot_fields=f2,
    )
    row1 = conn.execute(
        "SELECT is_superseded, superseded_by_record_id "
        "FROM daily_management_records WHERE management_record_id = ?",
        (rec1,),
    ).fetchone()
    assert row1 == (1, rec2)

    # Step 3: tier-upgrade to intraday_exact
    f3 = _full_snapshot_fields(data_asof_session="2026-05-07")
    f3["mfe_mae_precision_level"] = "intraday_exact"
    rec3 = tier_upgrade_snapshot(
        conn,
        trade_id=1,
        data_asof_session="2026-05-07",
        new_precision_level="intraday_exact",
        snapshot_fields=f3,
    )
    row2 = conn.execute(
        "SELECT is_superseded, superseded_by_record_id "
        "FROM daily_management_records WHERE management_record_id = ?",
        (rec2,),
    ).fetchone()
    assert row2 == (1, rec3)

    # Active count must be 1 at end:
    active_count = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records "
        "WHERE trade_id = 1 AND data_asof_session = '2026-05-07' "
        "  AND record_type = 'daily_snapshot' AND is_superseded = 0"
    ).fetchone()[0]
    assert active_count == 1


def test_tier_upgrade_without_predecessor_raises_TierOrderingError(  # noqa: N802
    conn: sqlite3.Connection,
) -> None:
    """Codex R1 Major 4 discriminator.

    ``tier_upgrade_snapshot`` is the audit-chain "successor inserts +
    predecessor flips superseded_by_record_id" path; calling it without a
    predecessor at the lower tier silently produced a higher-tier row with
    no daily_approximate root, breaking the audit chain.

    Pre-fix: INSERT proceeds; the new active row exists with no
    predecessor link; downstream audit-trail traversal misses the gap.
    Post-fix: TierOrderingError raised — operator must seed the daily
    snapshot via upsert_snapshot first.
    """
    fields = _full_snapshot_fields(data_asof_session="2026-05-07")
    fields["mfe_mae_precision_level"] = "intraday_estimated"
    with pytest.raises(TierOrderingError, match="predecessor"):
        tier_upgrade_snapshot(
            conn,
            trade_id=1,
            data_asof_session="2026-05-07",
            new_precision_level="intraday_estimated",
            snapshot_fields=fields,
        )
    # Defensive: no orphan row was inserted before the raise.
    inserted = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records "
        "WHERE trade_id = 1 AND data_asof_session = '2026-05-07'"
    ).fetchone()[0]
    assert inserted == 0, (
        f"tier_upgrade_snapshot must not insert an orphan row when "
        f"predecessor is missing; got {inserted} rows."
    )


def test_tier_upgrade_to_lower_tier_raises_TierOrderingError(
    conn: sqlite3.Connection,
) -> None:
    f1 = _full_snapshot_fields(data_asof_session="2026-05-07")
    f1["mfe_mae_precision_level"] = "intraday_estimated"
    upsert_snapshot(conn, trade_id=1, snapshot_fields=f1)
    f2 = _full_snapshot_fields(data_asof_session="2026-05-07")
    f2["mfe_mae_precision_level"] = "daily_approximate"
    with pytest.raises(TierOrderingError):
        tier_upgrade_snapshot(
            conn,
            trade_id=1,
            data_asof_session="2026-05-07",
            new_precision_level="daily_approximate",
            snapshot_fields=f2,
        )


def test_upsert_snapshot_does_not_use_REPLACE(
    conn: sqlite3.Connection,
) -> None:
    """Discriminating against `INSERT OR REPLACE` (CLAUDE.md gotcha 2026-05-06).
    REPLACE would: (a) cascade-wipe child FK rows, (b) mint new PK. We test (b):
    insert; reflow; assert original management_record_id IS the same row, not a
    new one with same logical key. (Already tested in
    test_upsert_snapshot_same_tier_reflow_preserves_PK; this test additionally
    asserts no AUTOINCREMENT advance.)"""
    f1 = _full_snapshot_fields(data_asof_session="2026-05-07")
    rec_id = upsert_snapshot(conn, trade_id=1, snapshot_fields=f1)
    upsert_snapshot(conn, trade_id=1, snapshot_fields=f1)  # reflow
    # Highest auto-incremented id should still equal rec_id (no INSERT happened):
    max_id = conn.execute(
        "SELECT MAX(management_record_id) FROM daily_management_records"
    ).fetchone()[0]
    assert max_id == rec_id


# ---- has_update_today_for_trades (Polish-bundle 2026-05-09 Family A) -------


def test_has_update_today_for_trades_empty_when_no_records(
    conn: sqlite3.Connection,
) -> None:
    """A.1 — open trade with NO daily_management_records returns empty set."""
    today = "2026-05-09"
    result = has_update_today_for_trades(conn, [1], action_session=today)
    assert result == set()


def test_has_update_today_for_trades_returns_id_for_today_snapshot(
    conn: sqlite3.Connection,
) -> None:
    """A.2 — daily_snapshot row whose review_date matches today qualifies."""
    today = "2026-05-09"
    fields = _full_snapshot_fields(data_asof_session=today)
    insert_snapshot(conn, trade_id=1, snapshot_fields=fields)
    result = has_update_today_for_trades(conn, [1], action_session=today)
    assert result == {1}


def test_has_update_today_for_trades_excludes_superseded(
    conn: sqlite3.Connection,
) -> None:
    """A.4 — superseded rows are filtered out by the ``is_superseded = 0``
    clause in the helper's predicate. GREEN at write-time (predicate already
    enforces this) — captures the contract so a future maintainer who edits
    the predicate cannot silently drop the supersede filter."""
    today = "2026-05-09"
    fields = _full_snapshot_fields(data_asof_session=today)
    rec_id = insert_snapshot(conn, trade_id=1, snapshot_fields=fields)
    conn.execute(
        "UPDATE daily_management_records SET is_superseded = 1 "
        "WHERE management_record_id = ?",
        (rec_id,),
    )
    result = has_update_today_for_trades(conn, [1], action_session=today)
    assert result == set()


# ---- helpers ----------------------------------------------------------------


def _seed_minimal_trade(conn: sqlite3.Connection, *, trade_id: int) -> None:
    """Mirror Phase 7 trades schema; sufficient to satisfy NOT NULL + CHECK.

    Ticker is derived from ``trade_id`` so multiple seeds in the same test
    don't collide on the ``trades.ticker`` UNIQUE constraint.
    """
    conn.execute(
        "INSERT INTO trades "
        "(id, ticker, entry_date, entry_price, initial_shares, initial_stop, "
        " current_stop, state, trade_origin, pre_trade_locked_at, current_size) "
        "VALUES (?, ?, '2026-05-01', 100.0, 10, 90.0, 90.0, "
        "        'managing', 'manual_off_pipeline', '2026-05-01T16:00:00', 10.0)",
        (trade_id, f"TST{trade_id}"),
    )


def _full_snapshot_fields(*, data_asof_session: str) -> dict[str, Any]:
    """All snapshot-required fields per spec §3.1.1 OPERATION_REQUIRED_FIELDS["snapshot_emit"].

    Plan §G + spec list these as caller-validated. T2.0 trusts validated input.
    """
    return {
        "review_date": data_asof_session,
        "data_asof_session": data_asof_session,
        "created_at": f"{data_asof_session}T00:00:00",
        "mfe_mae_precision_level": "daily_approximate",
        "pipeline_run_id": None,
        "current_price": 110.0,
        "current_stop": 95.0,
        "current_size": 10.0,
        "current_avg_cost": 100.0,
        "open_R_effective": 1.0,
        "open_MFE_R_to_date": 1.5,
        "open_MAE_R_to_date": 0.2,
        "intraday_high": 111.0,
        "intraday_low": 109.0,
        "position_capital_utilization_pct": 0.1467,
        "position_capital_denominator_dollars": 7500.0,
        "position_portfolio_heat_contribution_dollars": 50.0,
        "maturity_stage": "+1.5R_to_+2R",
        "trail_MA_candidate_price": 105.0,
        "trail_MA_period_days": 21,
        "trail_MA_eligibility_flag": 0,
    }


def _minimal_event_log_fields(*, data_asof_session: str) -> dict[str, Any]:
    """Only required-by-validator fields for ``event_log_emit``.

    Position-state is OPTIONAL on event_log (§3.1.1 R1 Critical 1 fix); a
    populated ``current_price`` is included so that the
    ``test_insert_event_log_position_state_optional`` test can pop it and
    verify the NULL persistence path.
    """
    return {
        "review_date": data_asof_session,
        "data_asof_session": data_asof_session,
        "created_at": f"{data_asof_session}T12:00:00",
        "mfe_mae_precision_level": "daily_approximate",
        "current_price": 110.0,
    }
