"""T-D.14 — briefing.md "Reconciliation status" section end-to-end test.

Per plan §E.14 acceptance criteria:
  1. Plant 2 pending-ambiguity discrepancies + 1 recently-applied tier-1
     correction; run ``_step_export``; assert briefing.md contains the
     "Reconciliation status" section with the expected counters (pending = 2,
     tier-1 recent = 1).
  2. Empty-state case: no pending + no recent tier-1 → briefing.md does NOT
     include the section (per T-C.9 conditional rendering at
     ``swing/rendering/briefing_md.py``: section emits only when EITHER
     counter > 0).

Plants DB rows directly + invokes ``_step_export`` against an isolated tmp DB
(mirrors ``test_phase12_bundle_c_cvgi_41_full_pipeline.py`` T-C.11 shape but
seeds discrepancies + corrections without going through
``run_schwab_reconciliation`` — the wiring under test is the T-C.8 SQL counter
queries → T-C.10 BriefingInputs propagation → T-C.9 markdown rendering chain).
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import date as _date
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from swing.data.db import ensure_schema


def _seed_pipeline_run_running(conn: sqlite3.Connection) -> tuple[int, str]:
    """Insert a 'running' pipeline_runs row that satisfies the
    ``lease.verify_held()`` precondition in ``_step_export``.
    Mirrors the T-C.11 pattern verbatim.
    """
    token = str(uuid.uuid4())
    cur = conn.execute(
        """INSERT INTO pipeline_runs
           (started_ts, trigger, data_asof_date, action_session_date,
            state, lease_token, lease_heartbeat_ts)
           VALUES ('2026-04-27T20:55:00', 'manual', '2026-04-27',
                   '2026-04-28', 'running', ?, '2026-04-27T20:55:00')""",
        (token,),
    )
    return int(cur.lastrowid), token


def _seed_empty_evaluation_run(conn: sqlite3.Connection) -> int:
    """Minimal evaluation_runs row so ``_step_export``'s candidates/recs
    SELECTs return empty without raising. Zero candidates / recs is fine —
    the section-under-test reads ``reconciliation_corrections`` +
    ``reconciliation_discrepancies``, not the eval-grain tables.
    """
    cur = conn.execute(
        """INSERT INTO evaluation_runs
           (run_ts, data_asof_date, action_session_date, finviz_csv_path,
            tickers_evaluated, aplus_count, watch_count, skip_count,
            excluded_count, error_count, rs_universe_version, rs_universe_hash)
           VALUES ('2026-04-27T21:00:00', '2026-04-27', '2026-04-28', NULL,
                   0, 0, 0, 0, 0, 0, 'v1', 'd')""",
    )
    return int(cur.lastrowid)


def _insert_pending_ambiguity(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    run_id: int,
) -> int:
    """Plant a trade + a material=1 pending_ambiguity_resolution discrepancy.
    Returns the new trade_id."""
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ticker, "2026-04-27", 10.0, 100, 9.0, 9.0, "managing",
         "manual_off_pipeline", "2026-04-27T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    conn.execute(
        """
        INSERT INTO reconciliation_discrepancies (
            run_id, discrepancy_type, trade_id, ticker, field_name,
            expected_value_json, actual_value_json, delta_text,
            material_to_review, resolution, ambiguity_kind,
            resolution_reason, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, "stop_mismatch", trade_id, ticker, "current_stop",
            '{"current_stop": 9.0}', '{"stop_price": 8.0}', "-$1.00", 1,
            "pending_ambiguity_resolution", "schwab_returned_no_match",
            f"test pending {ticker}", "2026-05-15T12:00:00",
        ),
    )
    return trade_id


