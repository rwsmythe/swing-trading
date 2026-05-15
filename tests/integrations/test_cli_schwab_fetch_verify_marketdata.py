"""Phase 11 T-C.5 — `swing schwab fetch --verify-marketdata` CLI tests.

Per dispatch brief §3 surface S3 disposition (b): `--verify-marketdata` is a
verification-only subcommand exercising the schwabdev market-data API
endpoints (/quotes + /price_history). Both sandbox + production envs
produce ordinary `success`/`error` audit rows; the env switch determines
which tokens DB is loaded, NOT short-circuit behavior. NO cache writes
under any env — this subcommand does NOT install the ladder fetcher hook
into PriceCache/OhlcvCache, and it does NOT write to the OHLCV archive.

Per plan §H.10: `--verify-marketdata` is in the 3-SAFE-subcommands list
(alongside `status` + `refresh`); it does NOT enforce the pipeline-active
exclusion check.

6 tests + the un-skipped cross-bundle pin
(`test_schwab_pipeline_active_exclusion.py::test_b6_10_*`).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import click
import pytest
from click.testing import CliRunner

from swing.data.db import ensure_schema


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch):
    """Isolate USERPROFILE + HOME per CLAUDE.md gotcha for write_user_overrides."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "swing-data").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def isolated_db(isolated_home):
    db_path = isolated_home / "swing-data" / "swing.db"
    ensure_schema(db_path).close()
    return db_path


def _make_cfg(
    *,
    db_path: Path,
    environment: str = "production",
    account_hash: str | None = "abc...64charhash",
) -> SimpleNamespace:
    return SimpleNamespace(
        paths=SimpleNamespace(db_path=Path(db_path)),
        integrations=SimpleNamespace(
            schwab=SimpleNamespace(
                environment=environment,
                account_hash=account_hash,
                lookback_days=7,
                timeout_seconds=30.0,
                marketdata_ladder_enabled=True,
                callback_url="https://127.0.0.1",
            ),
            finviz=SimpleNamespace(token="", screen_query="", timeout_seconds=30),
        ),
    )


def _make_quotes_payload(symbols: list[str]) -> dict:
    """Construct a Schwab-style quotes response payload."""
    return {
        s: {
            "quote": {
                "lastPrice": 100.0 + i,
                "bidPrice": 99.0 + i,
                "askPrice": 101.0 + i,
                "mark": 100.0 + i,
                "quoteTime": "2026-05-14T15:30:00Z",
                "delayed": False,
            },
        }
        for i, s in enumerate(symbols)
    }


def _make_price_history_payload() -> dict:
    """Construct a Schwab-style price_history response payload (3 bars)."""
    return {
        "empty": False,
        "symbol": "AAPL",
        "candles": [
            {
                "datetime": 1747094400000,  # 2025-05-13 UTC
                "open": 100.0, "high": 101.0, "low": 99.0,
                "close": 100.5, "volume": 1_000_000,
            },
            {
                "datetime": 1747180800000,  # 2025-05-14 UTC
                "open": 100.5, "high": 102.0, "low": 100.0,
                "close": 101.5, "volume": 1_100_000,
            },
            {
                "datetime": 1747267200000,  # 2025-05-15 UTC
                "open": 101.5, "high": 103.0, "low": 101.0,
                "close": 102.5, "volume": 1_200_000,
            },
        ],
    }


def _stub_schwabdev_client(
    monkeypatch,
    *,
    quotes_symbols: list[str] | None = None,
    quotes_status: int = 200,
    price_history_status: int = 200,
    price_history_empty: bool = False,
):
    """Patch schwabdev.Client to return a MagicMock with quotes + price_history."""
    mock_client = MagicMock()
    mock_client.tokens.access_token = "stub_access_token_12345"
    mock_client.tokens.refresh_token = "stub_refresh_token_12345"

    # quotes response.
    quotes_resp = MagicMock()
    payload_symbols = quotes_symbols if quotes_symbols is not None else ["AAPL"]
    quotes_resp.json.return_value = _make_quotes_payload(payload_symbols)
    quotes_resp.status_code = quotes_status
    quotes_resp.headers = {}
    mock_client.quotes.return_value = quotes_resp

    # price_history response.
    ph_resp = MagicMock()
    if price_history_empty:
        ph_resp.json.return_value = {"empty": True, "candles": [], "symbol": "AAPL"}
    else:
        ph_resp.json.return_value = _make_price_history_payload()
    ph_resp.status_code = price_history_status
    ph_resp.headers = {}
    mock_client.price_history.return_value = ph_resp

    import schwabdev
    monkeypatch.setattr(schwabdev, "Client", MagicMock(return_value=mock_client))
    return mock_client


