"""22-A4 Task 1 -- the per-attempt identity token at the REPO and SERVICE grain.

(r1)-(r3), (r6), (r7), (e), (e2) and (w2).  (w) and the settlement rows belong
to the tasks that ship the probe and clause 2's return.

THE PLANTED TOKENS ARE CANONICAL LOWERCASE v4 STRINGS.  ``validate_attempt_id``
is the single admission authority and it parses; a bare ``"x" * 36`` no longer
reaches the database, which is the point of the predicate.
"""
from __future__ import annotations

import logging
import sqlite3
import uuid
from pathlib import Path

import pytest

from swing.data.db import ensure_schema, open_connection, run_migrations
from swing.data.models import Trade
from swing.data.repos.trades import (
    ATTEMPT_ID_LENGTH,
    find_trade_id_by_attempt_id,
    insert_trade_with_event,
    validate_attempt_id,
)
from swing.trades.entry import (
    DuplicateOpenPositionError,
    EntryRequest,
    record_entry,
)
from swing.trades.origin import EntryPath

TOK_A = "00000000-0000-4000-8000-000000000001"
TOK_B = "00000000-0000-4000-8000-000000000002"
# A token WITH HEX LETTERS, so uppercasing it is not a no-op.  The
# first draft of these rosters uppercased TOK_A, which is all digits
# and hyphens and therefore IDENTICAL to itself -- a case that
# asserted nothing, caught by execution rather than by reading.
TOK_MIXED = "0a0b0c0d-0e0f-4a1b-8c2d-0e3f4a5b6c7d"
SOFT, HARD = 8, 12
EVENT_TS = "2026-09-07T09:30:00"


class _BrokenSink(logging.Handler):
    def emit(self, record):
        raise RuntimeError("22-A4 PROBE: logging sink failed")


@pytest.fixture
def broken_sink():
    sink = _BrokenSink(level=logging.WARNING)
    root = logging.getLogger()
    root.addHandler(sink)
    try:
        yield sink
    finally:
        root.removeHandler(sink)


def _v37(tmp_path: Path, name: str = "v37.db") -> sqlite3.Connection:
    c = open_connection(tmp_path / name)
    run_migrations(c, target_version=37, backup_dir=tmp_path / "bak37")
    return c


def _trade(ticker: str = "AAA") -> Trade:
    return Trade(
        id=None, ticker=ticker, entry_date="2026-09-07", entry_price=10.0,
        initial_shares=1, initial_stop=9.0, current_stop=9.0, state="entered",
        watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
        trade_origin="manual_off_pipeline",
        pre_trade_locked_at="2026-09-07T16:00:00",
    )


def _req(**over) -> EntryRequest:
    fields = dict(
        ticker="AAA", entry_date="2026-09-07", entry_price=18.50, shares=2,
        initial_stop=14.00, watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None, rationale="vcp_breakout",
        event_ts=EVENT_TS, entry_path=EntryPath.MANUAL_WEB_FORM,
        thesis="the mandate fired", why_now="through the pivot",
        invalidation_condition="break of the stop",
        expected_scenario="20% in 4 weeks",
        premortem_technical="pivot fails",
        premortem_market_sector="sector breaks",
        premortem_execution="size too small",
        event_risk_present=0, event_handling="not_applicable",
        gap_risk_present=0, gap_risk_handling="not_applicable",
        emotional_state_pre_trade='["calm"]', market_regime="Bullish",
        catalyst="technical_only", manual_entry_confidence="normal",
        fill_origin="operator_typed", schwab_source_value_json=None,
    )
    fields.update(over)
    return EntryRequest(**fields)


# ===========================================================================
# (r1) The repo writes the token
# ===========================================================================
def test_r1_the_repo_writes_the_token(tmp_path: Path) -> None:
    conn = ensure_schema(tmp_path / "r1.db")
    try:
        with conn:
            tid = insert_trade_with_event(
                conn, _trade(), event_ts=EVENT_TS, attempt_id=TOK_A)
        assert conn.execute(
            "SELECT attempt_id FROM trades WHERE id = ?", (tid,)
        ).fetchone()[0] == TOK_A
    finally:
        conn.close()


