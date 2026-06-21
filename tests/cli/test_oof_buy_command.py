"""CLI: `swing journal oof-buy` (Phase-18 deferred follow-up #1).

Tests (per docs/plans/oof-buy-command-plan.md §4, AMENDED by brief e4ae1459 --
the RD fail-loud idempotency course-correction):
  - R1   the registry guard (non-OOF ticker -> ClickException; positive SPCX
         accepted; lower-case accepted with the canonical ref) -- seeded via the
         REAL overrides path (O1: the command reads apply_overrides, NOT bare
         config; a bare-config read would reject EVERY ticker).
  - I1   idempotency = FAIL LOUD (amended): a bare re-run (no --force) on a
         sentinel-ref collision is REJECTED with an actionable message naming the
         existing row, and STILL exactly one row (no double-record, no silent
         drop); --force records a genuinely-distinct second same-key buy under a
         DISTINCT oof: ref that STILL self-reconciles in the step-7 matcher.
  - SB1  sandbox (no domain row written; production writes one; AND a non-OOF
         ticker under sandbox STILL rejects -- the write-scoped gate proof).

The amendment SUPERSEDES the plan's silent-no-op idempotency (the old "same-cost
no-op vs different-cost conflict" distinction): because the sentinel key is
ticker+date (NO amount), a legitimately-distinct second same-ticker/same-day OOF
buy collided on the key and was SILENTLY DROPPED from the ledger (the #27
silent-ledger-loss class this arc exists to PREVENT). Now ANY collision without
--force fails loud (so the operator KNOWS nothing was recorded); --force records
the distinct second buy under a disambiguated ref.

The overrides path is exercised via write_user_overrides with USERPROFILE AND
HOME monkeypatched (the write_user_overrides gotcha) so apply_overrides
materializes the registry/env from disk -- the production read shape, not a
stubbed apply_overrides.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path: Path, monkeypatch, *, overrides: dict | None = None):
    """Build a minimal config + migrated DB; point USERPROFILE+HOME at home_dir
    so apply_overrides reads the seeded user-config.toml from there. Returns
    (runner, cfg_path, db_path)."""
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = _minimal_config(project, home)
    # Point the user-config home at the test home BEFORE writing overrides
    # (write_user_overrides + apply_overrides both read USERPROFILE/HOME).
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    if overrides is not None:
        from swing.config_user import write_user_overrides
        write_user_overrides(overrides)
    runner = CliRunner()
    r = runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    assert r.exit_code == 0, r.output
    db_path = home / "swing-data" / "swing.db"
    return runner, cfg, db_path


def _cash_rows(db_path: Path) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT id, date, kind, amount, ref, note FROM cash_movements "
            "ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


_SPCX_OVERRIDES = {"reconciliation": {"out_of_framework_tickers": ["SPCX"]}}


# --------------------------------------------------------------------------- #
# R1 — the registry guard
# --------------------------------------------------------------------------- #

def test_oof_buy_rejects_non_oof_ticker(tmp_path: Path, monkeypatch):
    """R1: a ticker NOT in out_of_framework_tickers -> ClickException; no row."""
    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch, overrides=_SPCX_OVERRIDES)
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "AAPL", "--cost", "100", "--date", "2026-06-18",
    ])
    assert r.exit_code != 0
    # The message names the rejected ticker + points to the registry section.
    assert "AAPL" in r.output
    assert "out_of_framework_tickers" in r.output
    assert _cash_rows(db_path) == []  # nothing written


def test_oof_buy_accepts_registered_ticker(tmp_path: Path, monkeypatch):
    """R1 positive: SPCX (in the registry) is accepted + writes the row.

    O1 discriminator: if the command read bare ctx.obj['config'] (the bug), the
    registry would be EMPTY (overrides not applied) and EVEN SPCX would be
    rejected -> this assertion FAILS. So it distinguishes the apply_overrides
    read from the bare-config bug.
    """
    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch, overrides=_SPCX_OVERRIDES)
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "SPCX", "--cost", "500", "--date", "2026-06-18",
    ])
    assert r.exit_code == 0, r.output
    rows = _cash_rows(db_path)
    assert len(rows) == 1
    _id, date, kind, amount, ref, _note = rows[0]
    assert (date, kind, amount, ref) == (
        "2026-06-18", "withdraw", 500.0, "oof:SPCX:2026-06-18")


def test_oof_buy_lower_case_ticker_accepted_canonical_ref(tmp_path: Path, monkeypatch):
    """R1 lower-case arm (the Codex R1 MAJOR coverage): `--ticker spcx` (lower)
    is ACCEPTED and writes a row whose ref is the CANONICAL upper-cased
    oof:SPCX:<d>.

    Pre-fix (no boundary upper-casing): rejected by the case-sensitive registry
    lookup ('spcx' in ('SPCX',) is False) and/or a non-canonical oof:spcx:... ref
    -> FAILS. Post-fix: accepted with the canonical ref.
    """
    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch, overrides=_SPCX_OVERRIDES)
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "spcx", "--cost", "500", "--date", "2026-06-18",
    ])
    assert r.exit_code == 0, r.output
    rows = _cash_rows(db_path)
    assert len(rows) == 1
    assert rows[0][4] == "oof:SPCX:2026-06-18"  # canonical upper-cased ref


# --------------------------------------------------------------------------- #
# I1 — idempotency = FAIL LOUD (amended brief e4ae1459)
# --------------------------------------------------------------------------- #

def test_oof_buy_bare_rerun_fails_loud_no_double_record(tmp_path: Path, monkeypatch):
    """I1 (AMENDED): a bare re-run (no --force) on a sentinel-ref collision is
    REJECTED with an actionable message naming the existing row, AND there is
    STILL exactly ONE cash_movements row (no double-record). The operator KNOWS
    nothing new was recorded.

    PRE-correction (the silent-no-op hole): the second run was a clean exit-0
    'already recorded' no-op -> a legitimately-distinct second same-day buy was
    SILENTLY DROPPED from the ledger (the #27 silent-ledger-loss class). So this
    test's non-zero-exit + actionable-message assertion FAILS against the
    pre-correction code. POST-correction: a non-zero exit + the actionable
    message + the escape-hatch pointer. DISTINGUISHES.
    """
    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch, overrides=_SPCX_OVERRIDES)
    args = [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "SPCX", "--cost", "500", "--date", "2026-06-18",
    ]
    r1 = runner.invoke(main, args)
    assert r1.exit_code == 0, r1.output
    assert len(_cash_rows(db_path)) == 1
    # The bare re-run (identical args) MUST fail loud -- not a silent no-op.
    r2 = runner.invoke(main, args)
    assert r2.exit_code != 0, r2.output                 # rejected, not exit 0
    assert "already exists" in r2.output.lower()        # actionable collision msg
    assert "#1" in r2.output                            # names the existing row id
    assert "--force" in r2.output                       # the escape hatch
    assert "oof:SPCX:2026-06-18" in r2.output           # names the colliding ref
    assert len(_cash_rows(db_path)) == 1                # STILL one row (no double)


def test_oof_buy_bare_rerun_different_cost_also_fails_loud(tmp_path: Path, monkeypatch):
    """I1 (AMENDED): a bare re-run with a DIFFERENT --cost ALSO fails loud (the
    amendment removed the same-cost-silent-no-op vs different-cost-conflict
    distinction -- ANY collision without --force is rejected). The original row
    is unchanged.

    PRE-correction: a different cost raised a CONFLICT (different message); a SAME
    cost was a silent no-op. POST-correction: BOTH are the same fail-loud
    'already exists' rejection (the operator uses --force for a deliberate second
    buy, or a distinct --date)."""
    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch, overrides=_SPCX_OVERRIDES)
    r1 = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "SPCX", "--cost", "500", "--date", "2026-06-18",
    ])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "SPCX", "--cost", "700", "--date", "2026-06-18",
    ])
    assert r2.exit_code != 0, r2.output
    assert "already exists" in r2.output.lower()
    assert "--force" in r2.output
    rows = _cash_rows(db_path)
    assert len(rows) == 1
    assert rows[0][3] == 500.0   # the ORIGINAL amount is unchanged (not 700)


def test_oof_buy_integrityerror_belt_fails_loud(tmp_path: Path, monkeypatch):
    """The IntegrityError belt (the TOCTOU-race fallback past the SELECT) ALSO
    fails loud -- it re-fetches the row that won the race and raises the SAME
    actionable collision error, consistent with the SELECT-first path. NEVER a
    silent no-op (amended brief §4 item 3).

    Simulate the race: the SELECT-first find_by_ref returns None (the row isn't
    visible yet), but a row already exists for the ref, so the INSERT hits
    ux_cash_ref -> IntegrityError -> the belt re-fetches + raises.

    PRE-correction: the belt echoed 'already recorded' + exited 0 on a same cost
    (silent), only conflicting on a different cost. POST-correction: the belt
    fails loud on ANY collision."""
    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch, overrides=_SPCX_OVERRIDES)
    # Pre-seed the race winner: an existing $500 OOF row for the same ref.
    r0 = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "SPCX", "--cost", "500", "--date", "2026-06-18",
    ])
    assert r0.exit_code == 0, r0.output

    # Force the SELECT-first find_by_ref to MISS once (simulate the race window),
    # so the command reaches the INSERT (-> IntegrityError -> the belt). (--force
    # would have re-disambiguated; this is a BARE re-run, so the SELECT-first
    # would normally catch it -- the patch forces the belt path.)
    import swing.data.repos.cash as _cash_repo
    _real_find = _cash_repo.find_by_ref
    calls = {"n": 0}

    def _racing_find(conn, ref):
        calls["n"] += 1
        if calls["n"] == 1:
            return None              # SELECT-first miss (the race window)
        return _real_find(conn, ref)  # the belt re-fetch sees the real row

    monkeypatch.setattr(_cash_repo, "find_by_ref", _racing_find)

    # A bare re-run (same cost) -> the INSERT collides; the belt must fail loud.
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "SPCX", "--cost", "500", "--date", "2026-06-18",
    ])
    assert r.exit_code != 0, r.output         # the belt raised, not exit 0
    assert "already exists" in r.output.lower()
    rows = _cash_rows(db_path)
    assert len(rows) == 1
    assert rows[0][3] == 500.0                # original unchanged (no double)


def test_oof_buy_mixed_case_rerun_fails_loud(tmp_path: Path, monkeypatch):
    """I1 mixed-case arm (preserved from the R1 fix, adapted to fail-loud): a
    lower-case re-run of the same key (`spcx` after `SPCX`) STILL collides + fails
    loud (both upper-case to the IDENTICAL canonical ref oof:SPCX:<d>).

    PRE the R1 case-normalization fix: the lower run would write oof:spcx:... (a
    SECOND row) -- the case-insensitivity bug. POST-fix (+ this amendment): the
    lower run normalizes to the same key and is rejected as a collision; STILL
    one row. DISTINGUISHES the boundary upper-casing AT the fail-loud layer."""
    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch, overrides=_SPCX_OVERRIDES)
    r1 = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "SPCX", "--cost", "500", "--date", "2026-06-18",
    ])
    assert r1.exit_code == 0, r1.output
    # Lower-case re-run of the SAME key -> normalizes to oof:SPCX:<d> -> collides.
    r2 = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "spcx", "--cost", "500", "--date", "2026-06-18",
    ])
    assert r2.exit_code != 0, r2.output
    assert "already exists" in r2.output.lower()
    rows = _cash_rows(db_path)
    assert len(rows) == 1                     # still ONE row (no case-split double)
    assert rows[0][4] == "oof:SPCX:2026-06-18"


# --------------------------------------------------------------------------- #
# --force — the escape hatch (amended brief e4ae1459)
# --------------------------------------------------------------------------- #

def test_oof_buy_force_records_distinct_second_row(tmp_path: Path, monkeypatch):
    """--force (AMENDED): a genuinely-distinct second same-key OOF buy is recorded
    under a DISTINCT oof: ref (the #<seq> disambiguator) -> TWO rows for the
    ticker/date, both withdraw, distinct amounts allowed.

    PRE-correction: there was no --force flag (and the second buy was silently
    dropped / errored). POST-correction: --force writes the second row under
    oof:SPCX:2026-06-18#2."""
    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch, overrides=_SPCX_OVERRIDES)
    r1 = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "SPCX", "--cost", "500", "--date", "2026-06-18",
    ])
    assert r1.exit_code == 0, r1.output
    # The distinct second buy (different cost), with --force.
    r2 = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "SPCX", "--cost", "250", "--date", "2026-06-18", "--force",
    ])
    assert r2.exit_code == 0, r2.output
    rows = _cash_rows(db_path)
    assert len(rows) == 2                       # TWO rows now (no silent drop)
    refs = sorted(r[4] for r in rows)
    assert refs == ["oof:SPCX:2026-06-18", "oof:SPCX:2026-06-18#2"]
    # The #2 row carries the forced cost.
    forced = [r for r in rows if r[4] == "oof:SPCX:2026-06-18#2"][0]
    assert forced[3] == 250.0
    assert forced[2] == "withdraw"
    # A THIRD --force buy picks the NEXT free disambiguator (#3) deterministically.
    r3 = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "SPCX", "--cost", "100", "--date", "2026-06-18", "--force",
    ])
    assert r3.exit_code == 0, r3.output
    refs3 = sorted(r[4] for r in _cash_rows(db_path))
    assert refs3 == [
        "oof:SPCX:2026-06-18", "oof:SPCX:2026-06-18#2", "oof:SPCX:2026-06-18#3"]


