"""Phase 12 C.D T-D.6 — CLI: ``swing journal reconcile-backfill`` scaffold.

Per plan §E.6 acceptance criteria — scaffold for the backfill orchestrator
that consumes unresolved discrepancies + dispatches Pass-1 / Pass-2
classification + tier-1 auto-apply + tier-2 stamp. T-D.6 scaffolds only
the iteration shell + ``BackfillPipelineActiveError`` guard + filter
behavior + dry-run-vs-apply-mode dispatch + Click mutually-exclusive
flag rejection.

Per-discrepancy classification logic + Pass-1 / Pass-2 mechanics are
deferred to T-D.7 + T-D.8 + T-D.9 (the ``_classify_and_apply`` callback
is a stub at T-D.6).

Discriminating tests:
  1. Dry-run with no ``--apply`` is the default + does NOT mutate journal.
  2. ``--apply --dry-run`` BOTH: Click rejects with usage error.
  3. Empty unresolved set: prints ``(no unresolved discrepancies)`` exit 0.
  4. ``--ticker DHC`` filter scopes iteration to DHC-only.
  5. ``BackfillPipelineActiveError``: plant pipeline_runs row with
     state='running'; invoke run_backfill; assert it raises.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


@pytest.fixture
def cli_workspace(tmp_path: Path):
    """Create a project + home dir + run db-migrate to land schema v19."""
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    r = runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    assert r.exit_code == 0, r.output
    db_path = home / "swing-data" / "swing.db"
    return runner, cfg, db_path


def _seed_reconciliation_run(conn: sqlite3.Connection) -> int:
    """Insert a minimal reconciliation_runs row + return run_id."""
    cur = conn.execute(
        "INSERT INTO reconciliation_runs ("
        "  source, started_ts, state, period_start, period_end"
        ") VALUES (?, ?, ?, ?, ?)",
        ("tos_csv", "2026-05-16T10:00:00", "completed",
         "2026-05-10", "2026-05-16"),
    )
    return int(cur.lastrowid)


def _plant_unresolved(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    ticker: str,
    discrepancy_type: str = "entry_price_mismatch",
    field_name: str = "price",
    created_at: str = "2026-05-16T10:05:00",
) -> int:
    """Insert one ``resolution='unresolved'`` discrepancy + return id."""
    cur = conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "  run_id, discrepancy_type, ticker, field_name, "
        "  material_to_review, resolution, created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            run_id, discrepancy_type, ticker, field_name,
            1, "unresolved", created_at,
        ),
    )
    return int(cur.lastrowid)


# ============================================================================
# CLI surface — Click flag interaction + default behavior
# ============================================================================


def test_dry_run_is_default_no_apply_flag(cli_workspace):
    """Per plan §E.6 #2 + discriminating test #1 — default is --dry-run."""
    runner, cfg, _db = cli_workspace
    r = runner.invoke(
        main, ["--config", str(cfg), "journal", "reconcile-backfill"],
    )
    assert r.exit_code == 0, r.output
    # Even with no discrepancies the empty-set message fires (not a crash).
    assert "(no unresolved discrepancies)" in r.output


def test_apply_and_dry_run_mutually_exclusive(cli_workspace):
    """Per plan §E.6 #3 + discriminating test #2 — both flags rejected."""
    runner, cfg, _db = cli_workspace
    r = runner.invoke(
        main, [
            "--config", str(cfg), "journal", "reconcile-backfill",
            "--apply", "--dry-run",
        ],
    )
    assert r.exit_code != 0
    # Click usage-error wording mentions the mutually exclusive constraint.
    assert "mutually exclusive" in r.output.lower() or "--apply" in r.output


def test_empty_unresolved_set_message(cli_workspace):
    """Discriminating test #3 — empty set → ``(no unresolved discrepancies)``."""
    runner, cfg, _db = cli_workspace
    r = runner.invoke(
        main, [
            "--config", str(cfg), "journal", "reconcile-backfill",
            "--dry-run",
        ],
    )
    assert r.exit_code == 0, r.output
    assert "(no unresolved discrepancies)" in r.output