# ===========================================================================
# (r2) A pre-v38 schema DROPS the token and still inserts
# ===========================================================================
def test_r2_a_pre_v38_schema_drops_the_token_and_still_inserts(
        tmp_path: Path, caplog) -> None:
    """The assertion is what a v37 database can ACTUALLY answer: SQL naming
    ``attempt_id`` there raises ``no such column``, so the column's ABSENCE is
    read from ``PRAGMA table_info``.  The NULL reading is a SECOND step, after
    migrating that same database to v38."""
    conn = _v37(tmp_path)
    try:
        with caplog.at_level(logging.WARNING):
            with conn:
                tid = insert_trade_with_event(
                    conn, _trade(), event_ts=EVENT_TS, attempt_id=TOK_A)
        assert tid > 0
        assert conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 1
        assert "attempt_id" not in {
            r[1] for r in conn.execute("PRAGMA table_info(trades)")}
        assert "attempt_id" in caplog.text

        run_migrations(conn, target_version=38, backup_dir=tmp_path / "bak38")
        assert conn.execute(
            "SELECT attempt_id FROM trades WHERE id = ?", (tid,)
        ).fetchone()[0] is None
    finally:
        conn.close()


def test_r2_the_pre_v38_warning_is_CONTAINED_against_a_raising_sink(
        tmp_path: Path, broken_sink) -> None:
    """A plain ``log.warning`` would satisfy the row above and ABORT the
    money-bearing INSERT the moment a caller-installed handler raises."""
    conn = _v37(tmp_path, "r2b.db")
    try:
        with conn:
            tid = insert_trade_with_event(
                conn, _trade("BBB"), event_ts=EVENT_TS, attempt_id=TOK_A)
        assert conn.execute(
            "SELECT COUNT(*) FROM trades WHERE id = ?", (tid,)
        ).fetchone()[0] == 1
    finally:
        conn.close()


# ===========================================================================
# (r3) A malformed token is refused BEFORE any write
# ===========================================================================
@pytest.mark.parametrize("bad", [
    "",
    "short",
    "0" * 37,
    b"y" * 36,
    "0" * 35 + "\x00",
    "\ud800" + "0" * 35,
    TOK_MIXED.upper(),
])
def test_r3_a_malformed_token_is_refused_before_any_write(
        tmp_path: Path, bad) -> None:
    """SEVEN values, and the last three each defeat a DIFFERENT layer:
    the NUL clears a Python length test and is refused by the CHECK (Python
    len 36, SQLite length() 35); the lone surrogate never reaches the CHECK at
    all (``sqlite3`` raises at PARAMETER BINDING, one layer below it); and the
    UPPERCASE canonical uuid4 satisfies the CHECK and BINDS cleanly, defeating
    ``ux_trades_attempt_id`` silently because ``'A...'`` and ``'a...'`` are
    DIFFERENT text keys.

    The row-count half is what distinguishes a pre-write guard from a
    post-write one.
    """
    conn = ensure_schema(tmp_path / "r3.db")
    try:
        with pytest.raises(ValueError):
            with conn:
                insert_trade_with_event(
                    conn, _trade(), event_ts=EVENT_TS, attempt_id=bad)
        assert conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0
    finally:
        conn.close()


def test_r3_the_validator_is_the_single_admission_authority() -> None:
    """The SERVICE side and the WRITE side call the SAME function.  Two
    hand-written predicates over one column are a mirror pair, and the drift
    that matters is the one where the service ADMITS what the write REFUSES --
    which turns a contained degradation into a failed entry."""
    from swing.trades import entry as entry_mod

    assert entry_mod.validate_attempt_id is validate_attempt_id
    assert ATTEMPT_ID_LENGTH == 36
    assert validate_attempt_id(TOK_A) is None
    for bad in ("", "short", "0" * 37, b"y" * 36, "0" * 35 + "\x00",
                "\ud800" + "0" * 35, TOK_MIXED.upper(), None,
                "00000000-0000-1000-8000-000000000001"):
        with pytest.raises(ValueError):
            validate_attempt_id(bad)


