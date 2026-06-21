"""CLI: `swing journal cash-void` (Phase-18 register D19).

Tests (per docs/plans/cash-void-command-plan.md §4):
  - V-KIND  the reversing-kind negation table (per original kind -> the negating
            reversing kind; current_equity restored to baseline).
  - REJ-V   the reject ladder (non-existent id; void-of-a-void; empty/whitespace
            --reason).
  - I1-V    idempotency = FAIL LOUD, FLAT, NO --force (a bare re-void -> a
            ClickException naming the existing void row + no double-record; the
            IntegrityError belt also fails loud).
  - SB-V    sandbox (no domain row; production writes one; validation still runs
            under sandbox -- the write-scoped-gate proof; the O2 overrides read).
  - NS-V    the `void:` namespace reservation at `journal cash --ref`.

The overrides path is exercised via write_user_overrides with USERPROFILE AND
HOME monkeypatched (the write_user_overrides gotcha) so apply_overrides
materializes the env from disk -- the production read shape (the O2
discriminator), not a stubbed apply_overrides.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from swing.data.db import connect
from swing.data.repos.cash import list_cash
from swing.trades.equity import current_equity
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path: Path, monkeypatch, *, overrides: dict | None = None):
    """Build a minimal config + migrated DB; point USERPROFILE+HOME at home_dir
    so apply_overrides reads the seeded user-config.toml. Returns
    (runner, cfg_path, db_path)."""
    project = tmp_path / "project"; project.mkdir(parents=True)
    home = tmp_path / "home"; home.mkdir(parents=True)
    cfg = _minimal_config(project, home)
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


def _seed_original(runner, cfg, *, kind: str, amount: str, date: str = "2026-06-18"):
    """Record an original cash_movement via the REAL `journal cash` CLI; return
    its id (the production write path -- not a raw insert)."""
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "cash",
        f"--{kind}", amount, "--date", date,
    ])
    assert r.exit_code == 0, r.output
    # The just-written row is the most recent id.
    return r


def _current_equity(db_path: Path, *, starting: float) -> float:
    conn = connect(db_path)
    try:
        return current_equity(
            starting_equity=starting, exits=[], cash_movements=list_cash(conn))
    finally:
        conn.close()


_SANDBOX_OVERRIDES = {"integrations": {"schwab": {"environment": "sandbox"}}}


# --------------------------------------------------------------------------- #
# V-KIND — the reversing-kind negation table (per-kind)
# --------------------------------------------------------------------------- #

def _negation(kind: str) -> str:
    # withdraw/fee SUBTRACT -> reverse with a deposit; deposit/interest/dividend
    # ADD -> reverse with a withdraw (plan §1 table).
    return "deposit" if kind in ("withdraw", "fee") else "withdraw"


def test_cash_void_reversing_kind_table(tmp_path: Path, monkeypatch):
    """V-KIND: each original kind -> the correct negating reversing kind, same
    amount, ref=void:<id>, note startswith 'VOID #<id>:', AND current_equity is
    restored to the pre-error baseline (the pair nets to 0).

    Distinguishes: a wrong negation (e.g. reversing a fee with a withdraw)
    DOUBLES the offset -> current_equity off by 2X not 0 -> the restoration
    assertion FAILS.
    """
    starting = 1450.0
    amount = 372.48
    for kind in ("withdraw", "fee", "deposit", "interest", "dividend"):
        runner, cfg, db_path = _setup(tmp_path / kind, monkeypatch)
        baseline = _current_equity(db_path, starting=starting)
        assert baseline == starting   # empty ledger
        _seed_original(runner, cfg, kind=kind, amount=str(amount))
        rows = _cash_rows(db_path)
        assert len(rows) == 1
        orig_id = rows[0][0]
        r = runner.invoke(main, [
            "--config", str(cfg), "journal", "cash-void", str(orig_id),
            "--reason", "test", "--date", "2026-06-18",
        ])
        assert r.exit_code == 0, r.output
        rows = _cash_rows(db_path)
        assert len(rows) == 2
        rev = rows[1]   # the reversing row is the newer id
        _id, _date, rev_kind, rev_amount, rev_ref, rev_note = rev
        assert rev_kind == _negation(kind), (kind, rev_kind)
        assert rev_amount == amount
        assert rev_ref == f"void:{orig_id}"
        assert rev_note.startswith(f"VOID #{orig_id}:")
        # The pair nets to 0 -> current_equity restored to baseline.
        assert _current_equity(db_path, starting=starting) == baseline


def test_cash_void_defaults_date_to_original(tmp_path: Path, monkeypatch):
    """The void row's date defaults to the ORIGINAL row's date when --date is
    omitted (plan §3) -- the correction belongs with the error's period."""
    runner, cfg, db_path = _setup(tmp_path, monkeypatch)
    _seed_original(runner, cfg, kind="withdraw", amount="100", date="2026-06-10")
    orig_id = _cash_rows(db_path)[0][0]
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "cash-void", str(orig_id),
        "--reason", "no date supplied",
    ])
    assert r.exit_code == 0, r.output
    rev = _cash_rows(db_path)[1]
    assert rev[1] == "2026-06-10"   # the void row carries the ORIGINAL's date


