"""Trade entry service: caps + per-ticker check + watchlist archival."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema, run_migrations
from swing.data.models import Trade, WatchlistEntry
from swing.data.repos.fills import list_fills_for_trade
from swing.data.repos.trades import get_trade, list_open_trades
from swing.data.repos.watchlist import get_watchlist_entry, upsert_watchlist_entry
from swing.trades.entry import (
    EntryRationale, EntryRequest, EntryResult, entry_rationale_options,
    MissingPreTradeFieldsException,
    record_entry,
    SoftWarnError, HardCapError, DuplicateOpenPositionError,
)
from swing.trades.origin import EntryPath


def _pretrade_kwargs() -> dict:
    """Phase 7 Sub-B B.1: spread into any direct EntryRequest construction
    in legacy tests so the validation gate doesn't reject as missing fields.
    Spec-compliant defaults satisfying OPERATION_REQUIRED_FIELDS + the
    conditional rules (event_risk_present=0, gap_risk_present=0, catalyst
    not 'other'); tests focused on a different concern can opt in/out per
    case via override kwargs."""
    return dict(
        entry_path=EntryPath.MANUAL_WEB_FORM,
        thesis="bullish on the setup",
        why_now="VCP completed today",
        invalidation_condition="break of stop",
        expected_scenario="20% in 4 weeks",
        premortem_technical="prior pivot fails",
        premortem_market_sector="sector breaks",
        premortem_execution="size too small to matter",
        event_risk_present=0,
        event_handling="not_applicable",
        gap_risk_present=0,
        gap_risk_handling="not_applicable",
        emotional_state_pre_trade='["calm","confident"]',
        market_regime="Bullish",
        catalyst="technical_only",
        manual_entry_confidence="normal",
    )


def _req(ticker: str = "AAPL") -> EntryRequest:
    """Legacy helper, expanded post-Phase-7 B.1 to populate the 18 new
    pre-trade fields with valid defaults so existing tests stay green
    after the validation gate lands. Tickers/dates remain parameterizable;
    the new fields are spec-compliant defaults that satisfy
    OPERATION_REQUIRED_FIELDS["entry_create"] + conditional rules.
    """
    return EntryRequest(
        ticker=ticker, entry_date="2026-04-15", entry_price=180.0,
        shares=5, initial_stop=170.0, watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
        rationale=EntryRationale.VCP_BREAKOUT.value,
        event_ts="2026-04-15T09:30:00",
        entry_path=EntryPath.MANUAL_WEB_FORM,
        thesis="bullish on the setup",
        why_now="VCP completed today",
        invalidation_condition="break of 170.0 stop",
        expected_scenario="20% in 4 weeks",
        premortem_technical="prior pivot fails",
        premortem_market_sector="sector breaks",
        premortem_execution="size too small to matter",
        event_risk_present=0,
        event_handling="not_applicable",
        gap_risk_present=0,
        gap_risk_handling="not_applicable",
        emotional_state_pre_trade='["calm","confident"]',
        market_regime="Bullish",
        catalyst="technical_only",
        manual_entry_confidence="normal",
    )


def _seed_v14(tmp_path: Path) -> sqlite3.Connection:
    """Phase 7 Sub-B B.1 test fixture: schema migrated through migration 0014
    so the trades table has all 18 new columns with correct CHECK constraints."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    run_migrations(conn, target_version=16, backup_dir=tmp_path)
    return conn


def _full_req(**overrides) -> EntryRequest:
    """Build an EntryRequest with all 18 Phase 7 fields populated."""
    base = dict(
        ticker="TST", entry_date="2026-05-04",
        entry_price=10.0, shares=100, initial_stop=9.0,
        watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None, rationale="vcp-breakout",
        event_ts="2026-05-04T16:00:00",
        entry_path=EntryPath.MANUAL_WEB_FORM,
        thesis="bullish on the setup",
        why_now="VCP completed today",
        invalidation_condition="break of 9.0 stop",
        expected_scenario="20% in 4 weeks",
        premortem_technical="prior pivot fails",
        premortem_market_sector="sector breaks",
        premortem_execution="size too small to matter",
        event_risk_present=0,
        event_handling="not_applicable",
        event_type=None, event_date=None,
        gap_risk_present=0,
        gap_risk_handling="not_applicable",
        emotional_state_pre_trade='["calm","confident"]',
        market_regime="Bullish",
        catalyst="technical_only",
        catalyst_other_description=None,
        manual_entry_confidence="normal",
    )
    base.update(overrides)
    return EntryRequest(**base)