def test_oof_buy_force_first_buy_uses_canonical_ref(tmp_path: Path, monkeypatch):
    """--force on a FIRST-ever buy (no existing row for the key) writes the
    canonical BARE ref (the natural seq-1) -- --force is well-defined and
    harmless when there is nothing to disambiguate against."""
    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch, overrides=_SPCX_OVERRIDES)
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "SPCX", "--cost", "500", "--date", "2026-06-18", "--force",
    ])
    assert r.exit_code == 0, r.output
    rows = _cash_rows(db_path)
    assert len(rows) == 1
    assert rows[0][4] == "oof:SPCX:2026-06-18"   # the canonical bare ref


def test_oof_buy_force_second_row_self_reconciles(tmp_path: Path, monkeypatch):
    """--force CRITICAL CONSTRAINT (amended brief §4 item 2a): the --force second
    row self-reconciles -- its cm.id does NOT fire cash_movement_mismatch across a
    reconciliation run. WITHOUT this, the disambiguated ref could silently
    re-introduce the recurring-mismatch bug (the exact bug this arc fixes).

    Records a canonical first buy + a --force second buy (-> oof:SPCX:<d>#2), then
    runs run_schwab_reconciliation directly against the SAME DB and asserts the
    #2 row's cm.id is NOT in the cash_movement_mismatch emit set. (The fixture has
    NO withdraw-typed Schwab counterpart in window, so WITHOUT the matcher
    recognizing the disambiguated ref the #2 row would emit.)"""
    from dataclasses import dataclass
    from typing import Any

    from swing.data.db import connect
    from swing.trades.schwab_reconciliation import run_schwab_reconciliation

    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch, overrides=_SPCX_OVERRIDES)
    d = "2026-06-18"
    r1 = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "SPCX", "--cost", "500", "--date", d,
    ])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "SPCX", "--cost", "250", "--date", d, "--force",
    ])
    assert r2.exit_code == 0, r2.output

    @dataclass
    class _Acct:
        net_liquidating_value: float | None = None
        positions: list[Any] | None = None

    @dataclass
    class _Txn:
        transaction_id: str
        transaction_date: str
        type: str
        net_amount: float
        description: str | None = None

    def _position(symbol, *, long_qty, market_value):
        return {
            "shortQuantity": 0.0, "longQuantity": long_qty,
            "instrument": {"symbol": symbol, "type": "EQUITY"},
            "marketValue": market_value,
        }

    conn = connect(db_path)
    try:
        force_id = conn.execute(
            "SELECT id FROM cash_movements WHERE ref=?",
            ("oof:SPCX:2026-06-18#2",),
        ).fetchone()[0]
        run = run_schwab_reconciliation(
            conn,
            account_hash="<acct>",
            period_start="2026-06-15",
            period_end="2026-06-20",
            schwab_orders=[],
            # The OOF buys' TRADE counterpart (skipped at ingest); NO
            # withdraw-typed tx in window -> without the matcher recognizing the
            # disambiguated ref, the #2 row would emit.
            schwab_transactions=[_Txn("115520131470", d, "TRADE", -750.0)],
            schwab_account=_Acct(
                net_liquidating_value=1450.0,
                positions=[_position("SPCX", long_qty=3.0, market_value=750.0)],
            ),
            out_of_framework_tickers=("SPCX",),
            starting_equity=700.0,
        )
        mismatch_ids = [
            r[0] for r in conn.execute(
                "SELECT cash_movement_id FROM reconciliation_discrepancies "
                "WHERE run_id=? AND discrepancy_type='cash_movement_mismatch'",
                (run.run_id,),
            ).fetchall()
        ]
    finally:
        conn.close()
    # The --force disambiguated row SELF-RECONCILES (recognized by the matcher).
    assert force_id not in mismatch_ids