def _insert_tier1_correction(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    run_id: int,
    applied_at: str,
) -> None:
    """Plant a trade + entry-fill + auto_corrected_from_schwab discrepancy +
    reconciliation_corrections.auto_applied row at ``applied_at``."""
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ticker, "2026-04-27", 5.23, 100, 4.0, 4.0, "managing",
         "manual_off_pipeline", "2026-04-27T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    fcur = conn.execute(
        """
        INSERT INTO fills (
            trade_id, fill_datetime, action, quantity, price,
            reconciliation_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (trade_id, "2026-04-27T14:23:00", "entry", 100.0, 5.30,
         "reconciled_discrepancy_resolved"),
    )
    fill_id = int(fcur.lastrowid)
    dcur = conn.execute(
        """
        INSERT INTO reconciliation_discrepancies (
            run_id, discrepancy_type, trade_id, fill_id, ticker, field_name,
            expected_value_json, actual_value_json, delta_text,
            material_to_review, resolution, resolution_reason,
            resolved_at, resolved_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, "entry_price_mismatch", trade_id, fill_id, ticker,
            "price", '{"price": 5.23}', '{"price": 5.30}', "+$0.07", 1,
            "auto_corrected_from_schwab", "tier-1 auto-correct probe",
            applied_at, "auto", "2026-05-15T12:00:00",
        ),
    )
    discrepancy_id = int(dcur.lastrowid)
    conn.execute(
        """
        INSERT INTO reconciliation_corrections (
            discrepancy_id, correction_action, correction_choice,
            affected_table, affected_row_id, field_name,
            pre_correction_value_json, source_canonical_value_json,
            applied_value_json, operator_truth_value_json,
            applied_at, applied_by, correction_set_id,
            superseded_by_correction_id, risk_policy_id_at_correction,
            schwab_api_call_id, reconciliation_run_id,
            correction_reason, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            discrepancy_id, "auto_applied", None,
            "fills", fill_id, "price",
            '{"price": 5.23}', '{"price": 5.30}',
            '{"price": 5.30}', None,
            applied_at, "auto", None, None, None, None, run_id,
            "tier-1 auto-correct probe", None,
        ),
    )


def _insert_reconciliation_run(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        """
        INSERT INTO reconciliation_runs (source, started_ts, state)
        VALUES (?, ?, ?)
        """,
        ("schwab_api", "2026-05-15T12:00:00", "completed"),
    )
    return int(cur.lastrowid)


def _make_cfg(tmp_path: Path):
    """Construct a minimal cfg + initialize schema on its db_path.
    Mirrors T-C.11 pattern verbatim.
    """
    from swing.config import load
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg


def _run_step_export(cfg, *, run_id: int, token: str, eval_run_id: int) -> str:
    """Invoke ``_step_export`` end-to-end + return the on-disk briefing.md
    contents.
    """
    from swing.pipeline.lease import Lease
    from swing.pipeline.runner import _step_export

    lease = Lease(db_path=cfg.paths.db_path, run_id=run_id, token=token)
    action_session = _date(2026, 4, 28)
    _step_export(
        cfg=cfg, lease=lease, eval_run_id=eval_run_id,
        action_session=action_session,
        data_asof="2026-04-27",
        chart_paths={},
        fetcher=None,
    )
    target_dir = cfg.paths.exports_dir / action_session.isoformat()
    md_path = target_dir / "briefing.md"
    assert md_path.exists(), (
        f"_step_export did not emit briefing.md at {md_path}"
    )
    return md_path.read_text(encoding="utf-8")


def test_briefing_md_reconciliation_section_present_with_pending_and_tier1(
    tmp_path: Path,
) -> None:
    """BINDING acceptance criterion #1 (plan §E.14):
    plant 2 pending-ambiguity + 1 recent tier-1 → briefing.md contains the
    "Reconciliation status" section with pending=2 + tier-1 recent>=1.
    """
    cfg = _make_cfg(tmp_path)
    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        run_id_recon = _insert_reconciliation_run(conn)
        _insert_pending_ambiguity(conn, ticker="PND1", run_id=run_id_recon)
        _insert_pending_ambiguity(conn, ticker="PND2", run_id=run_id_recon)
        # Tier-1 correction within the last-7-day window: stamp `applied_at`
        # to "now (UTC, microseconds stripped)" which satisfies the
        # `applied_at >= cutoff` predicate in `_step_export`'s SQL.
        applied_at = (
            datetime.now(timezone.utc)
            .replace(microsecond=0, tzinfo=None)
            .isoformat(timespec="milliseconds")
        )
        _insert_tier1_correction(
            conn, ticker="AUT", run_id=run_id_recon, applied_at=applied_at,
        )
        with conn:
            eval_run_id = _seed_empty_evaluation_run(conn)
            run_id, token = _seed_pipeline_run_running(conn)
    finally:
        conn.close()

    md = _run_step_export(
        cfg, run_id=run_id, token=token, eval_run_id=eval_run_id,
    )

    # Section heading present.
    assert "## Reconciliation status" in md, (
        "briefing.md missing Reconciliation status section under "
        "2-pending + 1-tier1 fixture"
    )
    # Counter assertions — discriminating per plan §E.14 acceptance #1.
    assert "Tier-2 pending operator review: 2" in md, (
        "briefing.md missing pending=2 counter line under 2-pending fixture"
    )
    # Tier-1 recent count >= 1 per acceptance criterion. Production
    # invariant: the fixture plants exactly one tier-1 correction within
    # the last 7 days, so the exact "1" rendering is the discriminator
    # against the empty-state and >1 alternatives.
    assert "Tier-1 auto-corrected (last 7 days): 1" in md, (
        "briefing.md missing tier1_recent_count=1 line under 1-tier1 fixture"
    )
    # CLI hints are part of T-C.9 rendering.
    assert "list-pending-ambiguities" in md, (
        "briefing.md missing T-C.9 CLI hint for list-pending-ambiguities"
    )
    assert "resolve-ambiguity" in md, (
        "briefing.md missing T-C.9 CLI hint for resolve-ambiguity"
    )


def test_briefing_md_reconciliation_section_absent_when_empty(
    tmp_path: Path,
) -> None:
    """BINDING acceptance criterion #2 (plan §E.14):
    no pending + no recent tier-1 → briefing.md does NOT include the
    "Reconciliation status" section. Conditional rendering at
    ``swing/rendering/briefing_md.py``: section emits only when EITHER
    counter > 0.

    Defense-in-depth: also plant a STALE tier-1 correction (>7 days old)
    + an IMMATERIAL pending discrepancy (material_to_review=0) so the
    test discriminates the SQL filter predicates (last-7-days cutoff on
    ``reconciliation_corrections.applied_at`` + ``material_to_review=1``
    on ``reconciliation_discrepancies``) — both should be excluded by
    ``_step_export``'s counter SQL.
    """
    cfg = _make_cfg(tmp_path)
    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        run_id_recon = _insert_reconciliation_run(conn)

        # Defense-in-depth: stale tier-1 (>7 days old) → SQL cutoff excludes.
        stale_applied_at = (
            datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)
            - timedelta(days=30)
        ).isoformat(timespec="milliseconds")
        _insert_tier1_correction(
            conn, ticker="STA", run_id=run_id_recon,
            applied_at=stale_applied_at,
        )

        # Defense-in-depth: immaterial pending (material=0) → SQL excludes.
        cur = conn.execute(
            """
            INSERT INTO trades (
                ticker, entry_date, entry_price, initial_shares, initial_stop,
                current_stop, state, trade_origin, pre_trade_locked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("IMM", "2026-04-27", 10.0, 100, 9.0, 9.0, "managing",
             "manual_off_pipeline", "2026-04-27T16:00:00"),
        )
        trade_id_imm = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO reconciliation_discrepancies (
                run_id, discrepancy_type, trade_id, ticker, field_name,
                expected_value_json, actual_value_json, delta_text,
                material_to_review, resolution, ambiguity_kind,
                resolution_reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id_recon, "stop_mismatch", trade_id_imm, "IMM",
                "current_stop", '{"current_stop": 9.0}',
                '{"stop_price": 8.0}', "-$1.00", 0,
                "pending_ambiguity_resolution",
                "schwab_returned_no_match", "immaterial pending",
                "2026-05-15T12:00:00",
            ),
        )

        with conn:
            eval_run_id = _seed_empty_evaluation_run(conn)
            run_id, token = _seed_pipeline_run_running(conn)
    finally:
        conn.close()

    md = _run_step_export(
        cfg, run_id=run_id, token=token, eval_run_id=eval_run_id,
    )

    # Section heading MUST be absent per T-C.9 conditional rendering.
    assert "## Reconciliation status" not in md, (
        "briefing.md unexpectedly contains Reconciliation status section "
        "under empty-state fixture (stale tier-1 + immaterial pending) — "
        "conditional render predicate at "
        "swing/rendering/briefing_md.py is broken OR the SQL filter "
        "predicates in _step_export changed and admit stale/immaterial rows."
    )
    # CLI hints (only rendered under the section) MUST also be absent.
    assert "list-pending-ambiguities" not in md, (
        "briefing.md leaks list-pending-ambiguities CLI hint under "
        "empty-state fixture"
    )
    assert "resolve-ambiguity" not in md, (
        "briefing.md leaks resolve-ambiguity CLI hint under empty-state "
        "fixture"
    )