def test_ticker_filter_scopes_iteration(cli_workspace):
    """Discriminating test #4 — --ticker DHC scopes the iteration."""
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        _plant_unresolved(conn, run_id, ticker="DHC")
        _plant_unresolved(conn, run_id, ticker="VSAT")
        _plant_unresolved(conn, run_id, ticker="CVGI")
        conn.commit()
    finally:
        conn.close()

    r = runner.invoke(
        main, [
            "--config", str(cfg), "journal", "reconcile-backfill",
            "--dry-run", "--ticker", "DHC",
        ],
    )
    assert r.exit_code == 0, r.output
    assert "DHC" in r.output
    assert "VSAT" not in r.output
    assert "CVGI" not in r.output


def test_ticker_filter_unscoped_shows_all(cli_workspace):
    """Sanity peer to test_ticker_filter_scopes_iteration: unscoped shows all."""
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        _plant_unresolved(conn, run_id, ticker="DHC")
        _plant_unresolved(conn, run_id, ticker="VSAT")
        conn.commit()
    finally:
        conn.close()

    r = runner.invoke(
        main, [
            "--config", str(cfg), "journal", "reconcile-backfill",
            "--dry-run",
        ],
    )
    assert r.exit_code == 0, r.output
    assert "DHC" in r.output
    assert "VSAT" in r.output


# ============================================================================
# Helper module — BackfillPipelineActiveError + iteration shell
# ============================================================================


def test_backfill_pipeline_active_error_raises(cli_workspace):
    """Discriminating test #5 — pipeline running → BackfillPipelineActiveError."""
    from swing.trades.reconciliation_backfill import (
        BackfillPipelineActiveError,
        run_backfill,
    )

    _runner, _cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        # Plant a pipeline_runs row with state='running'.
        conn.execute(
            "INSERT INTO pipeline_runs ("
            "  started_ts, state, trigger, data_asof_date, "
            "  action_session_date, lease_token"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            (
                "2026-05-16T10:00:00", "running", "manual",
                "2026-05-16", "2026-05-16", "test-lease-token",
            ),
        )
        conn.commit()

        with pytest.raises(BackfillPipelineActiveError):
            run_backfill(
                conn,
                dry_run=True,
                schwab_client=None,
                environment="production",
                account_hash=None,
            )
    finally:
        conn.close()


def test_backfill_pipeline_active_message_mentions_run_id(cli_workspace):
    """The error message names the active pipeline run for operator action."""
    from swing.trades.reconciliation_backfill import (
        BackfillPipelineActiveError,
        run_backfill,
    )

    _runner, _cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO pipeline_runs ("
            "  started_ts, state, trigger, data_asof_date, "
            "  action_session_date, lease_token"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            (
                "2026-05-16T10:00:00", "running", "manual",
                "2026-05-16", "2026-05-16", "test-lease-token",
            ),
        )
        run_id = int(cur.lastrowid)
        conn.commit()

        with pytest.raises(BackfillPipelineActiveError) as exc_info:
            run_backfill(
                conn,
                dry_run=True,
                schwab_client=None,
                environment="production",
                account_hash=None,
            )
        assert str(run_id) in str(exc_info.value)
    finally:
        conn.close()


def test_run_backfill_signature_keyword_only_post_star():
    """Plan §E.6 #4 — required-first then defaulted keyword-only after `*`."""
    import inspect

    from swing.trades.reconciliation_backfill import run_backfill

    sig = inspect.signature(run_backfill)
    params = list(sig.parameters.values())
    # ``conn`` is the single positional-or-keyword param.
    assert params[0].name == "conn"
    assert params[0].kind in (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )
    # Remaining params are keyword-only.
    for p in params[1:]:
        assert p.kind == inspect.Parameter.KEYWORD_ONLY, (
            f"param {p.name!r} should be keyword-only; got {p.kind}"
        )
    # Required-first then defaulted ordering check: every required param
    # (no default) appears before any defaulted param.
    seen_default = False
    for p in params[1:]:
        if p.default is inspect.Parameter.empty:
            assert not seen_default, (
                f"required keyword param {p.name!r} appears after a "
                f"defaulted one — violates required-first ordering"
            )
        else:
            seen_default = True