# --------------------------------------------------------------------------- #
# SB1 — the sandbox test
# --------------------------------------------------------------------------- #

def _sandbox_overrides() -> dict:
    return {
        "reconciliation": {"out_of_framework_tickers": ["SPCX"]},
        "integrations": {"schwab": {"environment": "sandbox"}},
    }


def test_oof_buy_sandbox_writes_no_domain_row(tmp_path: Path, monkeypatch):
    """SB1: under environment != 'production', no cash_movements row written;
    the command echoes a sandbox advisory + exits 0."""
    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch, overrides=_sandbox_overrides())
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "SPCX", "--cost", "500", "--date", "2026-06-18",
    ])
    assert r.exit_code == 0, r.output
    assert "sandbox" in r.output.lower()
    assert _cash_rows(db_path) == []   # audit-only; no domain row


def test_oof_buy_production_writes_one_row(tmp_path: Path, monkeypatch):
    """SB1 parallel: the SAME args under production write exactly ONE row -- so
    the gate is proven env-conditional, not 'never writes'. (Base config defaults
    environment='production' when no [integrations.schwab] override is present.)"""
    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch, overrides=_SPCX_OVERRIDES)
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "SPCX", "--cost", "500", "--date", "2026-06-18",
    ])
    assert r.exit_code == 0, r.output
    assert len(_cash_rows(db_path)) == 1