# --------------------------------------------------------------------------- #
# REJ-V — the reject ladder
# --------------------------------------------------------------------------- #

def test_cash_void_non_existent_id_rejected(tmp_path: Path, monkeypatch):
    """REJ-V: a non-existent id -> non-zero exit, the message names the id, NO
    row written."""
    runner, cfg, db_path = _setup(tmp_path, monkeypatch)
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "cash-void", "99999", "--reason", "x",
    ])
    assert r.exit_code != 0
    assert "99999" in r.output
    assert _cash_rows(db_path) == []


def test_cash_void_of_a_void_rejected(tmp_path: Path, monkeypatch):
    """REJ-V: voiding a row that is ITSELF a void entry (ref starts 'void:') ->
    non-zero exit, NO new row (no void-of-a-void in V1; the chain stays flat).

    Distinguishes: WITHOUT the void-of-a-void guard the command would write
    void:<vid> (a chained void) -> the 'no new row' assertion FAILS.
    """
    runner, cfg, db_path = _setup(tmp_path, monkeypatch)
    _seed_original(runner, cfg, kind="withdraw", amount="100")
    orig_id = _cash_rows(db_path)[0][0]
    r1 = runner.invoke(main, [
        "--config", str(cfg), "journal", "cash-void", str(orig_id),
        "--reason", "first void",
    ])
    assert r1.exit_code == 0, r1.output
    void_id = _cash_rows(db_path)[1][0]   # the void row's id
    assert len(_cash_rows(db_path)) == 2
    # Attempt to void the void row itself.
    r2 = runner.invoke(main, [
        "--config", str(cfg), "journal", "cash-void", str(void_id),
        "--reason", "void of a void",
    ])
    assert r2.exit_code != 0, r2.output
    assert "void" in r2.output.lower()
    assert len(_cash_rows(db_path)) == 2   # NO chained void row written


def test_cash_void_empty_reason_rejected(tmp_path: Path, monkeypatch):
    """REJ-V: an empty / whitespace-only --reason -> non-zero exit, NO row.

    Distinguishes: WITHOUT the empty-reason guard an empty reason would write
    note='VOID #<id>: ' (a useless audit trail) -> the no-row assertion FAILS.
    (A MISSING --reason is a click usage error by construction -- --reason is
    required; the empty/whitespace check is the added guard.)
    """
    runner, cfg, db_path = _setup(tmp_path, monkeypatch)
    _seed_original(runner, cfg, kind="withdraw", amount="100")
    orig_id = _cash_rows(db_path)[0][0]
    before = _cash_rows(db_path)
    for bad in ("", "   "):
        r = runner.invoke(main, [
            "--config", str(cfg), "journal", "cash-void", str(orig_id),
            "--reason", bad,
        ])
        assert r.exit_code != 0, (repr(bad), r.output)
    assert _cash_rows(db_path) == before   # only the original; no void row