def test_backfill_summary_dataclass_fields():
    """Plan §E.6 #5 — BackfillSummary has all required counter fields."""
    from swing.trades.reconciliation_backfill import BackfillSummary

    s = BackfillSummary()
    assert s.tier1_applied == 0
    assert s.tier2_stamped == 0
    assert s.tier_errored == 0
    assert s.pass_2_failed == 0
    assert s.skipped_already_resolved == 0
    assert s.skipped_pass_2_failed == 0
    assert s.per_discrepancy_outcomes == []


def test_backfill_outcome_dataclass_fields():
    """Plan §E.6 #6 — BackfillOutcome carries the per-row outcome record."""
    from swing.trades.reconciliation_backfill import BackfillOutcome

    o = BackfillOutcome(
        discrepancy_id=42,
        ticker="DHC",
        discrepancy_type="entry_price_mismatch",
        tier=1,
        outcome="tier1_applied",
    )
    assert o.discrepancy_id == 42
    assert o.ticker == "DHC"
    assert o.discrepancy_type == "entry_price_mismatch"
    assert o.tier == 1
    assert o.outcome == "tier1_applied"
    # Optional fields default sanely.
    assert o.ambiguity_kind is None
    assert o.correction_id is None
    assert o.pass_2_call_id is None
    assert o.reason is None


def test_run_backfill_returns_summary_for_empty_set(cli_workspace):
    """run_backfill returns a BackfillSummary instance even with no rows."""
    from swing.trades.reconciliation_backfill import (
        BackfillSummary,
        run_backfill,
    )

    _runner, _cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        summary = run_backfill(
            conn,
            dry_run=True,
            schwab_client=None,
            environment="production",
            account_hash=None,
        )
        assert isinstance(summary, BackfillSummary)
        assert summary.per_discrepancy_outcomes == []
    finally:
        conn.close()


def test_run_backfill_iteration_visits_unresolved_rows(cli_workspace):
    """T-D.6 scaffold iterates unresolved discrepancies + emits per-row outcomes.

    Per-discrepancy classification logic is T-D.7+. T-D.6 stub returns
    ``outcome='projection'`` for dry-run mode (placeholder).
    """
    from swing.trades.reconciliation_backfill import run_backfill

    _runner, _cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        _plant_unresolved(conn, run_id, ticker="DHC")
        _plant_unresolved(conn, run_id, ticker="VSAT")
        conn.commit()

        summary = run_backfill(
            conn,
            dry_run=True,
            schwab_client=None,
            environment="production",
            account_hash=None,
        )
        assert len(summary.per_discrepancy_outcomes) == 2
        tickers = {o.ticker for o in summary.per_discrepancy_outcomes}
        assert tickers == {"DHC", "VSAT"}
    finally:
        conn.close()


def test_run_backfill_ticker_kwarg_filters_iteration(cli_workspace):
    """The ``ticker`` kwarg restricts the iteration set."""
    from swing.trades.reconciliation_backfill import run_backfill

    _runner, _cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        _plant_unresolved(conn, run_id, ticker="DHC")
        _plant_unresolved(conn, run_id, ticker="VSAT")
        conn.commit()

        summary = run_backfill(
            conn,
            dry_run=True,
            schwab_client=None,
            environment="production",
            account_hash=None,
            ticker="DHC",
        )
        assert len(summary.per_discrepancy_outcomes) == 1
        assert summary.per_discrepancy_outcomes[0].ticker == "DHC"
    finally:
        conn.close()


def test_run_backfill_limit_kwarg_caps_iteration(cli_workspace):
    """The ``limit`` kwarg caps the iteration count."""
    from swing.trades.reconciliation_backfill import run_backfill

    _runner, _cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        _plant_unresolved(conn, run_id, ticker="DHC")
        _plant_unresolved(conn, run_id, ticker="VSAT")
        _plant_unresolved(conn, run_id, ticker="CVGI")
        conn.commit()

        summary = run_backfill(
            conn,
            dry_run=True,
            schwab_client=None,
            environment="production",
            account_hash=None,
            limit=2,
        )
        assert len(summary.per_discrepancy_outcomes) == 2
    finally:
        conn.close()