def test_oof_buy_sandbox_non_oof_ticker_still_rejects(tmp_path: Path, monkeypatch):
    """SB1 validation-still-runs arm (the Codex R2 MAJOR-2 fix): under SANDBOX a
    NON-OOF ticker STILL raises the registry ClickException (NOT a silent sandbox
    no-op). Proves the sandbox short-circuit is WRITE-SCOPED -- validation
    precedes it.

    Pre-fix (if the CLI short-circuited to sandbox BEFORE the registry guard):
    this would NOT raise (silent no-op) -> FAILS. Post-fix: it raises.
    """
    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch, overrides=_sandbox_overrides())
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "AAPL", "--cost", "100", "--date", "2026-06-18",
    ])
    assert r.exit_code != 0          # registry rejection, even under sandbox
    assert "AAPL" in r.output
    assert _cash_rows(db_path) == []


def test_oof_buy_invalid_date_rejected(tmp_path: Path, monkeypatch):
    """The ISO-date validation (mirrors journal_cash_cmd) -> ClickException."""
    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch, overrides=_SPCX_OVERRIDES)
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "SPCX", "--cost", "500", "--date", "2026-13-99",
    ])
    assert r.exit_code != 0
    assert _cash_rows(db_path) == []


def test_oof_buy_non_positive_cost_rejected(tmp_path: Path, monkeypatch):
    """--cost <= 0 -> ClickException; no row."""
    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch, overrides=_SPCX_OVERRIDES)
    for bad in ("0", "-5"):
        r = runner.invoke(main, [
            "--config", str(cfg), "journal", "oof-buy",
            "--ticker", "SPCX", "--cost", bad, "--date", "2026-06-18",
        ])
        assert r.exit_code != 0, (bad, r.output)
    assert _cash_rows(db_path) == []