@pytest.mark.parametrize("missing_field", [
    "thesis", "why_now", "invalidation_condition", "expected_scenario",
    "premortem_technical", "premortem_market_sector", "premortem_execution",
    "emotional_state_pre_trade", "market_regime", "catalyst",
    "manual_entry_confidence",
])
def test_record_entry_rejects_missing_required_field(tmp_path, missing_field):
    conn = _seed_v14(tmp_path)
    req = _full_req(**{missing_field: None})
    with pytest.raises(MissingPreTradeFieldsException) as excinfo:
        record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
    assert missing_field in excinfo.value.missing_fields


def test_record_entry_event_risk_conditional_required(tmp_path):
    conn = _seed_v14(tmp_path)
    req = _full_req(
        event_risk_present=1, event_handling=None, event_type=None, event_date=None,
    )
    with pytest.raises(MissingPreTradeFieldsException) as excinfo:
        record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
    for required in ("event_handling", "event_type", "event_date"):
        assert required in excinfo.value.missing_fields


def test_record_entry_catalyst_other_requires_description(tmp_path):
    conn = _seed_v14(tmp_path)
    req = _full_req(catalyst="other", catalyst_other_description=None)
    with pytest.raises(MissingPreTradeFieldsException) as excinfo:
        record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
    assert "catalyst_other_description" in excinfo.value.missing_fields


def test_record_entry_force_does_NOT_bypass_missing_fields(tmp_path):
    """MissingPreTradeFieldsException is not force-bypassable per spec §9.3."""
    conn = _seed_v14(tmp_path)
    req = _full_req(thesis=None)
    with pytest.raises(MissingPreTradeFieldsException):
        record_entry(conn, req, soft_warn=10, hard_cap=20, force=True)


def test_record_entry_complete_succeeds(tmp_path):
    conn = _seed_v14(tmp_path)
    req = _full_req()
    result = record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
    assert result.trade_id > 0


# ---------------------------------------------------------------------------
# Phase 7 Sub-B B.2 — trade_origin derivation wired into record_entry.
#
# Helpers mirror tests/trades/test_origin.py verbatim (column lists + NOT
# NULL fixtures) so the entry-service tests don't drift from the origin
# service's own seed pattern. If origin.py's helpers change, update both
# in lockstep — diverging schemas here are a recurring drift class.
# ---------------------------------------------------------------------------


def _b2_insert_evaluation_run(
    conn: sqlite3.Connection, *, eval_id: int,
    run_ts: str = "2026-05-04T08:15:00",
    data_asof: str = "2026-05-01",
    action_session: str = "2026-05-04",
) -> None:
    conn.execute(
        "INSERT INTO evaluation_runs "
        "(id, run_ts, data_asof_date, action_session_date, "
        " tickers_evaluated, aplus_count, watch_count, skip_count, "
        " excluded_count, error_count) "
        "VALUES (?, ?, ?, ?, 1, 0, 0, 0, 0, 0)",
        (eval_id, run_ts, data_asof, action_session),
    )


def _b2_insert_pipeline_run(
    conn: sqlite3.Connection, *, run_id: int, eval_run_id: int | None,
    finished: bool = True,
    started_ts: str = "2026-05-04T08:00:00",
    finished_ts: str | None = "2026-05-04T08:30:00",
    data_asof: str = "2026-05-01",
    action_session: str = "2026-05-04",
) -> None:
    conn.execute(
        "INSERT INTO pipeline_runs "
        "(id, started_ts, finished_ts, trigger, data_asof_date, "
        " action_session_date, state, lease_token, evaluation_run_id) "
        "VALUES (?, ?, ?, 'manual', ?, ?, ?, ?, ?)",
        (
            run_id, started_ts,
            finished_ts if finished else None,
            data_asof, action_session,
            "complete" if finished else "running",
            f"lease-{run_id}", eval_run_id,
        ),
    )