@pytest.fixture
def invoke_cli():
    runner = CliRunner()

    def _invoke(cfg, *args, input_str: str = "cid\ncsecret\n"):
        from swing.cli_schwab import schwab_group

        @click.group()
        @click.pass_context
        def root(ctx):
            ctx.obj = {"config": cfg}

        root.add_command(schwab_group)
        return runner.invoke(root, ["schwab", *args], input=input_str)
    return _invoke


# ============================================================================
# T-C.5 Tests
# ============================================================================


def test_c5_01_verify_marketdata_production_writes_audit_no_cache(
    isolated_home, isolated_db, invoke_cli, monkeypatch,
):
    """Production env: audit rows written; NO cache writes (no OHLCV archive)."""
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    _stub_schwabdev_client(monkeypatch, quotes_symbols=["AAPL"])
    result = invoke_cli(cfg, "fetch", "--verify-marketdata")
    assert result.exit_code == 0, result.output

    # Verify audit rows.
    conn = sqlite3.connect(isolated_db)
    try:
        # quotes + price_history endpoints both audited.
        rows = conn.execute(
            "SELECT endpoint, surface, environment, status FROM schwab_api_calls "
            "ORDER BY call_id ASC"
        ).fetchall()
        assert len(rows) == 2
        endpoints = {r[0] for r in rows}
        assert endpoints == {"marketdata.quotes", "marketdata.pricehistory"}
        for r in rows:
            assert r[1] == "cli"  # surface
            assert r[2] == "production"  # environment
            assert r[3] == "success"
        # linked_snapshot_id + linked_reconciliation_run_id stay NULL.
        link_rows = conn.execute(
            "SELECT linked_snapshot_id, linked_reconciliation_run_id "
            "FROM schwab_api_calls"
        ).fetchall()
        for r in link_rows:
            assert r[0] is None
            assert r[1] is None
    finally:
        conn.close()

    # No cache writes: OHLCV archive directory should be empty (or non-existent).
    archive_dir = isolated_home / "swing-data" / "ohlcv-archive"
    if archive_dir.exists():
        # The archive directory may exist from other setup but must contain
        # no parquet files attributable to this verification call.
        parquet_files = list(archive_dir.rglob("*.parquet"))
        assert parquet_files == [], (
            f"--verify-marketdata must NOT write to OHLCV archive; "
            f"found {parquet_files}"
        )


def test_c5_02_verify_marketdata_sandbox_writes_audit_no_cache(
    isolated_home, isolated_db, invoke_cli, monkeypatch,
):
    """Sandbox env: ordinary success audit rows; env=sandbox; NO cache writes.

    Per dispatch brief §3 interpretation (b): the CLI does NOT short-circuit
    on sandbox; it invokes schwabdev market-data endpoints regardless. The
    sandbox/prod difference is "which tokens DB is loaded". Verification-only.
    """
    cfg = _make_cfg(db_path=isolated_db, environment="sandbox")
    _stub_schwabdev_client(monkeypatch, quotes_symbols=["AAPL"])
    result = invoke_cli(cfg, "fetch", "--verify-marketdata")
    assert result.exit_code == 0, result.output

    conn = sqlite3.connect(isolated_db)
    try:
        rows = conn.execute(
            "SELECT endpoint, surface, environment, status FROM schwab_api_calls "
            "ORDER BY call_id ASC"
        ).fetchall()
        assert len(rows) == 2
        for r in rows:
            assert r[1] == "cli"
            assert r[2] == "sandbox"
            assert r[3] == "success"
    finally:
        conn.close()

    archive_dir = isolated_home / "swing-data" / "ohlcv-archive"
    if archive_dir.exists():
        parquet_files = list(archive_dir.rglob("*.parquet"))
        assert parquet_files == []