def test_oof_buy_non_finite_cost_rejected(tmp_path: Path, monkeypatch):
    """Codex R1-MAJOR-2 (measurement-core): --cost inf / nan -> ClickException;
    NO row written.

    Pre-fix: `inf` passes `cost <= 0` (inf not <= 0) AND the SQLite `amount >= 0`
    CHECK (inf >= 0 is True) -> a non-finite withdraw lands -> current_equity
    propagates a non-finite ledger -> the coherence eval is SUPPRESSED (the
    opposite of a trustworthy signal). `nan` fails the SQLite CHECK ->
    IntegrityError -> the belt mis-reports it as 'already recorded'.
    Post-fix: an explicit finiteness guard rejects both with a clear message,
    and nothing is written.
    """
    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch, overrides=_SPCX_OVERRIDES)
    for bad in ("inf", "nan", "-inf"):
        r = runner.invoke(main, [
            "--config", str(cfg), "journal", "oof-buy",
            "--ticker", "SPCX", "--cost", bad, "--date", "2026-06-18",
        ])
        assert r.exit_code != 0, (bad, r.output)
        # Not mis-reported as a dedup no-op.
        assert "already recorded" not in r.output.lower(), (bad, r.output)
    assert _cash_rows(db_path) == []   # nothing written for any non-finite cost