def _b2_insert_candidate(
    conn: sqlite3.Connection, *, ticker: str, bucket: str, eval_run_id: int,
) -> None:
    conn.execute(
        "INSERT INTO candidates "
        "(evaluation_run_id, ticker, bucket, close, pivot, initial_stop, "
        " adr_pct, tight_streak, pullback_pct, prior_trend_pct, rs_rank, "
        " rs_return_12w_vs_spy, rs_method, pattern_tag, notes, sector, "
        " industry) "
        "VALUES (?, ?, ?, 10.0, NULL, 9.0, 5.0, 3, 5.0, 30.0, 50, 0.1, "
        "'universe', 'vcp', NULL, '', '')",
        (eval_run_id, ticker, bucket),
    )


@pytest.mark.parametrize("bucket,entry_path,expected_origin", [
    ("aplus", EntryPath.APLUS_TODAY_DECISION, "pipeline_aplus"),
    ("aplus", EntryPath.MANUAL_WEB_FORM,      "pipeline_aplus"),
    ("watch", EntryPath.HYP_RECS_BUTTON,      "pipeline_watch_hyp_recs"),
    ("watch", EntryPath.MANUAL_WEB_FORM,      "pipeline_watch_manual"),
])
def test_record_entry_derives_trade_origin(
    tmp_path, bucket, entry_path, expected_origin,
):
    """B.2: record_entry calls derive_trade_origin and persists the result
    on the trades row, IGNORING any value the caller might have hinted.
    Parametrize covers all 4 enum values across the bucket × entry_path
    grid that produce non-default origins."""
    conn = _seed_v14(tmp_path)
    with conn:
        _b2_insert_evaluation_run(conn, eval_id=1)
        _b2_insert_pipeline_run(conn, run_id=1, eval_run_id=1)
        _b2_insert_candidate(conn, ticker="TST", bucket=bucket, eval_run_id=1)
    req = _full_req(entry_path=entry_path)
    result = record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
    trade = get_trade(conn, result.trade_id)
    assert trade.trade_origin == expected_origin


def test_record_entry_off_pipeline_default(tmp_path):
    """B.2: no completed pipeline run anywhere → trade_origin defaults to
    'manual_off_pipeline' (the off-pipeline branch of derive_trade_origin)."""
    conn = _seed_v14(tmp_path)
    req = _full_req(entry_path=EntryPath.MANUAL_WEB_FORM)
    result = record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
    trade = get_trade(conn, result.trade_id)
    assert trade.trade_origin == "manual_off_pipeline"


def test_entry_rationale_enum_values_match_spec_order():
    """Tranche B-ops T4: EntryRationale enum is the closed taxonomy per
    spec §3 table, in the spec-declared order."""
    assert [r.value for r in EntryRationale] == [
        "aplus-setup",
        "near-trigger-breakout",
        "vcp-breakout",
        "pivot-breakout",
        "post-earnings-continuation",
        "relative-strength",
        "other",
    ]


def test_entry_rationale_options_pair_value_with_display_label():
    """entry_rationale_options() returns (value, label) pairs in enum order.
    Template consumes this to render the <select>."""
    opts = entry_rationale_options()
    assert len(opts) == 7
    assert opts[0] == ("aplus-setup", "A+ setup (today's decision)")
    assert opts[-1] == ("other", "Other (see notes)")
    # Every enum value is represented exactly once.
    assert {v for v, _ in opts} == {r.value for r in EntryRationale}


