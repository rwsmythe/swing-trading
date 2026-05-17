"""Shared pytest fixtures."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from swing.data.models import Fill, Trade

# ============================================================================
# Schwab API cassette filter (T-A.10 — plan §G.3)
# ============================================================================
#
# pytest-recording / VCR.py configuration applied to any test marked with
# `@pytest.mark.vcr`. Filters Schwab OAuth + Trader + Market Data sensitive
# bytes from recorded request URLs / headers / form bodies / response bodies
# BEFORE the cassette file is written to disk.
#
# Per CLAUDE.md gotcha "Finviz Elite API token storage", individual Finviz
# tests pass `filter_query_parameters=["auth"]` directly to
# `@pytest.mark.vcr` and override this fixture's broader filter list. The
# Schwab-shaped filter list below is a SUPERSET of the Finviz `auth` filter
# so it works for both surfaces.

# 32+ hex-char run, or 24+ base64-shaped run, in any response body chunk.
_TOKEN_HEX_PATTERN = re.compile(rb"[a-fA-F0-9]{32,}")
_TOKEN_B64_PATTERN = re.compile(rb"[A-Za-z0-9+/=]{24,}")
# Field-value scrubber for token-bearing JSON keys in response bodies.
# Sub-bundle 1 T-1.0 extension: id_token / code / client_id / bearerToken added
# per plan §F.3 + Codex R3 Critical #1 LOCK widening.
_RESPONSE_FIELD_SCRUBBERS: tuple[tuple[re.Pattern[bytes], bytes], ...] = (
    # Quoted JSON field values for tokens / account identifiers. The pattern
    # matches `"key"\s*:\s*"<value>"` and replaces the value slot.
    (
        re.compile(
            rb'("(?:access_token|refresh_token|client_secret|id_token|code|client_id|bearerToken)"\s*:\s*")[^"]*(")',
        ),
        rb'\1<REDACTED>\2',
    ),
    (
        re.compile(rb'("(?:accountNumber|account_number)"\s*:\s*")[^"]*(")'),
        rb'\1<REDACTED>\2',
    ),
    (
        re.compile(rb'("(?:accountHash|account_hash|hashValue)"\s*:\s*")[^"]*(")'),
        rb'\1<HASHED_REDACTED>\2',
    ),
)

# Sub-bundle 1 T-1.0 — URI/path sanitization. Schwab Trader API account-scoped
# endpoints embed accountHash in URL path segments (e.g.,
# `/trader/v1/accounts/{accountHash}/orders`). `filter_query_parameters` does
# NOT scrub path segments; Codex R2 Critical #1 + plan §F.3 LOCK require a
# `before_record_request` callable that rewrites `request.uri` before the
# cassette captures it.
_ACCOUNT_PATH_PATTERN = re.compile(r"(/accounts/)[^/?#]+")
_HEX_PATH_PATTERN = re.compile(r"\b[a-fA-F0-9]{32,}\b")
_BASE64_PATH_PATTERN = re.compile(r"\b[A-Za-z0-9+/=]{40,}={0,2}\b")


def _redact_schwab_response_body(response: dict) -> dict:
    """`before_record_response` callback for pytest-recording / VCR.py.

    Mutates the response in-place + returns it. Masks `access_token`,
    `refresh_token`, `client_secret`, `accountNumber`, `accountHash` field
    values in JSON bodies + scrubs token-shaped substrings (32+ hex, 24+
    base64) defense-in-depth.

    Per plan §G.3 lines 908-914.
    """
    body = response.get("body", {})
    raw = body.get("string") if isinstance(body, dict) else None
    if raw is None:
        return response
    if isinstance(raw, str):
        raw_bytes = raw.encode("utf-8", errors="replace")
        was_str = True
    elif isinstance(raw, (bytes, bytearray)):
        raw_bytes = bytes(raw)
        was_str = False
    else:
        return response

    # Field-value scrub (preserve JSON shape; mask the value slot).
    for pattern, replacement in _RESPONSE_FIELD_SCRUBBERS:
        raw_bytes = pattern.sub(replacement, raw_bytes)
    # Heuristic substring scrub for token-shaped runs NOT already inside a
    # <REDACTED> marker. Applied after field-value scrub so the masked
    # placeholders are stable.
    raw_bytes = _TOKEN_HEX_PATTERN.sub(b"<REDACTED>", raw_bytes)
    raw_bytes = _TOKEN_B64_PATTERN.sub(b"<REDACTED>", raw_bytes)

    body["string"] = raw_bytes.decode("utf-8", errors="replace") if was_str else raw_bytes
    response["body"] = body
    return response


def _sanitize_schwab_request(request):
    """`before_record_request` callback (Sub-bundle 1 T-1.0; Codex R2 C#1).

    Scrubs accountHash + bare token-shape substrings from `request.uri`
    BEFORE the cassette captures the request. `filter_query_parameters` only
    handles query-string params; Schwab Trader API embeds accountHash in URL
    PATH segments (e.g., `/trader/v1/accounts/{accountHash}/orders`) which
    that filter cannot reach.

    Mutates the request in-place + returns it (vcrpy contract).
    """
    uri = getattr(request, "uri", None) or ""
    if not uri:
        return request
    sanitized = _ACCOUNT_PATH_PATTERN.sub(r"\1<account>", uri)
    sanitized = _HEX_PATH_PATTERN.sub("<hex-token>", sanitized)
    sanitized = _BASE64_PATH_PATTERN.sub("<base64-token>", sanitized)
    if sanitized != uri:
        try:
            request.uri = sanitized
        except AttributeError:
            # vcrpy Request is a mutable object on supported versions; in the
            # unlikely event we're called with a read-only request shape just
            # return the unmutated original (cassette will surface the leak
            # via the post-record sentinel-leak audit).
            pass
    return request


@pytest.fixture
def vcr_config():
    """pytest-recording / VCR.py configuration applied to any `@pytest.mark.vcr`
    test that does NOT supply its own filter overrides.

    Filters cover: Authorization / Cookie / Schwab custom headers; OAuth query
    params (`code`, `refresh_token`, `client_id`, `client_secret`,
    `redirect_uri`, `access_token`, `auth`, `accountNumber`, `accountHash`);
    OAuth form-body params; response-body token + account-identifier
    substrings via `_redact_schwab_response_body`; URI/path accountHash
    segments + bare token-shape via `_sanitize_schwab_request`.

    Per plan §G.3 lines 886-905 + Sub-bundle 1 T-1.0 plan §F.3 LOCK widening
    (Codex R2 Critical #1 + Codex R3 Critical #1 + Codex R4 Minor #1) +
    CLAUDE.md gotcha "Finviz Elite API token storage" precedent.
    """
    return {
        "filter_headers": [
            "authorization", "cookie", "set-cookie",
            "schwab-client-correl-id", "schwab-client-channel",
            "schwab-client-customerid",
        ],
        "filter_query_parameters": [
            "code", "refresh_token", "client_id", "client_secret",
            "redirect_uri", "access_token", "auth",
            "accountNumber", "accountHash",
        ],
        "filter_post_data_parameters": [
            "code", "refresh_token", "client_id", "client_secret",
            "redirect_uri", "access_token",
        ],
        "before_record_request": _sanitize_schwab_request,
        "before_record_response": _redact_schwab_response_body,
    }


def insert_trade_with_entry_fill(
    conn: sqlite3.Connection, trade: Trade, *,
    event_ts: str, rationale: str | None = None,
) -> int:
    """Phase 7 Sub-C C.13: insert_trade_with_event + entry-fill in one txn.

    Per Phase 7 R2 Minor 1 warning on ``insert_trade_with_event``, callers
    MUST follow with ``insert_fill_with_event(action='entry')`` in the same
    transaction so ``trades.current_size`` reflects the entry shares.
    Without this, the exit service's `current_size - shares < 0` guard
    rejects every exit attempt with a 400. This helper bundles both.
    """
    from swing.data.repos.fills import insert_fill_with_event
    from swing.data.repos.trades import insert_trade_with_event

    trade_id = insert_trade_with_event(
        conn, trade, event_ts=event_ts, rationale=rationale,
    )
    insert_fill_with_event(
        conn,
        Fill(
            fill_id=None, trade_id=trade_id,
            fill_datetime=event_ts, action="entry",
            quantity=float(trade.initial_shares),
            price=float(trade.entry_price),
        ),
        event_ts=event_ts,
    )
    return trade_id


def cli_entry_pre_trade_args() -> list[str]:
    """Phase 7 Sub-C C.13: 11 CLI flags satisfying the post-Sub-A pre-trade gate.

    The ``swing trade entry`` command refuses entry unless the operator
    supplies a non-empty value for each of the 11 required pre-trade fields
    (Sub-A T6 added the gate). Tests that don't exercise pre-trade-form
    behavior directly should append this list to their CLI invocation so
    the gate doesn't fire for unrelated reasons.

    Tests that intentionally OMIT a field to trigger the gate should NOT
    use this helper (or should pop the relevant flag/value pair).
    """
    return [
        "--thesis", "test-thesis",
        "--why-now", "test-why-now",
        "--invalidation", "stop-hit",
        "--expected-scenario", "win",
        "--premortem-technical", "tech-risk",
        "--premortem-market-sector", "market-risk",
        "--premortem-execution", "execution-risk",
        "--emotional-state", "calm",
        "--manual-entry-confidence", "normal",
        "--market-regime", "Bullish",
        "--catalyst", "technical_only",
    ]


def insert_exit_fill(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    exit_date: str,
    exit_price: float,
    shares: int,
    reason: str | None = None,
    fill_datetime: str | None = None,
    action: str = "exit",
    close_trade: bool = True,
    notes: str | None = None,  # noqa: ARG001 — accepted for legacy-call shape compat
    realized_pnl: float | None = None,  # noqa: ARG001 — recomputed by repo, not stored
    r_multiple: float | None = None,  # noqa: ARG001 — recomputed by repo, not stored
) -> int:
    """Test helper: insert a Fill (action='exit'/'trim'/'stop') replacing legacy `Exit(...)`.

    Phase 7 Sub-C C.13 — many tests previously did:
        insert_exit_with_event(conn, Exit(id=None, trade_id=..., exit_date=...,
            exit_price=..., shares=..., reason=..., realized_pnl=..., r_multiple=...,
            notes=None), event_ts=...)
    The Exit dataclass was removed (Sub-A T3 stub raises) and `insert_exit_with_event`
    raises post-Sub-A. This helper takes the same arguments and routes them via the
    canonical fills repo. `realized_pnl` and `r_multiple` arguments are accepted
    (so call sites stay readable) but ignored — those values are derived from the
    fill at read time by the legacy shim or the consumer-side migration.
    """
    from swing.data.repos.fills import insert_fill_with_event

    if fill_datetime is None:
        fill_datetime = f"{exit_date}T16:00:00"
    fill = Fill(
        fill_id=None,
        trade_id=trade_id,
        fill_datetime=fill_datetime,
        action=action,
        quantity=float(shares),
        price=float(exit_price),
        reason=reason,
        rule_based=None,
        fees=None,
        manual_entry_confidence=None,
    )
    fill_id = insert_fill_with_event(
        conn, fill, event_ts=fill_datetime, rationale=None,
    )
    if close_trade and action == "exit":
        # Mirror production exit-service behavior: a full exit closes the trade.
        # We don't go through the state-machine helper because tests seed trades
        # in arbitrary states (entered/managing/partial_exited); just set state.
        conn.execute(
            "UPDATE trades SET state = 'closed' WHERE id = ?", (trade_id,),
        )
    return fill_id


def make_trade(
    *,
    id: int | None = None,
    ticker: str = "AAA",
    entry_date: str = "2026-01-01",
    entry_price: float = 10.0,
    initial_shares: int = 100,
    initial_stop: float = 9.0,
    current_stop: float = 9.0,
    state: str = "entered",
    watchlist_entry_target: float | None = None,
    watchlist_initial_stop: float | None = None,
    notes: str | None = None,
    # Phase 7 lifecycle defaults — provide schema-safe values so dataclass
    # callers don't have to opt in to the new fields. The entry service in
    # Sub-B sets these atomically in production; tests that don't exercise
    # entry-service code rely on these defaults.
    trade_origin: str = "manual_off_pipeline",
    pre_trade_locked_at: str = "2026-01-01T16:00:00",
    **overrides,
) -> Trade:
    """Canonical Trade fixture builder for the test corpus.

    Phase 7 Sub-A T0 introduced this builder. T3 dropped `status` from the
    Trade dataclass; this signature mirrors that change. The 18 pre-trade
    decision fields default to None via the dataclass; callers can override
    via `**overrides`.
    """
    return Trade(
        id=id,
        ticker=ticker,
        entry_date=entry_date,
        entry_price=entry_price,
        initial_shares=initial_shares,
        initial_stop=initial_stop,
        current_stop=current_stop,
        state=state,
        watchlist_entry_target=watchlist_entry_target,
        watchlist_initial_stop=watchlist_initial_stop,
        notes=notes,
        trade_origin=trade_origin,
        pre_trade_locked_at=pre_trade_locked_at,
        **overrides,
    )


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Path to a fresh temp SQLite DB (no schema applied)."""
    return tmp_path / "test.db"


@pytest.fixture
def ohlcv_factory():
    """Factory for building synthetic daily OHLCV DataFrames."""
    def _make(
        closes: list[float],
        *,
        start_date: str = "2026-01-02",
        volume: int = 1_000_000,
    ) -> pd.DataFrame:
        idx = pd.bdate_range(start=start_date, periods=len(closes))
        df = pd.DataFrame(
            {
                "Open": closes,
                "High": [c * 1.01 for c in closes],
                "Low": [c * 0.99 for c in closes],
                "Close": closes,
                "Volume": [volume] * len(closes),
            },
            index=idx,
        )
        return df

    return _make


@pytest.fixture
def sample_config(tmp_path):
    """Minimal valid Config for criterion tests."""
    from swing.config import load

    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(
        """[paths]
db_path = "swing-data/swing.db"
data_dir = "swing-data"
logs_dir = "swing-data/logs"
charts_dir = "swing-data/charts"
backups_dir = "swing-data/backups"
prices_cache_dir = "swing-data/prices-cache"
finviz_inbox_dir = "data/finviz-inbox"
exports_dir = "exports"
rs_universe_path = "reference/rs-universe.csv"

[account]
starting_equity = 1200.0
starting_date = "2026-03-16"
risk_equity_floor = 7500.0

[position_limits]
soft_warn_open = 4
hard_cap_open = 6

[risk]
max_risk_pct = 0.005

[vcp]
prior_trend_min_pct = 25.0
adr_min_pct = 4.0
pullback_max_pct = 25.0
proximity_max_pct = 5.0
tightness_days_required = 2
tightness_range_factor = 0.67
orderliness_max_bar_ratio = 3.0
orderliness_max_range_cv = 0.60

[trend_template]
min_passes = 7
allowed_miss_names = ["TT8_rs_rank"]
rising_ma_period_days = 21
high_52w_margin_pct = 25.0
low_52w_min_pct = 30.0

[rs]
horizon_weeks = 12
benchmark_ticker = "SPY"
rs_rank_min_pass = 70
fallback_extreme_pct = 20.0

[etf_exclusion]
exclude_etfs = true
manual_block = []
manual_allow = []

[focus_ranking]
closeness_to_pivot = 0.50
adr = 0.25
prior_trend = 0.25
""",
        encoding="utf-8",
    )
    return load(cfg_path)