# ===========================================================================
# (r7) The probe is SCHEMA-AWARE
# ===========================================================================
def test_r7_the_probe_returns_None_without_raising_on_a_v37_database(
        tmp_path: Path) -> None:
    """An implementation that unconditionally executes ``WHERE attempt_id = ?``
    passes the whole suite while the advertised ABSENT branch does not exist:
    the settle contains the resulting ``OperationalError`` and re-raises the
    original, so every high-level assertion still holds.  The suite must be
    able to tell ABSENCE from INTERNAL PROBE FAILURE."""
    conn = _v37(tmp_path)
    try:
        assert find_trade_id_by_attempt_id(conn, TOK_A) is None
    finally:
        conn.close()


def test_r7_the_probe_finds_the_row_on_v38(tmp_path: Path) -> None:
    conn = ensure_schema(tmp_path / "r7b.db")
    try:
        with conn:
            tid = insert_trade_with_event(
                conn, _trade(), event_ts=EVENT_TS, attempt_id=TOK_A)
        assert find_trade_id_by_attempt_id(conn, TOK_A) == tid
        assert find_trade_id_by_attempt_id(conn, TOK_B) is None
    finally:
        conn.close()


# ===========================================================================
# (r6) The IntegrityError mapping no longer mis-labels
# ===========================================================================
def test_r6_a_duplicate_attempt_id_is_NOT_relabelled_as_a_position_race(
        tmp_path: Path, monkeypatch) -> None:
    """The assertion is on the TYPE and the MESSAGE of what escapes, NOT on
    the absence of ``DuplicateOpenPositionError`` -- a row written as "no
    DuplicateOpenPositionError was raised" would pass an implementation that
    raised nothing at all.

    PRE-FIX (the loose ``"UNIQUE" in msg and "trades" in msg`` match plus the
    new index): this raises ``DuplicateOpenPositionError("Already an open
    position in BBB (race-detected)")`` over a ticker with NO open position.
    """
    from swing.trades import entry as entry_mod

    conn = ensure_schema(tmp_path / "r6.db")
    try:
        monkeypatch.setattr(entry_mod, "_mint_attempt_token", lambda: TOK_A)
        record_entry(conn, _req(ticker="AAA"), soft_warn=SOFT, hard_cap=HARD,
                     force=False, cfg=None)
        with pytest.raises(sqlite3.IntegrityError) as caught:
            record_entry(conn, _req(ticker="BBB"), soft_warn=SOFT,
                         hard_cap=HARD, force=False, cfg=None)
        assert "UNIQUE constraint failed: trades.attempt_id" in str(caught.value)
    finally:
        conn.close()


def test_r6_a_genuine_same_ticker_race_still_maps_to_the_typed_error(
        tmp_path: Path, monkeypatch) -> None:
    """The narrowing must not retire the mapping it narrows.  The app-layer
    gate is neutralised so the INSERT actually reaches
    ``ux_trades_one_open_per_ticker`` -- the race the mapping exists for."""
    from swing.trades import entry as entry_mod

    conn = ensure_schema(tmp_path / "r6b.db")
    try:
        record_entry(conn, _req(ticker="AAA"), soft_warn=SOFT, hard_cap=HARD,
                     force=False, cfg=None)
        monkeypatch.setattr(entry_mod, "list_open_trades", lambda _c: [])
        with pytest.raises(DuplicateOpenPositionError, match="AAA"):
            record_entry(conn, _req(ticker="AAA"), soft_warn=SOFT,
                         hard_cap=HARD, force=False, cfg=None)
    finally:
        conn.close()


