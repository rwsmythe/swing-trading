"""Phase 12 C.D T-D.7 — backfill Pass 1 persisted-JSON-only classification.

Per plan §E.7 acceptance criteria #1-6:

  1. Pass 1 reads each unresolved discrepancy's ``expected_value_json``
     + ``actual_value_json`` + the FK-referenced journal row.
  2. Pass 1 invokes ``classify_discrepancy`` with ``validator_chain=None``
     (defense-in-depth at C.C apply-time per writing-plans LOCK).
  3. Pass 1 sufficient for 8 of 10 discrepancy_types per spec §8.4 table;
     INSUFFICIENT for ``unmatched_open_fill`` + ``unmatched_close_fill``
     which emit ``_pass_2_required=True`` substring in
     ``correction_reason`` — backfill reads this signal + records a
     ``'pass_2_pending'`` placeholder for T-D.8.
  4. Dry-run prints projected classification matrix per acceptance
     criterion #4 sample layout.
  5. Apply mode dispatches via PUBLIC ``apply_tier1_correction`` (own-tx)
     OR PUBLIC ``stamp_pending_ambiguity`` (own-tx). NO backfill-owned
     ``BEGIN IMMEDIATE``. ``environment='sandbox'`` propagates end-to-end
     so sandbox short-circuit at C.C inner fires (no journal mutation;
     no ``reconciliation_corrections`` row; outcome records as
     ``'tier1_skipped_sandbox'``).
  6. Discriminating tests cover CVGI tier-1 (dry-run + --apply),
     DHC ``unmatched_open_fill`` Pass-2-required placeholder, sector
     tamper tier-2 stamp, and sandbox short-circuit.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from swing.data.db import ensure_schema
from swing.trades.reconciliation_backfill import (
    BackfillOutcome,
    BackfillSummary,
    format_projection_row,
    format_projection_table_header,
    run_backfill,
)


# ---------------------------------------------------------------------------
# Test scaffold — minimal v19 schema + fixture seeds
# ---------------------------------------------------------------------------


@pytest.fixture
def v19_db(tmp_path: Path) -> sqlite3.Connection:
    """Create + return a sqlite3 connection to a fresh v19 schema."""
    db_path = tmp_path / "swing.db"
    ensure_schema(db_path).close()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _seed_reconciliation_run(conn: sqlite3.Connection) -> int:
    """Minimal reconciliation_runs row for FK satisfaction."""
    cur = conn.execute(
        "INSERT INTO reconciliation_runs ("
        "  source, started_ts, state, period_start, period_end"
        ") VALUES (?, ?, ?, ?, ?)",
        ("schwab_api", "2026-05-16T10:00:00", "completed",
         "2026-05-10", "2026-05-16"),
    )
    conn.commit()
    return int(cur.lastrowid)


def _seed_cvgi_trade_and_fill(
    conn: sqlite3.Connection, *, journal_price: float = 5.23,
) -> dict[str, int]:
    """Plant CVGI: trade + entry-fill at price=journal_price.

    Mirrors ``tests/integration/test_phase12_bundle_c_cvgi_41_full_pipeline.py::
    _seed_cvgi_world`` shape so the existing C.C dispatch helpers + the
    classifier's Shape-A predicate (persisted-JSON-only ``{'price': X}``)
    align with our seed.
    """
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("CVGI", "2026-04-27", journal_price, 100, 4.0, 4.0, "managing",
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
        (trade_id, "2026-04-27T14:23:00", "entry", 100.0, journal_price,
         "unreconciled"),
    )
    fill_id = int(fcur.lastrowid)
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)
    conn.commit()
    return {"trade_id": trade_id, "fill_id": fill_id}


def _seed_cvgi_entry_price_mismatch_disc(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    trade_id: int,
    fill_id: int,
    schwab_price: float = 5.30,
    journal_price: float = 5.23,
) -> int:
    """Plant a CVGI entry_price_mismatch tier-1-eligible discrepancy.

    Uses the V1 shipped emitter shape (``actual_value_json={"price": X}``,
    Shape A in classifier's predicate at C.B
    ``_classify_entry_price_mismatch``).
    """
    import json
    cur = conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "  run_id, discrepancy_type, trade_id, fill_id, ticker, "
        "  field_name, expected_value_json, actual_value_json, "
        "  delta_text, material_to_review, resolution, created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id, "entry_price_mismatch", trade_id, fill_id, "CVGI",
            "price",
            json.dumps({"price": journal_price}),
            json.dumps({"price": schwab_price}),
            f"+${schwab_price - journal_price:.2f} (schwab minus journal)",
            1, "unresolved", "2026-05-16T10:05:00",
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def _seed_dhc_trade_and_fill(conn: sqlite3.Connection) -> dict[str, int]:
    """DHC trade + entry fill (price doesn't matter — Pass-1 cannot
    enumerate Schwab candidates so classifier emits
    tier-2 unsupported with ``_pass_2_required=True``)."""
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("DHC", "2026-04-15", 7.50, 50, 7.0, 7.0, "managing",
         "manual_off_pipeline", "2026-04-15T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    fcur = conn.execute(
        """
        INSERT INTO fills (
            trade_id, fill_datetime, action, quantity, price,
            reconciliation_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (trade_id, "2026-04-15T13:00:00", "entry", 50.0, 7.50,
         "unreconciled"),
    )
    fill_id = int(fcur.lastrowid)
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)
    conn.commit()
    return {"trade_id": trade_id, "fill_id": fill_id}