# --------------------------------------------------------------------------- #
# I1-V — idempotency = FAIL LOUD, FLAT, NO --force (RD course-correction)
# --------------------------------------------------------------------------- #

def test_cash_void_bare_rerun_fails_loud_no_double(tmp_path: Path, monkeypatch):
    """I1-V (AMENDED): voiding the same id twice -> the second run is REJECTED
    with an actionable message naming the existing void row, AND there is STILL
    exactly ONE void row (no double-record). NO silent no-op, NO --force.

    PRE-correction (a silent-no-op idempotency, the OOF arc's original sin):
    the second run would exit 0 with one row unchanged -> the non-zero-exit
    assertion FAILS against a silent-no-op impl; the fail-loud raises -> PASSES.
    """
    runner, cfg, db_path = _setup(tmp_path, monkeypatch)
    _seed_original(runner, cfg, kind="withdraw", amount="372.48")
    orig_id = _cash_rows(db_path)[0][0]
    args = [
        "--config", str(cfg), "journal", "cash-void", str(orig_id),
        "--reason", "double-debit", "--date", "2026-06-18",
    ]
    r1 = runner.invoke(main, args)
    assert r1.exit_code == 0, r1.output
    assert len(_cash_rows(db_path)) == 2   # original + ONE void row
    void_id = _cash_rows(db_path)[1][0]
    # The bare re-run MUST fail loud -- not a silent no-op.
    r2 = runner.invoke(main, args)
    assert r2.exit_code != 0, r2.output                # rejected, not exit 0
    assert "already voided" in r2.output.lower()       # actionable collision msg
    assert f"#{void_id}" in r2.output                  # names the existing void row
    assert f"void:{orig_id}" in r2.output              # names the colliding ref
    assert "--force" not in r2.output                  # NO escape hatch offered
    assert len(_cash_rows(db_path)) == 2               # STILL one void row


def test_cash_void_no_force_option(tmp_path: Path, monkeypatch):
    """I1-V: the cash-void command does NOT offer a --force flag (the fail-loud
    is FLAT + unconditional -- there is no legitimate double-void).

    Asserts against the rendered Options block only (the docstring prose may
    reference '--force' historically; what matters is no --force OPTION exists).
    """
    runner, cfg, _db = _setup(tmp_path, monkeypatch)
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "cash-void", "--help",
    ])
    assert r.exit_code == 0, r.output
    options_block = r.output.split("Options:", 1)[1]
    assert "--force" not in options_block
    # The expected options ARE present.
    assert "--reason" in options_block
    assert "--date" in options_block


def test_cash_void_integrityerror_belt_fails_loud(tmp_path: Path, monkeypatch):
    """I1-V belt (the TOCTOU-race fallback): with the SELECT-first find_by_ref
    forced to MISS once (the race window), the command reaches insert_cash ->
    IntegrityError -> the belt re-fetches + raises the SAME fail-loud collision
    error (non-zero exit, names the row, one void row only).

    PRE-correction: the belt would mis-report a silent no-op. POST-correction:
    the belt fails loud on the collision.
    """
    runner, cfg, db_path = _setup(tmp_path, monkeypatch)
    _seed_original(runner, cfg, kind="withdraw", amount="500")
    orig_id = _cash_rows(db_path)[0][0]
    args = [
        "--config", str(cfg), "journal", "cash-void", str(orig_id),
        "--reason", "x", "--date", "2026-06-18",
    ]
    # Pre-seed the race winner: the FIRST void lands normally.
    r0 = runner.invoke(main, args)
    assert r0.exit_code == 0, r0.output
    assert len(_cash_rows(db_path)) == 2

    import swing.data.repos.cash as _cash_repo
    _real_find = _cash_repo.find_by_ref
    calls = {"n": 0}

    def _racing_find(conn, ref):
        calls["n"] += 1
        if calls["n"] == 1:
            return None               # SELECT-first miss (the race window)
        return _real_find(conn, ref)  # the belt re-fetch sees the real row

    monkeypatch.setattr(_cash_repo, "find_by_ref", _racing_find)
    r = runner.invoke(main, args)
    assert r.exit_code != 0, r.output          # the belt raised, not exit 0
    assert "already voided" in r.output.lower()
    assert len(_cash_rows(db_path)) == 2       # STILL one void row (no double)