# ===========================================================================
# (w2) The mint's own contract
# ===========================================================================
def test_w2_the_mint_draws_from_uuid4_once_per_mint(monkeypatch) -> None:
    """Every other identity row patches ``_mint_attempt_token`` ITSELF, so a
    production mint returning a CONSTANT valid 36-character string passes all
    of them.  This patches one level BELOW the mint."""
    from swing.trades import entry as entry_mod

    sentinels = [uuid.UUID(TOK_A), uuid.UUID(TOK_B)]
    calls = []

    def _fake():
        calls.append(1)
        return sentinels[len(calls) - 1]

    monkeypatch.setattr(uuid, "uuid4", _fake)
    first = entry_mod._mint_attempt_token()
    assert len(calls) == 1
    assert first == str(sentinels[0])
    second = entry_mod._mint_attempt_token()
    assert len(calls) == 2
    assert second == str(sentinels[1])
    assert first != second


def test_w2_two_attempts_the_first_rolled_back_yield_DISTINCT_tokens(
        tmp_path: Path, monkeypatch) -> None:
    """A caching or constant mint returns the first token on the second
    attempt -- which no ``_mint_attempt_token``-level patch can detect."""
    from swing.data.repos import fills as fills_mod
    from swing.trades import entry as entry_mod

    seen: list[str] = []
    real_insert = entry_mod.insert_trade_with_event

    def _spy(conn, trade, **kw):
        seen.append(kw.get("attempt_id"))
        return real_insert(conn, trade, **kw)

    monkeypatch.setattr(entry_mod, "insert_trade_with_event", _spy)

    conn = ensure_schema(tmp_path / "w2b.db")
    try:
        def _boom(*_a, **_k):
            raise RuntimeError("22-A4 PROBE: the body raised after the INSERT")

        monkeypatch.setattr(entry_mod, "insert_fill_with_event", _boom)
        with pytest.raises(RuntimeError, match="the body raised"):
            record_entry(conn, _req(), soft_warn=SOFT, hard_cap=HARD,
                         force=False, cfg=None)
        assert conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0

        monkeypatch.setattr(
            entry_mod, "insert_fill_with_event",
            fills_mod.insert_fill_with_event)
        record_entry(conn, _req(), soft_warn=SOFT, hard_cap=HARD, force=False,
                     cfg=None)
        assert len(seen) == 2
        assert seen[0] is not None and seen[1] is not None
        assert seen[0] != seen[1], (
            "a rolled-back attempt's token was REISSUED to the retry")
    finally:
        conn.close()


# ===========================================================================
# (e) Co-durability, OBSERVED AT THE TRANSACTION BOUNDARY
# ===========================================================================
class _BoundaryProxy:
    """A connection proxy whose context exit READS FIRST and only then commits.

    The observation has to happen AT THE BOUNDARY: a "committed row carries the
    token / rolled-back leaves none" pair is satisfied by a LATE STAMP -- commit
    the trade with no token, then UPDATE it in a second transaction.
    """

    def __init__(self, conn: sqlite3.Connection, db_path: Path):
        self._conn = conn
        self._db_path = db_path
        self.at_boundary_own = "<unread>"
        self.at_boundary_fresh = "<unread>"
        self.token = None

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __enter__(self):
        return self._conn.__enter__()

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            row = self._conn.execute(
                "SELECT attempt_id FROM trades ORDER BY id DESC LIMIT 1"
            ).fetchone()
            self.at_boundary_own = row[0] if row else None
            fresh = sqlite3.connect(self._db_path)
            try:
                self.at_boundary_fresh = fresh.execute(
                    "SELECT COUNT(*) FROM trades WHERE attempt_id IS NOT NULL"
                ).fetchone()[0]
            finally:
                fresh.close()
        return self._conn.__exit__(exc_type, exc, tb)


