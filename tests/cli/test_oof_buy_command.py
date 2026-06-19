"""CLI: `swing journal oof-buy` (Phase-18 deferred follow-up #1).

Tests (per docs/plans/oof-buy-command-plan.md §4):
  - R1   the registry guard (non-OOF ticker -> ClickException; positive SPCX
         accepted; lower-case accepted with the canonical ref) -- seeded via the
         REAL overrides path (O1: the command reads apply_overrides, NOT bare
         config; a bare-config read would reject EVERY ticker).
  - I1   idempotency (twice, same key -> one row; mixed-case dedups).
  - SB1  sandbox (no domain row written; production writes one; AND a non-OOF
         ticker under sandbox STILL rejects -- the write-scoped gate proof).

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
# I1 — idempotency
# --------------------------------------------------------------------------- #

def test_oof_buy_idempotent_same_key(tmp_path: Path, monkeypatch):
    """I1: run twice with the same key -> exactly one row; the second exits 0
    with a clean 'already recorded' message (NOT an IntegrityError traceback)."""
    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch, overrides=_SPCX_OVERRIDES)
    args = [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "SPCX", "--cost", "500", "--date", "2026-06-18",
    ]
    r1 = runner.invoke(main, args)
    assert r1.exit_code == 0, r1.output
    assert len(_cash_rows(db_path)) == 1
    r2 = runner.invoke(main, args)
    assert r2.exit_code == 0, r2.output           # clean no-op, not a traceback
    assert len(_cash_rows(db_path)) == 1          # still exactly one row
    assert "already recorded" in r2.output.lower()


def test_oof_buy_conflicting_cost_replay_rejected(tmp_path: Path, monkeypatch):
    """codex-auto-review [P2]: a re-run for the SAME ticker/date with a DIFFERENT
    --cost is a CONFLICT (the sentinel ref does not encode cost), NOT a silent
    'already recorded' no-op -- otherwise the ledger keeps the OLD cost while
    reporting success (silent coherence corruption on a measurement-core path).

    Pre-fix: the second run reports 'already recorded' and leaves the original
    $500 row -> the ledger is wrong (the operator believes $700 was recorded).
    Post-fix: the second run ERRORS (conflict); the original row is unchanged;
    the operator resolves deliberately.
    """
    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch, overrides=_SPCX_OVERRIDES)
    r1 = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "SPCX", "--cost", "500", "--date", "2026-06-18",
    ])
    assert r1.exit_code == 0, r1.output
    # Same ticker/date, DIFFERENT cost -> conflict.
    r2 = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "SPCX", "--cost", "700", "--date", "2026-06-18",
    ])
    assert r2.exit_code != 0, r2.output            # a conflict error, not exit 0
    assert "differs" in r2.output.lower()          # the message explains the conflict
    rows = _cash_rows(db_path)
    assert len(rows) == 1
    assert rows[0][3] == 500.0   # the ORIGINAL amount is unchanged (not 700)


def test_oof_buy_idempotent_mixed_case(tmp_path: Path, monkeypatch):
    """I1 mixed-case arm (the Codex R1 MAJOR coverage): `spcx` then `SPCX`, same
    date -> STILL exactly one row (both upper-case to the IDENTICAL canonical
    ref).

    Pre-fix (no boundary upper-casing): the lower run writes oof:spcx:... and the
    upper run oof:SPCX:... -> TWO rows -> FAILS. Post-fix: one row.
    """
    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch, overrides=_SPCX_OVERRIDES)
    r1 = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "spcx", "--cost", "500", "--date", "2026-06-18",
    ])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(main, [
        "--config", str(cfg), "journal", "oof-buy",
        "--ticker", "SPCX", "--cost", "500", "--date", "2026-06-18",
    ])
    assert r2.exit_code == 0, r2.output
    rows = _cash_rows(db_path)
    assert len(rows) == 1
    assert rows[0][4] == "oof:SPCX:2026-06-18"


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