def _seed_dhc_unmatched_open_fill_disc(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    trade_id: int,
    fill_id: int,
) -> int:
    """Plant DHC unmatched_open_fill — Pass 1 must emit
    ``_pass_2_required=True`` substring per spec §10.2."""
    import json
    cur = conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "  run_id, discrepancy_type, trade_id, fill_id, ticker, "
        "  field_name, expected_value_json, actual_value_json, "
        "  material_to_review, resolution, created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id, "unmatched_open_fill", trade_id, fill_id, "DHC",
            "match",
            json.dumps({"fill_datetime": "2026-04-15T13:00:00"}),
            json.dumps({"matched": None}),
            1, "unresolved", "2026-05-16T10:06:00",
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def _seed_sector_tamper_disc(
    conn: sqlite3.Connection, *, run_id: int, trade_id: int,
) -> int:
    """Plant a sector_tamper discrepancy — C.B sub-classifier emits
    tier-2 ``unknown_schwab_subtype`` (NOT pass-2-required)."""
    import json
    cur = conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "  run_id, discrepancy_type, trade_id, ticker, field_name, "
        "  expected_value_json, actual_value_json, "
        "  material_to_review, resolution, created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id, "sector_tamper", trade_id, "CVGI", "sector",
            json.dumps({"sector": "Energy"}),
            json.dumps({"sector": "Technology"}),
            0, "unresolved", "2026-05-16T10:07:00",
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


# ---------------------------------------------------------------------------
# CVGI tier-1 — dry-run projection
# ---------------------------------------------------------------------------


def test_cvgi_tier1_dry_run_projection(v19_db: sqlite3.Connection) -> None:
    """Acceptance criterion #4 — dry-run prints projection matrix for
    a CVGI entry_price_mismatch tier-1-eligible discrepancy."""
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_cvgi_trade_and_fill(v19_db, journal_price=5.23)
    disc_id = _seed_cvgi_entry_price_mismatch_disc(
        v19_db, run_id=run_id, schwab_price=5.30, journal_price=5.23,
        **seed,
    )

    # Read pre-state for journal-not-mutated assertion.
    pre_price = v19_db.execute(
        "SELECT price FROM fills WHERE fill_id = ?", (seed["fill_id"],),
    ).fetchone()[0]
    assert pre_price == 5.23

    summary = run_backfill(
        v19_db,
        dry_run=True,
        schwab_client=None,
        environment="production",
        account_hash=None,
    )

    # Discriminating: a tier-1 projection emitted; no journal mutation.
    assert summary.projection_tier1 == 1
    assert summary.tier1_applied == 0
    assert len(summary.per_discrepancy_outcomes) == 1
    out = summary.per_discrepancy_outcomes[0]
    assert out.discrepancy_id == disc_id
    assert out.tier == 1
    assert out.outcome == "projection_tier1"
    assert out.projection_outcome_label == "tier-1 auto-apply"
    assert out.projection_action_needed == "(none)"

    # Journal not mutated.
    post_price = v19_db.execute(
        "SELECT price FROM fills WHERE fill_id = ?", (seed["fill_id"],),
    ).fetchone()[0]
    assert post_price == 5.23

    # No correction row was written.
    n = v19_db.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0]
    assert n == 0