@pytest.mark.parametrize(
    "symbols_arg,expected",
    [
        ("AAPL", ["AAPL"]),
        ("AAPL,AMD", ["AAPL", "AMD"]),
        ("AAPL,AMD,GOOG", ["AAPL", "AMD", "GOOG"]),
        ("AAPL ,AMD", ["AAPL", "AMD"]),  # whitespace stripped
        (" AAPL , AMD ", ["AAPL", "AMD"]),  # leading/trailing trimmed
    ],
)
def test_c5_03_verify_marketdata_symbols_flag_parses(
    isolated_db, invoke_cli, monkeypatch, symbols_arg, expected,
):
    """`--symbols` parses comma-separated list; whitespace stripped per element."""
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    mc = _stub_schwabdev_client(monkeypatch, quotes_symbols=expected)
    result = invoke_cli(
        cfg, "fetch", "--verify-marketdata", "--symbols", symbols_arg,
    )
    assert result.exit_code == 0, result.output
    # Verify the call was made with the parsed symbol list.
    quotes_call = mc.quotes.call_args
    assert quotes_call is not None
    actual_symbols = quotes_call.kwargs.get("symbols") or (
        quotes_call.args[0] if quotes_call.args else None
    )
    assert actual_symbols == expected


def test_c5_04_verify_marketdata_default_symbol_is_aapl(
    isolated_db, invoke_cli, monkeypatch,
):
    """When `--symbols` omitted: defaults to AAPL (operator smoke-test pattern)."""
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    mc = _stub_schwabdev_client(monkeypatch, quotes_symbols=["AAPL"])
    result = invoke_cli(cfg, "fetch", "--verify-marketdata")
    assert result.exit_code == 0, result.output

    # quotes call uses AAPL.
    quotes_call = mc.quotes.call_args
    actual_symbols = quotes_call.kwargs.get("symbols")
    assert actual_symbols == ["AAPL"]

    # price_history call also uses AAPL (positional first arg).
    ph_call = mc.price_history.call_args
    actual_symbol = ph_call.args[0] if ph_call.args else ph_call.kwargs.get("symbol")
    assert actual_symbol == "AAPL"


def test_c5_05_verify_marketdata_partial_quotes_surfaces_in_output(
    isolated_db, invoke_cli, monkeypatch,
):
    """Partial-response on quotes: stdout/stderr shows e.g. '1/2 OK; failed: XYZ'.

    Construct a quotes payload where 1 of 2 symbols is OK; the other is an
    error envelope. The marketdata.py `get_quotes_batch` finish_hook produces
    the partial-response audit message; CLI surfaces it to operator output.
    Exit code stays 0 because at least one symbol succeeded.
    """
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    # Stub a payload with AAPL succeeding + XYZ failing (error envelope).
    mc = MagicMock()
    mc.tokens.access_token = "stub_access_token"
    mc.tokens.refresh_token = "stub_refresh_token"
    quotes_resp = MagicMock()
    quotes_resp.json.return_value = {
        "AAPL": {
            "quote": {
                "lastPrice": 100.0, "bidPrice": 99.0, "askPrice": 101.0,
                "mark": 100.0, "quoteTime": "2026-05-14T15:30:00Z",
                "delayed": False,
            },
        },
        "XYZ": {"errors": [{"code": "404", "message": "symbol not found"}]},
    }
    quotes_resp.status_code = 200
    quotes_resp.headers = {}
    mc.quotes.return_value = quotes_resp

    ph_resp = MagicMock()
    ph_resp.json.return_value = _make_price_history_payload()
    ph_resp.status_code = 200
    ph_resp.headers = {}
    mc.price_history.return_value = ph_resp

    import schwabdev
    monkeypatch.setattr(schwabdev, "Client", MagicMock(return_value=mc))

    result = invoke_cli(
        cfg, "fetch", "--verify-marketdata", "--symbols", "AAPL,XYZ",
    )
    assert result.exit_code == 0, result.output
    # Operator-visible partial summary.
    assert "1/2 OK" in result.output
    assert "XYZ" in result.output

    # Audit row carries the partial-success message.
    conn = sqlite3.connect(isolated_db)
    try:
        row = conn.execute(
            "SELECT status, error_message FROM schwab_api_calls "
            "WHERE endpoint = 'marketdata.quotes' ORDER BY call_id DESC LIMIT 1"
        ).fetchone()
        assert row[0] == "success"
        assert row[1] is not None
        assert "1/2 OK" in row[1]
    finally:
        conn.close()