def test_basic_entry(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        result = record_entry(conn, _req(), soft_warn=4, hard_cap=6, force=False)
        assert isinstance(result, EntryResult)
        assert result.trade_id > 0
        assert result.warning is None
        t = get_trade(conn, result.trade_id)
        assert t.ticker == "AAPL"
    finally:
        conn.close()


def test_entry_persists_hypothesis_label(tmp_path: Path):
    """Brief §4.3: EntryRequest.hypothesis_label flows to trades.hypothesis_label."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        req = EntryRequest(
            ticker="HYP", entry_date="2026-04-25", entry_price=20.0,
            shares=3, initial_stop=18.0, watchlist_entry_target=None,
            watchlist_initial_stop=None, notes=None,
            rationale=EntryRationale.OTHER.value,
            event_ts="2026-04-25T09:30:00",
            hypothesis_label="Sub-A+ candidate meeting TT + price threshold",
            **_pretrade_kwargs(),
        )
        result = record_entry(conn, req, soft_warn=4, hard_cap=6, force=False)
        t = get_trade(conn, result.trade_id)
        assert t.hypothesis_label == "Sub-A+ candidate meeting TT + price threshold"
    finally:
        conn.close()


def test_entry_default_hypothesis_label_is_null(tmp_path: Path):
    """Existing-call-site preservation: EntryRequest without hypothesis_label
    defaults to None and persists NULL."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        result = record_entry(conn, _req(), soft_warn=4, hard_cap=6, force=False)
        t = get_trade(conn, result.trade_id)
        assert t.hypothesis_label is None
    finally:
        conn.close()


def test_entry_canonicalizes_hypothesis_label_at_service_boundary(tmp_path: Path):
    """Adversarial M2/M3 (round 1): non-CLI callers could otherwise persist raw
    whitespace/control-char variants and create phantom buckets in the journal
    breakdown. The service normalizes at persistence so grouping always sees
    the canonical form."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        for i, (ticker, raw) in enumerate([
            ("AAA", "  alpha  bucket  "),    # leading/trailing + double space
            ("BBB", "alpha\tbucket"),         # tab separator
            ("CCC", "alpha\x00bucket"),       # NUL byte (control)
        ]):
            req = EntryRequest(
                ticker=ticker, entry_date="2026-04-25", entry_price=10.0,
                shares=1, initial_stop=9.0, watchlist_entry_target=None,
                watchlist_initial_stop=None, notes=None,
                rationale=EntryRationale.OTHER.value,
                event_ts=f"2026-04-25T09:{i:02d}:00",
                hypothesis_label=raw,
                **_pretrade_kwargs(),
            )
            result = record_entry(conn, req, soft_warn=10, hard_cap=10, force=False)
            t = get_trade(conn, result.trade_id)
            assert t.hypothesis_label == "alpha bucket", (
                f"row {i}: got {t.hypothesis_label!r}"
            )
    finally:
        conn.close()


def test_entry_canonicalization_strips_format_characters(tmp_path: Path):
    """Adversarial R2 M1: Unicode-Cf (format) characters — zero-width spaces,
    zero-width joiners, bidi overrides — would survive a Cc-only filter and
    let two visually-identical labels group separately. Service must strip
    Cf as well so grouping stays robust to invisible-character spoofing."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        # U+200B = ZERO WIDTH SPACE (Cf), U+200D = ZERO WIDTH JOINER (Cf),
        # U+202E = RIGHT-TO-LEFT OVERRIDE (Cf).
        for i, (ticker, raw) in enumerate([
            ("ZW1", "alpha​bucket"),
            ("ZW2", "alpha‍bucket"),
            ("ZW3", "alpha‮bucket"),
        ]):
            req = EntryRequest(
                ticker=ticker, entry_date="2026-04-25", entry_price=10.0,
                shares=1, initial_stop=9.0, watchlist_entry_target=None,
                watchlist_initial_stop=None, notes=None,
                rationale=EntryRationale.OTHER.value,
                event_ts=f"2026-04-25T10:{i:02d}:00",
                hypothesis_label=raw,
                **_pretrade_kwargs(),
            )
            result = record_entry(conn, req, soft_warn=10, hard_cap=10, force=False)
            t = get_trade(conn, result.trade_id)
            assert t.hypothesis_label == "alphabucket", (
                f"row {i}: got {t.hypothesis_label!r} (expected Cf to be stripped)"
            )
    finally:
        conn.close()


def test_entry_canonicalization_normalizes_unicode_to_nfc(tmp_path: Path):
    """Adversarial R2 m2: NFC vs NFD decomposition. The string "café" can be
    encoded as composed (U+00E9) or decomposed (U+0065 U+0301). Without NFC
    normalization the same visible label groups into separate buckets."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        composed = "café"          # NFC: é as single codepoint
        decomposed = "café"        # NFD: e + combining acute
        for i, (ticker, raw) in enumerate([("NFC1", composed), ("NFC2", decomposed)]):
            req = EntryRequest(
                ticker=ticker, entry_date="2026-04-25", entry_price=10.0,
                shares=1, initial_stop=9.0, watchlist_entry_target=None,
                watchlist_initial_stop=None, notes=None,
                rationale=EntryRationale.OTHER.value,
                event_ts=f"2026-04-25T11:{i:02d}:00",
                hypothesis_label=raw,
                **_pretrade_kwargs(),
            )
            result = record_entry(conn, req, soft_warn=10, hard_cap=10, force=False)
            t = get_trade(conn, result.trade_id)
            # Both should round-trip to the NFC composed form.
            assert t.hypothesis_label == composed
    finally:
        conn.close()


def test_entry_blank_hypothesis_label_becomes_null(tmp_path: Path):
    """Whitespace-only labels (any caller, not just the CLI) collapse to None
    so the operator never accidentally creates an unnamed labeled bucket."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        req = EntryRequest(
            ticker="WSP", entry_date="2026-04-25", entry_price=10.0,
            shares=1, initial_stop=9.0, watchlist_entry_target=None,
            watchlist_initial_stop=None, notes=None,
            rationale=EntryRationale.OTHER.value,
            event_ts="2026-04-25T09:30:00",
            hypothesis_label="   \t\n  ",
            **_pretrade_kwargs(),
        )
        result = record_entry(conn, req, soft_warn=4, hard_cap=6, force=False)
        t = get_trade(conn, result.trade_id)
        assert t.hypothesis_label is None
    finally:
        conn.close()