# ---------------------------------------------------------------------------
# CVGI tier-1 — --apply path
# ---------------------------------------------------------------------------


def test_cvgi_tier1_apply_writes_correction(v19_db: sqlite3.Connection) -> None:
    """Acceptance criteria #5 + #6 — --apply path actually mutates
    fills.price via PUBLIC apply_tier1_correction (own-tx)."""
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_cvgi_trade_and_fill(v19_db, journal_price=5.23)
    disc_id = _seed_cvgi_entry_price_mismatch_disc(
        v19_db, run_id=run_id, schwab_price=5.30, journal_price=5.23,
        **seed,
    )

    summary = run_backfill(
        v19_db,
        dry_run=False,
        schwab_client=None,
        environment="production",
        account_hash=None,
    )

    assert summary.tier1_applied == 1
    assert summary.projection_tier1 == 0  # NOT dry-run.
    out = summary.per_discrepancy_outcomes[0]
    assert out.tier == 1
    assert out.outcome == "tier1_applied"
    assert out.correction_id is not None
    assert out.discrepancy_id == disc_id

    # fills.price actually mutated to Schwab value.
    post_price = v19_db.execute(
        "SELECT price FROM fills WHERE fill_id = ?", (seed["fill_id"],),
    ).fetchone()[0]
    assert post_price == 5.30

    # reconciliation_corrections row was written.
    n = v19_db.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0]
    assert n == 1

    # discrepancy flipped to auto_corrected_from_schwab.
    res = v19_db.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (disc_id,),
    ).fetchone()[0]
    assert res == "auto_corrected_from_schwab"


# ---------------------------------------------------------------------------
# DHC unmatched_open_fill — Pass 1 emits _pass_2_required placeholder
# ---------------------------------------------------------------------------


def test_dhc_unmatched_open_fill_records_pass_2_pending_placeholder(
    v19_db: sqlite3.Connection,
) -> None:
    """Acceptance criterion #3 — unmatched_open_fill Pass 1 cannot
    enumerate candidates from persisted JSON; classifier emits
    ``_pass_2_required=True`` substring in correction_reason; T-D.7
    records ``outcome='pass_2_pending'`` placeholder for T-D.8."""
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_dhc_trade_and_fill(v19_db)
    disc_id = _seed_dhc_unmatched_open_fill_disc(
        v19_db, run_id=run_id, **seed,
    )

    # --apply mode is the interesting branch — placeholder must be
    # recorded; no journal mutation; T-D.8 will overwrite.
    summary = run_backfill(
        v19_db,
        dry_run=False,
        schwab_client=None,
        environment="production",
        account_hash=None,
    )

    assert summary.pass_2_pending == 1
    assert summary.tier1_applied == 0
    assert summary.tier2_stamped == 0
    out = summary.per_discrepancy_outcomes[0]
    assert out.discrepancy_id == disc_id
    assert out.outcome == "pass_2_pending"
    assert out.tier is None
    # Discriminating: the reason mentions T-D.8 / Pass 2 forward link.
    assert "Pass 2" in (out.reason or "") or "_pass_2_required" in (
        out.reason or ""
    ) or "T-D.8" in (out.reason or "")

    # Journal not mutated; no correction row.
    n_corr = v19_db.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0]
    assert n_corr == 0
    res = v19_db.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (disc_id,),
    ).fetchone()[0]
    assert res == "unresolved"  # T-D.8 will flip it.


def test_dhc_unmatched_open_fill_dry_run_projection(
    v19_db: sqlite3.Connection,
) -> None:
    """Dry-run for Pass-2-required shows "Pass 2 required" projection."""
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_dhc_trade_and_fill(v19_db)
    _seed_dhc_unmatched_open_fill_disc(v19_db, run_id=run_id, **seed)

    summary = run_backfill(
        v19_db,
        dry_run=True,
        schwab_client=None,
        environment="production",
        account_hash=None,
    )
    assert summary.projection_pass_2 == 1
    out = summary.per_discrepancy_outcomes[0]
    assert out.outcome == "projection_pass_2"
    assert out.projection_outcome_label == "Pass 2 required (re-fetch)"
    assert out.projection_action_needed == "--apply or --no-pass-2"