def test_c5_06_verify_marketdata_401_handled_as_friendly_error(
    isolated_db, invoke_cli, monkeypatch,
):
    """401 (SchwabAuthError) surfaces as ClickException with friendly message
    + non-zero exit code; audit row written with `status='auth_failed'`.
    """
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    mc = MagicMock()
    mc.tokens.access_token = "stub_access_token"
    mc.tokens.refresh_token = "stub_refresh_token"
    # quotes returns HTTP 401.
    quotes_resp = MagicMock()
    quotes_resp.json.return_value = {"error": "unauthorized"}
    quotes_resp.status_code = 401
    quotes_resp.headers = {}
    mc.quotes.return_value = quotes_resp
    # price_history won't be called, but stub anyway.
    ph_resp = MagicMock()
    ph_resp.json.return_value = _make_price_history_payload()
    ph_resp.status_code = 200
    ph_resp.headers = {}
    mc.price_history.return_value = ph_resp

    import schwabdev
    monkeypatch.setattr(schwabdev, "Client", MagicMock(return_value=mc))

    result = invoke_cli(cfg, "fetch", "--verify-marketdata")
    assert result.exit_code != 0
    # Operator-visible friendly error.
    assert (
        "auth" in result.output.lower()
        or "401" in result.output
        or "Authentication" in result.output
    )

    conn = sqlite3.connect(isolated_db)
    try:
        row = conn.execute(
            "SELECT status, http_status FROM schwab_api_calls "
            "WHERE endpoint = 'marketdata.quotes' ORDER BY call_id DESC LIMIT 1"
        ).fetchone()
        assert row[0] == "auth_failed"
        assert row[1] == 401
    finally:
        conn.close()


def test_c5_06b_verify_marketdata_429_rate_limit_handled(
    isolated_db, invoke_cli, monkeypatch,
):
    """429 (SchwabRateLimitError) surfaces with non-zero exit code +
    audit row with `status='rate_limited'`.

    Secondary discriminating coverage for the auth/rate exception family
    per pre-emption #6 — paired with c5_06 (401 path).
    """
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    mc = MagicMock()
    mc.tokens.access_token = "stub_access_token"
    mc.tokens.refresh_token = "stub_refresh_token"
    quotes_resp = MagicMock()
    quotes_resp.json.return_value = {"error": "rate limit exceeded"}
    quotes_resp.status_code = 429
    quotes_resp.headers = {"X-RateLimit-Remaining": "0"}
    mc.quotes.return_value = quotes_resp
    ph_resp = MagicMock()
    ph_resp.json.return_value = _make_price_history_payload()
    ph_resp.status_code = 200
    ph_resp.headers = {}
    mc.price_history.return_value = ph_resp

    import schwabdev
    monkeypatch.setattr(schwabdev, "Client", MagicMock(return_value=mc))

    result = invoke_cli(cfg, "fetch", "--verify-marketdata")
    assert result.exit_code != 0

    conn = sqlite3.connect(isolated_db)
    try:
        row = conn.execute(
            "SELECT status, http_status FROM schwab_api_calls "
            "WHERE endpoint = 'marketdata.quotes' ORDER BY call_id DESC LIMIT 1"
        ).fetchone()
        assert row[0] == "rate_limited"
        assert row[1] == 429
    finally:
        conn.close()


# ============================================================================
# Additional defense-in-depth: --symbols parses to empty → reject; pipeline-
# active should NOT block (covered separately by the un-skipped
# test_b6_10_fetch_verify_marketdata_NOT_protected test).
# ============================================================================


def test_c5_07_verify_marketdata_empty_symbols_rejected(
    isolated_db, invoke_cli, monkeypatch,
):
    """`--symbols ""` or `--symbols ","` parses to empty list → friendly error.

    Operator typo defense. Discriminating: the parsing pre-empts the
    schwabdev call entirely (no audit row written; no schwabdev.quotes
    invocation).
    """
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    mc = _stub_schwabdev_client(monkeypatch, quotes_symbols=["AAPL"])
    result = invoke_cli(cfg, "fetch", "--verify-marketdata", "--symbols", " , ")
    assert result.exit_code != 0
    # No schwabdev calls.
    assert mc.quotes.call_count == 0
    assert mc.price_history.call_count == 0