def test_journal_cash_rejects_oof_prefixed_ref(tmp_path: Path, monkeypatch):
    """Codex R3-MAJOR-1: the `oof:` ref namespace is RESERVED for `journal
    oof-buy`. `journal cash --ref oof:...` is rejected -> a non-OOF cash row can
    never carry an `oof:` ref -> the step-7 self-reconcile branch is provably
    inert for every row `journal cash` can produce (Lock 1 holds completely).

    Pre-fix: `journal cash --withdraw 123 --ref oof:SPCX:2026-06-18` writes a
    non-OOF row that the matcher then skips as self-sourced (the Lock-1 hole).
    Post-fix: the write is rejected with a clear ClickException; nothing written.
    """
    runner, cfg, db_path = _setup(tmp_path, monkeypatch)
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "cash",
        "--withdraw", "123", "--date", "2026-06-18",
        "--ref", "oof:SPCX:2026-06-18",
    ])
    assert r.exit_code != 0, r.output
    assert "oof:" in r.output            # the message names the reserved prefix
    assert _cash_rows(db_path) == []     # nothing written

    # A non-oof ref still works (the guard is scoped to the reserved prefix).
    r2 = runner.invoke(main, [
        "--config", str(cfg), "journal", "cash",
        "--withdraw", "123", "--date", "2026-06-18", "--ref", "DEP-X",
    ])
    assert r2.exit_code == 0, r2.output
    assert len(_cash_rows(db_path)) == 1


def test_oof_buy_colon_ticker_surfaces_clickexception(tmp_path: Path, monkeypatch):
    """Codex R4-MAJOR-2: a registered colon-bearing ticker (pathological but
    registry-legal) surfaces a clean ClickException, NOT a raw ValueError
    traceback, and writes nothing. _build_oof_ref raises on the colon (the
    delimiter); the CLI wraps it."""
    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch,
        overrides={"reconciliation": {"out_of_framework_tickers": ["NYSE:SPCX"]}},
    )
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "NYSE:SPCX", "--cost", "500", "--date", "2026-06-18",
    ])
    assert r.exit_code != 0
    # A clean ClickException (click prints 'Error: ...'), not a traceback.
    assert "Traceback" not in r.output
    assert "':'" in r.output or "colon" in r.output.lower()
    assert _cash_rows(db_path) == []