def test_e_the_token_is_co_durable_with_the_row(
        tmp_path: Path, monkeypatch) -> None:
    from swing.trades import entry as entry_mod

    db_path = tmp_path / "e.db"
    conn = ensure_schema(db_path)
    try:
        monkeypatch.setattr(entry_mod, "_mint_attempt_token", lambda: TOK_A)
        proxy = _BoundaryProxy(conn, db_path)
        result = record_entry(proxy, _req(), soft_warn=SOFT, hard_cap=HARD,
                              force=False, cfg=None)
        # AT THE BOUNDARY: the writer already holds the token (it was written
        # by the INSERT, not afterwards) while nothing is durable yet.  A LATE
        # STAMP reads None here, which is precisely where it must fail.
        assert proxy.at_boundary_own == TOK_A
        assert proxy.at_boundary_fresh == 0
        # AFTER: the token's presence coincides with the whole transaction's.
        row = conn.execute(
            "SELECT attempt_id, risk_policy_id_at_lock FROM trades WHERE id = ?",
            (result.trade_id,)).fetchone()
        assert row[0] == TOK_A
        assert conn.execute(
            "SELECT COUNT(*) FROM trade_events WHERE trade_id = ? "
            "AND event_type = 'entry'", (result.trade_id,)).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM fills WHERE trade_id = ?",
            (result.trade_id,)).fetchone()[0] == 1
    finally:
        conn.close()


def test_e_a_rolled_back_attempt_leaves_no_token_and_no_row(
        tmp_path: Path, monkeypatch) -> None:
    from swing.trades import entry as entry_mod

    conn = ensure_schema(tmp_path / "e2roll.db")
    try:
        monkeypatch.setattr(entry_mod, "_mint_attempt_token", lambda: TOK_A)

        def _boom(*_a, **_k):
            raise RuntimeError("22-A4 PROBE: the body raised after the INSERT")

        monkeypatch.setattr(entry_mod, "insert_fill_with_event", _boom)
        with pytest.raises(RuntimeError, match="the body raised"):
            record_entry(conn, _req(), soft_warn=SOFT, hard_cap=HARD,
                         force=False, cfg=None)
        assert conn.execute(
            "SELECT COUNT(*) FROM trades WHERE attempt_id IS NOT NULL"
        ).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0
    finally:
        conn.close()


# ===========================================================================
# (e2) The identity apparatus cannot FAIL an entry
# ===========================================================================
def _raise():
    raise RuntimeError("22-A4 PROBE: the mint raised")


# THE ROSTER IS THE MANIFEST; the count in any heading is derived from it.
# ELEVEN contained failures, plus ONE interrupt-propagation control.
_CONTAINED = [
    ("mint_raises", _raise),
    ("empty", lambda: ""),
    ("short", lambda: "short"),
    ("too_long", lambda: "0" * 37),
    ("bytes_other_length", lambda: b"abc"),
    ("none", lambda: None),
    ("blob_36", lambda: b"y" * 36),
    ("nul_at_35", lambda: "0" * 35 + "\x00"),
    ("lone_surrogate", lambda: "\ud800" + "0" * 35),
    ("uppercase_canonical", lambda: TOK_MIXED.upper()),
]


@pytest.mark.parametrize("name,mint", _CONTAINED, ids=[n for n, _ in _CONTAINED])
def test_e2_a_failing_or_malformed_mint_cannot_fail_an_entry(
        tmp_path: Path, monkeypatch, caplog, name, mint) -> None:
    """The malformed-RETURN variants are the ones that matter: without result
    validation the value reaches the repo, trips the pre-write ``ValueError``
    (r3) requires, and FAILS AN ENTRY THAT WOULD HAVE SUCCEEDED -- the exact
    outcome the containment exists to prevent, arriving through the
    containment's own blind spot."""
    from swing.trades import entry as entry_mod

    conn = ensure_schema(tmp_path / f"e2_{name}.db")
    try:
        monkeypatch.setattr(entry_mod, "_mint_attempt_token", mint)
        with caplog.at_level(logging.WARNING):
            result = record_entry(conn, _req(), soft_warn=SOFT, hard_cap=HARD,
                                  force=False, cfg=None)
        row = conn.execute(
            "SELECT attempt_id FROM trades WHERE id = ?",
            (result.trade_id,)).fetchone()
        assert row[0] is None
        assert caplog.records, "the degradation was not recorded"
    finally:
        conn.close()