# --------------------------------------------------------------------------- #
# SB-V — the sandbox test
# --------------------------------------------------------------------------- #

def test_cash_void_sandbox_writes_no_domain_row(tmp_path: Path, monkeypatch):
    """SB-V: under environment != 'production', no void row written; the command
    echoes a sandbox advisory + exits 0.

    O2 discriminator: the sandbox env is seeded via OVERRIDES; if the command
    read bare ctx.obj['config'] (the O2 bug), the override would be IGNORED (env
    stays 'production') -> the sandbox run would WRITE a row -> the 'no row'
    assertion FAILS. So it distinguishes the apply_overrides env read.
    """
    # The original must exist to reach the sandbox gate (validation precedes it),
    # so seed it under PRODUCTION first (a separate setup), then run the void
    # under SANDBOX against the SAME DB. We instead seed via a raw insert so the
    # original is present regardless of env.
    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch, overrides=_SANDBOX_OVERRIDES)
    # Seed the original via a raw insert (the `journal cash` write is env-
    # agnostic -- cash is a manual ledger entry -- so this is a faithful seed).
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO cash_movements (date, kind, amount, ref, note) "
                "VALUES (?,?,?,?,?)",
                ("2026-06-18", "withdraw", 500.0, None, "seed"),
            )
            orig_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()
    before = _cash_rows(db_path)
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "cash-void", str(orig_id),
        "--reason", "x", "--date", "2026-06-18",
    ])
    assert r.exit_code == 0, r.output
    assert "sandbox" in r.output.lower()
    assert _cash_rows(db_path) == before    # audit-only; no void row


def test_cash_void_production_writes_one_row(tmp_path: Path, monkeypatch):
    """SB-V parallel: the SAME flow under production writes exactly ONE void row
    -- the gate is proven env-conditional, not 'never writes'. (Base config
    defaults environment='production' when no override is present.)"""
    runner, cfg, db_path = _setup(tmp_path, monkeypatch)
    _seed_original(runner, cfg, kind="withdraw", amount="500")
    orig_id = _cash_rows(db_path)[0][0]
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "cash-void", str(orig_id),
        "--reason", "x", "--date", "2026-06-18",
    ])
    assert r.exit_code == 0, r.output
    assert len(_cash_rows(db_path)) == 2     # original + ONE void row


def test_cash_void_sandbox_non_existent_id_still_rejects(tmp_path: Path, monkeypatch):
    """SB-V validation-still-runs arm (the write-scoped-gate proof): under
    SANDBOX a NON-EXISTENT id STILL raises the not-found ClickException (NOT a
    silent sandbox no-op). Validation precedes the write-scoped sandbox gate.

    Pre-fix (if the CLI short-circuited to sandbox BEFORE the find_by_id fetch):
    this would NOT raise -> FAILS. Post-fix: it raises.
    """
    runner, cfg, db_path = _setup(
        tmp_path, monkeypatch, overrides=_SANDBOX_OVERRIDES)
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "cash-void", "99999", "--reason", "x",
    ])
    assert r.exit_code != 0          # not-found rejection, even under sandbox
    assert "99999" in r.output
    assert _cash_rows(db_path) == []