# ---------------------------------------------------------------------------
# Sector tamper — Pass 1 tier-2 stamp
# ---------------------------------------------------------------------------


def test_sector_tamper_tier2_stamp(v19_db: sqlite3.Connection) -> None:
    """Acceptance criterion #6 — sector_tamper Pass 1 emits tier-2 via
    C.B sub-classifier; backfill stamps via PUBLIC
    stamp_pending_ambiguity (own-tx)."""
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_cvgi_trade_and_fill(v19_db, journal_price=5.23)
    disc_id = _seed_sector_tamper_disc(
        v19_db, run_id=run_id, trade_id=seed["trade_id"],
    )

    summary = run_backfill(
        v19_db,
        dry_run=False,
        schwab_client=None,
        environment="production",
        account_hash=None,
    )

    assert summary.tier2_stamped == 1
    out = summary.per_discrepancy_outcomes[0]
    assert out.discrepancy_id == disc_id
    assert out.tier == 2
    assert out.outcome == "tier2_stamped"
    # C.B sector_tamper sub-classifier produces unknown_schwab_subtype.
    assert out.ambiguity_kind == "unknown_schwab_subtype"

    # discrepancy resolution flipped to pending_ambiguity_resolution +
    # ambiguity_kind populated.
    row = v19_db.execute(
        "SELECT resolution, ambiguity_kind "
        "FROM reconciliation_discrepancies WHERE discrepancy_id = ?",
        (disc_id,),
    ).fetchone()
    assert row[0] == "pending_ambiguity_resolution"
    assert row[1] == "unknown_schwab_subtype"


# ---------------------------------------------------------------------------
# Sandbox short-circuit — tier-1-eligible, environment='sandbox'
# ---------------------------------------------------------------------------


def test_sandbox_short_circuit_on_tier1_eligible(
    v19_db: sqlite3.Connection,
) -> None:
    """Acceptance criterion §0 sandbox discriminating test — environment
    propagates end-to-end; C.C inner short-circuits; no journal
    mutation; no correction row; BackfillSummary.tier1_applied == 0."""
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_cvgi_trade_and_fill(v19_db, journal_price=5.23)
    _seed_cvgi_entry_price_mismatch_disc(
        v19_db, run_id=run_id, schwab_price=5.30, journal_price=5.23,
        **seed,
    )

    summary = run_backfill(
        v19_db,
        dry_run=False,
        schwab_client=None,
        environment="sandbox",  # discriminating.
        account_hash=None,
    )

    # Sandbox short-circuit: tier-1 dispatched but inner short-circuited.
    assert summary.tier1_applied == 0
    assert summary.tier1_skipped_sandbox == 1
    out = summary.per_discrepancy_outcomes[0]
    assert out.tier == 1
    assert out.outcome == "tier1_skipped_sandbox"

    # No journal mutation.
    post_price = v19_db.execute(
        "SELECT price FROM fills WHERE fill_id = ?", (seed["fill_id"],),
    ).fetchone()[0]
    assert post_price == 5.23

    # No correction row.
    n = v19_db.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0]
    assert n == 0


# ---------------------------------------------------------------------------
# Validator chain — INTENTIONAL None on Pass 1
# ---------------------------------------------------------------------------