def test_soft_warn_returns_warning_but_succeeds(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        for i, t in enumerate(["AAPL", "MSFT", "NVDA", "META"]):
            record_entry(conn, _req(t), soft_warn=10, hard_cap=10, force=False)
        result = record_entry(conn, _req("GOOG"), soft_warn=4, hard_cap=10, force=True)
        assert result.warning is not None
        assert "soft warn" in result.warning.lower()
    finally:
        conn.close()


def test_soft_warn_blocks_unless_forced(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        for t in ["AAPL", "MSFT", "NVDA", "META"]:
            record_entry(conn, _req(t), soft_warn=10, hard_cap=10, force=False)
        with pytest.raises(SoftWarnError):
            record_entry(conn, _req("GOOG"), soft_warn=4, hard_cap=10, force=False)
    finally:
        conn.close()


def test_hard_cap_blocks_even_with_force(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        for t in ["AAPL", "MSFT", "NVDA", "META", "GOOG", "TSLA"]:
            record_entry(conn, _req(t), soft_warn=10, hard_cap=10, force=False)
        with pytest.raises(HardCapError):
            record_entry(conn, _req("AMZN"), soft_warn=2, hard_cap=6, force=True)
    finally:
        conn.close()


def test_duplicate_open_position_blocked(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        record_entry(conn, _req("AAPL"), soft_warn=4, hard_cap=6, force=False)
        with pytest.raises(DuplicateOpenPositionError):
            record_entry(conn, _req("AAPL"), soft_warn=4, hard_cap=6, force=False)
    finally:
        conn.close()


def test_invalid_stop_above_entry_raises(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        bad = EntryRequest(
            ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
            shares=5, initial_stop=185.0, watchlist_entry_target=None,
            watchlist_initial_stop=None, notes=None,
            rationale="bad stop", event_ts="2026-04-15T09:30:00",
            **_pretrade_kwargs(),
        )
        with pytest.raises(ValueError, match="stop must be < entry"):
            record_entry(conn, bad, soft_warn=4, hard_cap=6, force=False)
    finally:
        conn.close()


def test_watchlist_entry_auto_archived(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10", last_qualified_date="2026-04-14",
                status="watch", qualification_count=3, not_qualified_streak=0,
                last_data_asof_date="2026-04-14",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=178.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
        result = record_entry(conn, _req("AAPL"), soft_warn=4, hard_cap=6, force=False)
        assert result.watchlist_archived is True
        assert get_watchlist_entry(conn, "AAPL") is None
    finally:
        conn.close()


def test_integrity_error_mapped_to_duplicate_exception(tmp_path: Path, monkeypatch):
    """Adversarial review Batch 3 Round 2 Minor: when the app-layer duplicate
    check is bypassed (simulated race between list_open_trades and INSERT),
    the schema-level partial unique index fires IntegrityError, and
    record_entry must map it to DuplicateOpenPositionError with the
    race-detected suffix."""
    from swing.data.repos.trades import insert_trade_with_event
    from swing.trades import entry as entry_module
    import sqlite3

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    conn = sqlite3.connect(db)
    try:
        with conn:
            insert_trade_with_event(
                conn,
                Trade(id=None, ticker="AAPL", entry_date="2026-04-15",
                      entry_price=180.0, initial_shares=5, initial_stop=170.0,
                      current_stop=170.0, state="entered",
                      watchlist_entry_target=None, watchlist_initial_stop=None,
                      notes=None),
                event_ts="2026-04-15T09:30:00",
            )
        # Simulate the race: app-layer duplicate check sees an empty list.
        monkeypatch.setattr(entry_module, "list_open_trades", lambda c: [])
        with pytest.raises(DuplicateOpenPositionError, match="race-detected"):
            record_entry(conn, _req("AAPL"), soft_warn=10, hard_cap=10, force=False)
    finally:
        conn.close()


def test_concurrent_entry_one_wins_schema_level(tmp_path: Path):
    """Adversarial review Batch 3 Critical: two concurrent record_entry calls
    for the SAME ticker — one wins, the other MUST get DuplicateOpenPositionError.
    This tests the schema-level safety net (migration 0004 partial unique index)
    by bypassing the app-layer list_open_trades check (we seed a trade directly,
    then try to insert another via the repo — the partial unique index rejects).
    """
    from swing.data.db import ensure_schema
    from swing.data.repos.trades import insert_trade_with_event
    from swing.data.models import Trade
    import sqlite3

    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    conn = sqlite3.connect(db)
    try:
        with conn:
            insert_trade_with_event(
                conn,
                Trade(id=None, ticker="AAPL", entry_date="2026-04-15",
                      entry_price=180.0, initial_shares=5, initial_stop=170.0,
                      current_stop=170.0, state="entered",
                      watchlist_entry_target=None, watchlist_initial_stop=None,
                      notes=None),
                event_ts="2026-04-15T09:30:00",
            )
        # Now try to record_entry with the same ticker. The app-layer check
        # would reject on its own, but we also want to prove the schema
        # constraint catches a race that bypasses the app check. Simulating:
        # we directly verify the partial unique index exists and refuses.
        with pytest.raises(DuplicateOpenPositionError):
            record_entry(conn, _req("AAPL"), soft_warn=10, hard_cap=10, force=False)
    finally:
        conn.close()


def test_record_entry_persists_sector_industry_as_is(tmp_path):
    """record_entry persists EntryRequest.sector + .industry AS-IS on the
    Trade row (snapshot-at-entry-surface — no re-resolve at submit time)."""
    from swing.data.db import ensure_schema
    from swing.data.repos.trades import get_trade
    from swing.trades.entry import EntryRequest, record_entry
    db_path = tmp_path / "swing.db"
    conn = ensure_schema(db_path)
    try:
        req = EntryRequest(
            ticker="ZZZF", entry_date="2026-04-28", entry_price=100.0,
            shares=10, initial_stop=95.0,
            watchlist_entry_target=None, watchlist_initial_stop=None,
            notes=None, rationale="aplus-setup",
            event_ts="2026-04-28T00:00:00",
            sector="Healthcare", industry="Pharmaceuticals",
            **_pretrade_kwargs(),
        )
        result = record_entry(conn, req, soft_warn=999, hard_cap=999, force=False)
        t = get_trade(conn, result.trade_id)
        assert t is not None
        assert t.sector == "Healthcare"
        assert t.industry == "Pharmaceuticals"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Phase 7 Sub-B B.3 — atomic INSERT trade + first entry-fill +
# pre_trade_locked_at. After B.3, record_entry inserts the trades row AND
# the first entry-action fill in a single transaction; the fill's
# _recompute_aggregates populates trades.current_size, current_avg_cost,
# last_fill_at; pre_trade_locked_at is set to req.event_ts.
# ---------------------------------------------------------------------------


def test_record_entry_writes_first_entry_fill_atomically(tmp_path):
    """B.3: trade INSERT + entry-fill INSERT in same transaction."""
    conn = _seed_v14(tmp_path)
    req = _full_req()
    result = record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
    fills = list_fills_for_trade(conn, result.trade_id)
    assert len(fills) == 1
    assert fills[0].action == "entry"
    assert fills[0].quantity == 100.0
    assert fills[0].price == 10.0
    assert fills[0].fill_datetime == "2026-05-04T16:00:00"
    assert fills[0].manual_entry_confidence == "normal"
    trade = get_trade(conn, result.trade_id)
    assert trade.pre_trade_locked_at == "2026-05-04T16:00:00"
    assert trade.state == "entered"
    assert trade.current_size == 100.0


def test_record_entry_aggregate_recompute_after_fill(tmp_path):
    """B.3 + Sub-A T4 _recompute_aggregates: trade.current_avg_cost
    populated from entry fill price; last_fill_at populated from fill
    datetime."""
    conn = _seed_v14(tmp_path)
    req = _full_req(entry_price=12.5, shares=80, initial_stop=11.0)
    result = record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
    trade = get_trade(conn, result.trade_id)
    assert trade.current_size == 80.0
    assert trade.current_avg_cost == 12.5
    assert trade.last_fill_at == req.event_ts


def test_record_entry_atomic_rollback_on_fill_failure(tmp_path, monkeypatch):
    """B.3 atomic guarantee: if the fill insert raises, the trade INSERT
    also rolls back — no orphaned trade row with current_size=0 / NULL
    aggregates is left behind. Validates that record_entry wraps BOTH
    inserts in the same `with conn:` block (single transaction)."""
    from swing.trades import entry as entry_module

    conn = _seed_v14(tmp_path)

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated fill insert failure")

    monkeypatch.setattr(entry_module, "insert_fill_with_event", _boom)

    req = _full_req()
    with pytest.raises(RuntimeError, match="simulated fill insert failure"):
        record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)

    # Trade row was rolled back — no orphaned row.
    rows = conn.execute("SELECT COUNT(*) FROM trades").fetchone()
    assert rows[0] == 0
    # And no fills row either.
    fill_rows = conn.execute("SELECT COUNT(*) FROM fills").fetchone()
    assert fill_rows[0] == 0


def test_entry_request_default_sector_industry_empty():
    """EntryRequest constructed without sector/industry uses '' defaults."""
    from swing.trades.entry import EntryRequest
    req = EntryRequest(
        ticker="DFLT", entry_date="2026-04-28", entry_price=100.0,
        shares=10, initial_stop=95.0,
        watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None, rationale="aplus-setup",
        event_ts="2026-04-28T00:00:00",
    )
    assert req.sector == ""
    assert req.industry == ""


# ---------------------------------------------------------------------------
# Codex R4 Major 1 regression guard — back-recorded entries on entry_date.
# ---------------------------------------------------------------------------


def test_record_entry_uses_entry_date_for_pre_trade_locked_at_and_fill_datetime(
    tmp_path,
):
    """Codex R4 M1: pre_trade_locked_at + first-fill datetime must reflect
    when the trade actually entered (req.entry_date), NOT when the operator
    typed the command (req.event_ts).

    Pre-fix: a back-recorded entry (entry_date=2026-05-01, event_ts=now())
    persisted pre_trade_locked_at and fill_datetime as today's clock-time,
    breaking entry-side fill ordering and date-based reporting.
    Post-fix: both fields synthesize "2026-05-01T16:00:00" via the shared
    _normalize_trade_event_date_to_iso helper.
    """
    from swing.data.repos.fills import list_fills_for_trade
    conn = _seed_v14(tmp_path)
    req = _full_req(
        entry_date="2026-05-01",  # back-record (was 2026-05-04)
        event_ts="2026-05-04T12:34:56",
    )
    result = record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
    trade = get_trade(conn, result.trade_id)
    fills = list_fills_for_trade(conn, result.trade_id)
    assert len(fills) == 1
    assert fills[0].fill_datetime == "2026-05-01T16:00:00", (
        f"fill_datetime must reflect entry_date 2026-05-01, "
        f"got {fills[0].fill_datetime!r}"
    )
    assert trade.pre_trade_locked_at == "2026-05-01T16:00:00", (
        f"pre_trade_locked_at must reflect entry_date 2026-05-01, "
        f"got {trade.pre_trade_locked_at!r}"
    )


def test_record_entry_rejects_malformed_entry_date(tmp_path):
    """Codex R4 M1: entry_date must validate before any INSERT. A malformed
    string like '2026-13-99' raises ValueError; no trade or fill written."""
    conn = _seed_v14(tmp_path)
    req = _full_req(entry_date="2026-13-99")
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
    n_trades = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    assert n_trades == 0


def test_record_entry_rejects_timezone_aware_entry_date(tmp_path):
    """Codex R4 M1 + R5 M1: tz-aware entry_date is rejected. After R5's
    date-only entry-side guard, the rejection fires earlier on the
    'must be YYYY-MM-DD only' check before the helper's tz check would,
    but either way the input is refused before any INSERT."""
    conn = _seed_v14(tmp_path)
    req = _full_req(entry_date="2026-05-01T09:30:00+05:00")
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)


def test_record_entry_rejects_full_iso_datetime_entry_date(tmp_path):
    """Codex R5 M1: trades.entry_date is date-only; full ISO datetime input
    must be rejected at the API boundary (entry-side guard fires before the
    shared helper would otherwise synthesize ISO).

    Pre-fix: entry_date='2026-05-01T09:30:00' was accepted by the helper
    (full ISO branch) and the raw string flowed through to trades.entry_date,
    where downstream consumers (advisory, journal, briefing, CLI) crash on
    date.fromisoformat parse failure.
    Post-fix: rejected with a clear 'must be YYYY-MM-DD' message; no INSERT.
    """
    conn = _seed_v14(tmp_path)
    req = _full_req(entry_date="2026-05-01T09:30:00")
    with pytest.raises(ValueError, match="must be YYYY-MM-DD only"):
        record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
    n_trades = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    assert n_trades == 0


def test_record_entry_persists_entry_date_as_yyyymmdd(tmp_path):
    """Codex R5 M1: trades.entry_date stored as YYYY-MM-DD verbatim
    (date.fromisoformat-parseable) — the ISO-with-T form is reserved for
    pre_trade_locked_at + fill_datetime synthesis."""
    from datetime import date
    conn = _seed_v14(tmp_path)
    req = _full_req(entry_date="2026-05-01")
    result = record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
    trade = get_trade(conn, result.trade_id)
    assert trade.entry_date == "2026-05-01"
    parsed = date.fromisoformat(trade.entry_date)
    assert parsed.isoformat() == "2026-05-01"


def test_record_entry_emits_exactly_one_entry_event(tmp_path):
    """Hotfix regression 2026-05-05: operator-witnessed gate finding S3.

    record_entry calls insert_trade_with_event (which writes a trade_events
    row with event_type='entry') AND insert_fill_with_event (which would
    ALSO write a trade_events row with event_type='entry' if not suppressed,
    since fill.action=='entry' maps to audit_event_type='entry'). Pre-hotfix:
    every record_entry call produced 2 duplicate entry events. Post-hotfix:
    record_entry passes ``emit_event=False`` to insert_fill_with_event so
    the second emission is suppressed; exactly 1 entry event remains.

    Discriminating shape: pre-hotfix this test fails with `event_count == 2`
    (verified by stash + run prior to hotfix application). Post-hotfix:
    `event_count == 1`.
    """
    conn = _seed_v14(tmp_path)
    req = _full_req()
    result = record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
    entry_events = conn.execute(
        "SELECT id, ts, event_type, rationale FROM trade_events "
        "WHERE trade_id = ? AND event_type = 'entry'",
        (result.trade_id,),
    ).fetchall()
    assert len(entry_events) == 1, (
        f"Expected exactly 1 'entry' trade_event row after record_entry; "
        f"got {len(entry_events)}: {entry_events}. Pre-hotfix value would be "
        f"2 (insert_trade_with_event + insert_fill_with_event both emitted)."
    )