def test_e2_variant_11_a_raising_path_resolver_leaves_the_token_intact(
        tmp_path: Path, monkeypatch, caplog) -> None:
    """The eleventh contained failure: ``_resolve_main_db_path`` RAISES.  The
    token is still written -- it costs nothing and leaves the row identifiable
    for forensics; only the probe is unavailable."""
    from swing.trades import entry as entry_mod

    conn = ensure_schema(tmp_path / "e2_path.db")
    try:
        monkeypatch.setattr(entry_mod, "_mint_attempt_token", lambda: TOK_A)

        def _boom(_c):
            raise RuntimeError("22-A4 PROBE: PRAGMA database_list failed")

        monkeypatch.setattr(entry_mod, "_resolve_main_db_path", _boom)
        with caplog.at_level(logging.WARNING):
            result = record_entry(conn, _req(), soft_warn=SOFT, hard_cap=HARD,
                                  force=False, cfg=None)
        assert conn.execute(
            "SELECT attempt_id FROM trades WHERE id = ?",
            (result.trade_id,)).fetchone()[0] == TOK_A
        assert caplog.records
    finally:
        conn.close()


def test_e2_variant_12_a_KeyboardInterrupt_from_the_mint_PROPAGATES(
        tmp_path: Path, monkeypatch) -> None:
    """The CONTROL of the opposite polarity.  ``Exception``, not
    ``BaseException``: this code runs PRE-COMMIT, where nothing is durable and
    failing is the honest answer."""
    from swing.trades import entry as entry_mod

    conn = ensure_schema(tmp_path / "e2_kbi.db")
    try:
        def _interrupt():
            raise KeyboardInterrupt("22-A4 PROBE")

        monkeypatch.setattr(entry_mod, "_mint_attempt_token", _interrupt)
        with pytest.raises(KeyboardInterrupt):
            record_entry(conn, _req(), soft_warn=SOFT, hard_cap=HARD,
                         force=False, cfg=None)
        assert conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0
    finally:
        conn.close()


@pytest.mark.parametrize("arm", ["mint", "path"])
def test_e2_BOTH_containment_arms_survive_a_raising_log_sink(
        tmp_path: Path, monkeypatch, broken_sink, arm) -> None:
    """Round 7 added hostile-sink coverage for the REPO's pre-v38 warning and
    left the SERVICE-side arms tested only with a working logger -- so a plain
    ``log.warning`` at either of them passes every variant above and then, when
    a handler raises, converts a contained failure into a FAILED ENTRY.

    THE ARMS ARE TWO: the ``except Exception`` after the mint-and-validate
    ``try``, and the ``except Exception`` after ``_resolve_main_db_path``.
    """
    from swing.trades import entry as entry_mod

    conn = ensure_schema(tmp_path / f"e2_sink_{arm}.db")
    try:
        if arm == "mint":
            monkeypatch.setattr(entry_mod, "_mint_attempt_token", _raise)
            expected = None
        else:
            monkeypatch.setattr(entry_mod, "_mint_attempt_token", lambda: TOK_A)

            def _boom(_c):
                raise RuntimeError("22-A4 PROBE: PRAGMA database_list failed")

            monkeypatch.setattr(entry_mod, "_resolve_main_db_path", _boom)
            expected = TOK_A
        result = record_entry(conn, _req(), soft_warn=SOFT, hard_cap=HARD,
                              force=False, cfg=None)
        assert conn.execute(
            "SELECT attempt_id FROM trades WHERE id = ?",
            (result.trade_id,)).fetchone()[0] == expected
    finally:
        conn.close()