def test_pass_1_invokes_classifier_with_validator_chain_None(
    v19_db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acceptance criterion #2 — INTENTIONAL ``validator_chain=None``.

    Defense-in-depth re-invocation lives at C.C apply-time (spec §5.4
    step 3); backfill must NOT pre-validate. Discriminating: spy on
    ``classify_discrepancy`` callsite and assert kwarg is None.
    """
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_cvgi_trade_and_fill(v19_db, journal_price=5.23)
    _seed_cvgi_entry_price_mismatch_disc(
        v19_db, run_id=run_id, schwab_price=5.30, journal_price=5.23,
        **seed,
    )

    import swing.trades.reconciliation_backfill as backfill_mod
    from swing.trades.reconciliation_classifier import (
        classify_discrepancy as real_classify,
    )

    captured: list[dict[str, Any]] = []

    def spy_classify(disc, **kwargs):
        captured.append({"discrepancy_id": disc.discrepancy_id, **kwargs})
        return real_classify(disc, **kwargs)

    # _classify_and_apply imports classify_discrepancy lazily — patch
    # the source module so the lazy import resolves to our spy.
    monkeypatch.setattr(
        "swing.trades.reconciliation_classifier.classify_discrepancy",
        spy_classify,
    )

    # Run backfill in dry-run (mutation-free; spy still captures call).
    backfill_mod.run_backfill(
        v19_db,
        dry_run=True,
        schwab_client=None,
        environment="production",
        account_hash=None,
    )

    assert len(captured) == 1
    # BINDING — validator_chain MUST be None on Pass 1.
    assert "validator_chain" in captured[0]
    assert captured[0]["validator_chain"] is None


# ---------------------------------------------------------------------------
# Projection matrix rendering — formatter shape
# ---------------------------------------------------------------------------


def test_format_projection_table_header_shape() -> None:
    """Header carries the 5 column labels per acceptance criterion #4."""
    h = format_projection_table_header()
    assert "ID" in h
    assert "Ticker" in h
    assert "Type" in h
    assert "Projected outcome" in h
    assert "Action needed" in h


def test_format_projection_row_renders_tier1_label() -> None:
    """Tier-1 row renders "tier-1 auto-apply" + "(none)" action."""
    out = BackfillOutcome(
        discrepancy_id=41,
        ticker="CVGI",
        discrepancy_type="entry_price_mismatch",
        tier=1,
        outcome="projection_tier1",
        projection_outcome_label="tier-1 auto-apply",
        projection_action_needed="(none)",
    )
    rendered = format_projection_row(out)
    assert "41" in rendered
    assert "CVGI" in rendered
    assert "entry_price_mismatch" in rendered
    assert "tier-1 auto-apply" in rendered
    assert "(none)" in rendered


def test_format_projection_row_renders_pass_2_label() -> None:
    """Pass-2-required row renders "Pass 2 required (re-fetch)"."""
    out = BackfillOutcome(
        discrepancy_id=39,
        ticker="DHC",
        discrepancy_type="unmatched_open_fill",
        tier=None,
        outcome="projection_pass_2",
        projection_outcome_label="Pass 2 required (re-fetch)",
        projection_action_needed="--apply or --no-pass-2",
    )
    rendered = format_projection_row(out)
    assert "39" in rendered
    assert "DHC" in rendered
    assert "Pass 2 required (re-fetch)" in rendered
    assert "--apply or --no-pass-2" in rendered


# ---------------------------------------------------------------------------
# Counter wiring — BackfillSummary aggregates per-outcome
# ---------------------------------------------------------------------------


def test_summary_counter_wiring_mixed_outcomes(
    v19_db: sqlite3.Connection,
) -> None:
    """Plant CVGI tier-1 + DHC pass-2-pending + sector_tamper tier-2;
    assert all three counters increment correctly under --apply."""
    run_id = _seed_reconciliation_run(v19_db)
    cvgi = _seed_cvgi_trade_and_fill(v19_db, journal_price=5.23)
    _seed_cvgi_entry_price_mismatch_disc(
        v19_db, run_id=run_id, schwab_price=5.30, journal_price=5.23,
        **cvgi,
    )
    dhc = _seed_dhc_trade_and_fill(v19_db)
    _seed_dhc_unmatched_open_fill_disc(v19_db, run_id=run_id, **dhc)
    _seed_sector_tamper_disc(
        v19_db, run_id=run_id, trade_id=cvgi["trade_id"],
    )

    summary = run_backfill(
        v19_db,
        dry_run=False,
        schwab_client=None,
        environment="production",
        account_hash=None,
    )

    assert summary.tier1_applied == 1
    assert summary.pass_2_pending == 1
    assert summary.tier2_stamped == 1
    assert len(summary.per_discrepancy_outcomes) == 3
    assert isinstance(summary, BackfillSummary)