def test_cash_void_invalid_date_rejected(tmp_path: Path, monkeypatch):
    """The ISO-date validation (mirrors journal_cash_cmd) -> ClickException; no
    void row."""
    runner, cfg, db_path = _setup(tmp_path, monkeypatch)
    _seed_original(runner, cfg, kind="withdraw", amount="100")
    orig_id = _cash_rows(db_path)[0][0]
    before = _cash_rows(db_path)
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "cash-void", str(orig_id),
        "--reason", "x", "--date", "2026-13-99",
    ])
    assert r.exit_code != 0
    assert _cash_rows(db_path) == before   # no void row


def test_cash_void_non_finite_original_amount_rejected(tmp_path: Path, monkeypatch):
    """Codex R1-MAJOR-2 (measurement-core): voiding an original whose amount is
    non-finite (inf) is REJECTED with a clear ClickException; NO void row.

    Pre-fix: `journal cash --withdraw inf` passes (`inf <= 0` is False) AND the
    SQLite `amount >= 0` CHECK (inf >= 0 is True) -> a non-finite withdraw lands.
    Voiding it copies `original.amount` (inf) into a reversing deposit -> the
    pair sums to `-inf + inf = NaN` in net_cash_movements -> current_equity is
    NOT restored and the coherence eval is SUPPRESSED. Post-fix: the void
    command rejects a non-finite original amount before deriving the reversing
    row; nothing is written. (The non-finite ORIGINAL is itself a `journal cash`
    gap flagged separately; the void command's guard closes the void-arc
    vector.)
    """
    runner, cfg, db_path = _setup(tmp_path, monkeypatch)
    # Seed a non-finite original via a raw insert (journal cash lets inf through
    # today -- the separate flagged gap; we exercise the void's guard directly).
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO cash_movements (date, kind, amount, ref, note) "
                "VALUES (?,?,?,?,?)",
                ("2026-06-18", "withdraw", float("inf"), None, "bad inf"),
            )
            orig_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()
    before = _cash_rows(db_path)
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "cash-void", str(orig_id),
        "--reason", "x", "--date", "2026-06-18",
    ])
    assert r.exit_code != 0, r.output
    assert "finite" in r.output.lower()
    assert _cash_rows(db_path) == before   # no void row written


# --------------------------------------------------------------------------- #
# NS-V — the `void:` namespace reservation
# --------------------------------------------------------------------------- #

def test_journal_cash_rejects_void_prefixed_ref(tmp_path: Path, monkeypatch):
    """NS-V: the `void:` ref namespace is RESERVED for `journal cash-void`.
    `journal cash --ref void:...` is rejected -> a non-void cash row can never
    carry a `void:` ref -> the step-7 self-reconcile branch is provably inert for
    every row `journal cash` can produce (Lock 1 holds).

    Pre-fix: `journal cash --withdraw 123 --ref void:5` writes a non-void row
    that the matcher then skips as self-sourced (the Lock-1 hole). Post-fix: the
    write is rejected; nothing written. A non-void ref still works (the guard is
    scoped to the prefix).
    """
    runner, cfg, db_path = _setup(tmp_path, monkeypatch)
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "cash",
        "--withdraw", "123", "--date", "2026-06-18", "--ref", "void:5",
    ])
    assert r.exit_code != 0, r.output
    assert "void:" in r.output           # the message names the reserved prefix
    assert "cash-void" in r.output       # points to the right command
    assert _cash_rows(db_path) == []     # nothing written

    # A non-void ref still works (the guard is scoped to the reserved prefix).
    r2 = runner.invoke(main, [
        "--config", str(cfg), "journal", "cash",
        "--withdraw", "123", "--date", "2026-06-18", "--ref", "DEP-X",
    ])
    assert r2.exit_code == 0, r2.output
    assert len(_cash_rows(db_path)) == 1
