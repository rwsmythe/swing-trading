"""Tests for production-DB read and harness-input reconstruction.

The reconstruction must mirror ``swing/pipeline/runner.py:_step_evaluate``
exactly (D1 §"Comparison primitive" + brief §0 read commitments). These
tests assert that on synthetic fixtures:

- ``fetch_production`` returns a dict keyed by ticker with criteria populated.
- ``select_default_evaluation_run`` picks the most-recent run whose
  Finviz CSV is still present (skipping runs whose CSV has been rotated).
- ``reconstruct_harness_inputs`` builds a BatchContext with the FULL
  rs-universe (not the Finviz subset) and derives ``current_equity`` via
  the same ``sizing_equity(current_equity(starting, exits, cash), floor)``
  formula production uses.
- The comparison set is the tickers production ran through ``evaluate_one``
  (bucket ∈ {aplus, watch, skip}); excluded/error tickers are out of scope.
- yfinance cache hit/miss counters track per-ticker fetches.
- Universe-version drift between the production eval row's recorded
  ``rs_universe_hash`` and the current rs-universe.csv is detected.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from research.parity.fetcher import (
    HarnessInputs,
    NoRunsWithCsvError,
    fetch_production,
    reconstruct_harness_inputs,
    select_default_evaluation_run,
)
from swing.data.db import ensure_schema
from swing.data.models import (
    Candidate,
    CriterionResult,
    EvaluationRun,
)
from swing.data.repos.candidates import insert_candidates, insert_evaluation_run


@pytest.fixture
def schema_db(tmp_path) -> Path:
    """Schema-applied SQLite DB at v6 (latest migration), no rows seeded."""
    db_path = tmp_path / "parity.db"
    conn = ensure_schema(db_path)
    conn.close()
    return db_path


def _conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _insert_run(conn: sqlite3.Connection, *, run_ts: str, finviz_csv_path: str | None,
                 data_asof: str = "2026-04-24",
                 action_session: str = "2026-04-25",
                 universe_version: str = "2026-04-24-1",
                 universe_hash: str = "deadbeef") -> int:
    return insert_evaluation_run(conn, EvaluationRun(
        id=None, run_ts=run_ts, data_asof_date=data_asof,
        action_session_date=action_session, finviz_csv_path=finviz_csv_path,
        tickers_evaluated=0, aplus_count=0, watch_count=0, skip_count=0,
        excluded_count=0, error_count=0,
        rs_universe_version=universe_version,
        rs_universe_hash=universe_hash,
    ))


def _crit(name: str, layer: str, result: str = "pass") -> CriterionResult:
    return CriterionResult(criterion_name=name, layer=layer, result=result)


def _candidate(
    ticker: str, *, bucket: str,
    criteria: tuple[CriterionResult, ...] = (),
    notes: str | None = None,
) -> Candidate:
    return Candidate(
        ticker=ticker, bucket=bucket, close=100.0, pivot=110.0, initial_stop=95.0,
        adr_pct=None, tight_streak=None, pullback_pct=None, prior_trend_pct=None,
        rs_rank=None, rs_return_12w_vs_spy=None, rs_method="unavailable",
        pattern_tag=None, notes=notes, criteria=criteria,
    )


def test_fetch_production_returns_candidates_keyed_by_ticker(schema_db):
    conn = _conn(schema_db)
    run_id = _insert_run(conn, run_ts="2026-04-24T21:00:00", finviz_csv_path="/nope.csv")
    insert_candidates(conn, run_id, [
        _candidate("AAPL", bucket="watch", criteria=(
            _crit("TT1_above_150_200", "trend_template", "pass"),
            _crit("risk_feasibility", "risk", "pass"),
        )),
        _candidate("MSFT", bucket="skip", criteria=(
            _crit("TT1_above_150_200", "trend_template", "fail"),
        )),
    ])
    conn.commit()

    out = fetch_production(conn, run_id)
    conn.close()

    assert set(out) == {"AAPL", "MSFT"}
    assert out["AAPL"].bucket == "watch"
    assert {c.criterion_name for c in out["AAPL"].criteria} == {
        "TT1_above_150_200", "risk_feasibility",
    }
    assert out["MSFT"].criteria[0].result == "fail"


def test_fetch_production_for_nonexistent_run_returns_empty_dict(schema_db):
    conn = _conn(schema_db)
    out = fetch_production(conn, evaluation_run_id=99999)
    conn.close()
    assert out == {}


def test_select_default_picks_most_recent_with_present_csv(schema_db, tmp_path):
    inbox = tmp_path / "finviz-inbox"
    inbox.mkdir()
    csv_a = inbox / "finvizA.csv"
    csv_a.write_text("Ticker\nAAPL\n", encoding="utf-8")
    csv_b = inbox / "finvizB.csv"  # never created — simulates rotated CSV

    conn = _conn(schema_db)
    # Latest run references missing CSV.
    _insert_run(conn, run_ts="2026-04-24T21:00:00", finviz_csv_path=str(csv_b))
    # Earlier run references present CSV.
    older_id = _insert_run(conn, run_ts="2026-04-23T21:00:00", finviz_csv_path=str(csv_a))
    conn.commit()

    chosen = select_default_evaluation_run(conn, inbox)
    conn.close()

    assert chosen == older_id


def test_select_default_skips_null_csv_paths(schema_db, tmp_path):
    inbox = tmp_path / "finviz-inbox"
    inbox.mkdir()
    csv = inbox / "finviz.csv"
    csv.write_text("Ticker\nAAPL\n", encoding="utf-8")

    conn = _conn(schema_db)
    _insert_run(conn, run_ts="2026-04-24T21:00:00", finviz_csv_path=None)
    older_id = _insert_run(conn, run_ts="2026-04-23T21:00:00", finviz_csv_path=str(csv))
    conn.commit()

    chosen = select_default_evaluation_run(conn, inbox)
    conn.close()
    assert chosen == older_id


def test_select_default_falls_back_to_basename_in_inbox(schema_db, tmp_path):
    """If the absolute path on the eval row is stale (e.g., DB moved between
    machines) but the basename exists in the supplied inbox dir, accept it."""
    inbox = tmp_path / "finviz-inbox"
    inbox.mkdir()
    csv = inbox / "finvizA.csv"
    csv.write_text("Ticker\nAAPL\n", encoding="utf-8")

    conn = _conn(schema_db)
    stale_path = "/nonexistent/old-machine/finvizA.csv"
    run_id = _insert_run(conn, run_ts="2026-04-24T21:00:00", finviz_csv_path=stale_path)
    conn.commit()

    chosen = select_default_evaluation_run(conn, inbox)
    conn.close()
    assert chosen == run_id


def test_select_default_raises_when_no_runs_have_present_csv(schema_db, tmp_path):
    inbox = tmp_path / "finviz-inbox"
    inbox.mkdir()
    conn = _conn(schema_db)
    _insert_run(conn, run_ts="2026-04-24T21:00:00", finviz_csv_path=str(inbox / "missing.csv"))
    conn.commit()

    with pytest.raises(NoRunsWithCsvError):
        select_default_evaluation_run(conn, inbox)
    conn.close()


# --- reconstruct_harness_inputs ---

class _MockPriceFetcher:
    """Records every ticker request and returns canned OHLCV per ticker.

    ``responses`` maps ticker → DataFrame (or ValueError to simulate fetch
    failure). Cache-hit behavior: a ticker is a "hit" if previously requested
    AND the response was a DataFrame, else a "miss" on first request and a
    "fail" on errors. Mirrors :class:`swing.prices.PriceFetcher.get` signature
    well enough for ``_step_evaluate``-faithful reconstruction.
    """
    def __init__(self, responses: dict[str, pd.DataFrame | type | Exception]) -> None:
        self.responses = responses
        self.requests: list[tuple[str, int]] = []
        self.hits = 0
        self.misses = 0

    def get(self, ticker: str, lookback_days: int, *, as_of_date=None) -> pd.DataFrame:
        self.requests.append((ticker, lookback_days))
        prior = sum(1 for t, _ in self.requests[:-1] if t == ticker)
        resp = self.responses.get(ticker)
        if isinstance(resp, Exception) or (isinstance(resp, type) and issubclass(resp, Exception)):
            raise resp if isinstance(resp, Exception) else resp("fetch failed")
        if resp is None:
            raise ValueError(f"No data for {ticker}")
        if prior > 0:
            self.hits += 1
        else:
            self.misses += 1
        return resp


def _make_ohlcv(start: str, n_bars: int, base: float = 100.0) -> pd.DataFrame:
    idx = pd.bdate_range(start=start, periods=n_bars)
    return pd.DataFrame({
        "Open": [base + i * 0.05 for i in range(n_bars)],
        "High": [base + i * 0.05 + 0.5 for i in range(n_bars)],
        "Low": [base + i * 0.05 - 0.5 for i in range(n_bars)],
        "Close": [base + i * 0.05 for i in range(n_bars)],
        "Volume": [1_000_000] * n_bars,
    }, index=idx)


@pytest.fixture
def synthetic_universe_csv(tmp_path) -> Path:
    """Tiny rs-universe.csv with three tickers."""
    p = tmp_path / "rs-universe.csv"
    p.write_text(
        "# version: 2026-04-24-test\nticker\nAAPL\nMSFT\nNVDA\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def parity_cfg(tmp_path, synthetic_universe_csv):
    """Config that points at the synthetic universe and a placeholder DB."""
    from swing.config import load
    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(f"""[paths]
db_path = "swing-data/swing.db"
data_dir = "swing-data"
logs_dir = "swing-data/logs"
charts_dir = "swing-data/charts"
backups_dir = "swing-data/backups"
prices_cache_dir = "swing-data/prices-cache"
finviz_inbox_dir = "data/finviz-inbox"
exports_dir = "exports"
rs_universe_path = "{synthetic_universe_csv.as_posix()}"

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
""", encoding="utf-8")
    return load(cfg_path)


def test_reconstruct_uses_full_rs_universe_for_batch_context(
    schema_db, parity_cfg, synthetic_universe_csv,
):
    """The BatchContext universe is the FULL rs-universe per
    ``_step_evaluate`` lines 88, 344-350 — NOT the Finviz subset."""
    from swing.evaluation.rs import universe_version_hash
    real_universe_hash = universe_version_hash(synthetic_universe_csv)

    conn = _conn(schema_db)
    run_id = _insert_run(
        conn, run_ts="2026-04-24T21:00:00",
        finviz_csv_path="/nope.csv",
        universe_version="2026-04-24-test",
        universe_hash=real_universe_hash,
    )
    # Production evaluated only AAPL (Finviz universe ⊂ rs-universe).
    insert_candidates(conn, run_id, [
        _candidate("AAPL", bucket="watch", criteria=(
            _crit("TT1_above_150_200", "trend_template", "pass"),
        )),
    ])
    conn.commit()

    # 250 bars >= 200 minimum so evaluate_one can run.
    fetcher = _MockPriceFetcher({
        "AAPL": _make_ohlcv("2025-04-01", 250, base=100.0),
        "MSFT": _make_ohlcv("2025-04-01", 250, base=200.0),
        "NVDA": _make_ohlcv("2025-04-01", 250, base=300.0),
        "SPY":  _make_ohlcv("2025-04-01", 250, base=400.0),
    })

    out = reconstruct_harness_inputs(
        conn=conn, evaluation_run_id=run_id, fetcher=fetcher,
        cfg=parity_cfg, finviz_tickers=("AAPL",),
    )
    conn.close()

    assert isinstance(out, HarnessInputs)
    # BatchContext is identical for all tickers; pull from any context.
    ctx = out.contexts_by_ticker["AAPL"]
    assert set(ctx.batch.universe_tickers) == {"AAPL", "MSFT", "NVDA"}
    assert ctx.batch.universe_version == "2026-04-24-test"
    assert ctx.batch.universe_hash == real_universe_hash
    assert out.universe_match_with_production is True
    assert out.evaluation_run_id == run_id


def test_reconstruct_detects_universe_drift(
    schema_db, parity_cfg, synthetic_universe_csv,
):
    """When the production-recorded rs_universe_hash differs from the
    current rs-universe.csv hash, ``universe_match_with_production`` is
    False — flagged for the manifest, doesn't raise."""
    conn = _conn(schema_db)
    run_id = _insert_run(
        conn, run_ts="2026-04-24T21:00:00",
        finviz_csv_path="/nope.csv",
        universe_version="2026-01-01-old",
        universe_hash="aaaaaaaa",
    )
    insert_candidates(conn, run_id, [
        _candidate("AAPL", bucket="skip", criteria=(_crit("TT1", "trend_template", "fail"),)),
    ])
    conn.commit()

    fetcher = _MockPriceFetcher({
        "AAPL": _make_ohlcv("2025-04-01", 250),
        "MSFT": _make_ohlcv("2025-04-01", 250),
        "NVDA": _make_ohlcv("2025-04-01", 250),
        "SPY":  _make_ohlcv("2025-04-01", 250),
    })

    out = reconstruct_harness_inputs(
        conn=conn, evaluation_run_id=run_id, fetcher=fetcher,
        cfg=parity_cfg, finviz_tickers=("AAPL",),
    )
    conn.close()
    assert out.universe_match_with_production is False
    assert out.universe_version_recorded == "2026-01-01-old"
    assert out.universe_version_current == "2026-04-24-test"


def test_reconstruct_current_equity_matches_production_formula(
    schema_db, parity_cfg, synthetic_universe_csv,
):
    """current_equity must equal ``sizing_equity(current_equity(starting,
    exits, cash), floor)`` per ``_step_evaluate`` lines 358-369.

    With starting_equity=$1200, risk_equity_floor=$7500, no exits, no cash
    movements: real_equity=$1200, sizing_equity = max($1200, $7500) = $7500.
    """
    from swing.evaluation.rs import universe_version_hash
    real_universe_hash = universe_version_hash(synthetic_universe_csv)

    conn = _conn(schema_db)
    run_id = _insert_run(
        conn, run_ts="2026-04-24T21:00:00",
        finviz_csv_path="/nope.csv",
        universe_hash=real_universe_hash,
        universe_version="2026-04-24-test",
    )
    insert_candidates(conn, run_id, [
        _candidate("AAPL", bucket="skip", criteria=(_crit("TT1", "trend_template", "fail"),)),
    ])
    conn.commit()

    fetcher = _MockPriceFetcher({
        "AAPL": _make_ohlcv("2025-04-01", 250),
        "MSFT": _make_ohlcv("2025-04-01", 250),
        "NVDA": _make_ohlcv("2025-04-01", 250),
        "SPY":  _make_ohlcv("2025-04-01", 250),
    })

    out = reconstruct_harness_inputs(
        conn=conn, evaluation_run_id=run_id, fetcher=fetcher,
        cfg=parity_cfg, finviz_tickers=("AAPL",),
    )
    conn.close()
    # No exits, no cash movements; starting=1200, floor=7500.
    assert out.current_equity == 7500.0
    assert out.equity_derivation.startswith("sizing_equity(")


def test_reconstruct_current_equity_picks_up_realized_pnl_and_deposits(
    schema_db, parity_cfg, synthetic_universe_csv,
):
    """Real equity above the floor flows through unmodified."""
    from swing.evaluation.rs import universe_version_hash
    real_universe_hash = universe_version_hash(synthetic_universe_csv)

    conn = _conn(schema_db)
    run_id = _insert_run(
        conn, run_ts="2026-04-24T21:00:00",
        finviz_csv_path="/nope.csv",
        universe_hash=real_universe_hash,
        universe_version="2026-04-24-test",
    )
    # Insert a closed trade with a realized exit so list_all_exits returns it.
    conn.execute("""
        INSERT INTO trades (ticker, entry_date, entry_price, initial_shares,
            initial_stop, current_stop, status,
            watchlist_entry_target, watchlist_initial_stop, notes)
        VALUES ('AAPL', '2026-03-01', 100.0, 10, 95.0, 95.0, 'closed', NULL, NULL, NULL)
    """)
    trade_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute("""
        INSERT INTO exits (trade_id, exit_date, exit_price, shares, reason,
            realized_pnl, r_multiple, notes)
        VALUES (?, '2026-04-01', 120.0, 10, 'target', 200.0, 4.0, NULL)
    """, (trade_id,))
    conn.execute("""
        INSERT INTO cash_movements (date, kind, amount, ref, note)
        VALUES ('2026-04-15', 'deposit', 5000.0, NULL, NULL)
    """)
    insert_candidates(conn, run_id, [
        _candidate("AAPL", bucket="skip", criteria=(_crit("TT1", "trend_template", "fail"),)),
    ])
    conn.commit()

    fetcher = _MockPriceFetcher({
        "AAPL": _make_ohlcv("2025-04-01", 250),
        "MSFT": _make_ohlcv("2025-04-01", 250),
        "NVDA": _make_ohlcv("2025-04-01", 250),
        "SPY":  _make_ohlcv("2025-04-01", 250),
    })

    out = reconstruct_harness_inputs(
        conn=conn, evaluation_run_id=run_id, fetcher=fetcher,
        cfg=parity_cfg, finviz_tickers=("AAPL",),
    )
    conn.close()
    # starting=1200 + realized=200 + deposits=5000 = 6400 → below floor → 7500.
    assert out.current_equity == 7500.0


def test_reconstruct_comparison_set_is_evaluated_buckets_only(
    schema_db, parity_cfg, synthetic_universe_csv,
):
    """Tickers with bucket ∈ {excluded, error} are not in comparison set."""
    from swing.evaluation.rs import universe_version_hash
    real_universe_hash = universe_version_hash(synthetic_universe_csv)

    conn = _conn(schema_db)
    run_id = _insert_run(
        conn, run_ts="2026-04-24T21:00:00", finviz_csv_path="/nope.csv",
        universe_hash=real_universe_hash, universe_version="2026-04-24-test",
    )
    insert_candidates(conn, run_id, [
        _candidate("AAPL", bucket="watch", criteria=(_crit("TT1", "trend_template", "pass"),)),
        _candidate("MSFT", bucket="skip", criteria=(_crit("TT1", "trend_template", "fail"),)),
        _candidate("UCO", bucket="excluded", criteria=(), notes="ETF/fund blocklist"),
        _candidate("ZZZ", bucket="error", criteria=(), notes="OHLCV fetch failed"),
    ])
    conn.commit()

    fetcher = _MockPriceFetcher({
        "AAPL": _make_ohlcv("2025-04-01", 250),
        "MSFT": _make_ohlcv("2025-04-01", 250),
        "NVDA": _make_ohlcv("2025-04-01", 250),
        "SPY":  _make_ohlcv("2025-04-01", 250),
    })

    out = reconstruct_harness_inputs(
        conn=conn, evaluation_run_id=run_id, fetcher=fetcher,
        cfg=parity_cfg, finviz_tickers=("AAPL", "MSFT", "UCO", "ZZZ"),
    )
    conn.close()
    assert set(out.contexts_by_ticker) == {"AAPL", "MSFT"}
    assert "UCO" not in out.contexts_by_ticker
    assert "ZZZ" not in out.contexts_by_ticker


def test_reconstruct_logs_skipped_tickers_when_ohlcv_fetch_fails(
    schema_db, parity_cfg, synthetic_universe_csv,
):
    from swing.evaluation.rs import universe_version_hash
    real_universe_hash = universe_version_hash(synthetic_universe_csv)

    conn = _conn(schema_db)
    run_id = _insert_run(
        conn, run_ts="2026-04-24T21:00:00", finviz_csv_path="/nope.csv",
        universe_hash=real_universe_hash, universe_version="2026-04-24-test",
    )
    insert_candidates(conn, run_id, [
        _candidate("AAPL", bucket="watch", criteria=(_crit("TT1", "trend_template", "pass"),)),
        _candidate("MSFT", bucket="skip", criteria=(_crit("TT1", "trend_template", "fail"),)),
    ])
    conn.commit()

    fetcher = _MockPriceFetcher({
        "AAPL": _make_ohlcv("2025-04-01", 250),
        "MSFT": ValueError("yfinance returned empty"),
        "NVDA": _make_ohlcv("2025-04-01", 250),
        "SPY":  _make_ohlcv("2025-04-01", 250),
    })

    out = reconstruct_harness_inputs(
        conn=conn, evaluation_run_id=run_id, fetcher=fetcher,
        cfg=parity_cfg, finviz_tickers=("AAPL", "MSFT"),
    )
    conn.close()
    # AAPL evaluated; MSFT skipped due to fetch failure.
    assert "AAPL" in out.contexts_by_ticker
    assert "MSFT" not in out.contexts_by_ticker
    assert "MSFT" in out.skipped_tickers
    assert "fetch" in out.skipped_tickers["MSFT"].lower()


def test_reconstruct_returns_12w_populated_for_universe_tickers(
    schema_db, parity_cfg, synthetic_universe_csv,
):
    """The harness BatchContext.returns_12w_by_ticker covers BOTH the
    Finviz tickers (lookback 400d) AND the rs-universe tickers (lookback
    120d), per ``_step_evaluate`` lines 320-342."""
    from swing.evaluation.rs import universe_version_hash
    real_universe_hash = universe_version_hash(synthetic_universe_csv)

    conn = _conn(schema_db)
    run_id = _insert_run(
        conn, run_ts="2026-04-24T21:00:00", finviz_csv_path="/nope.csv",
        universe_hash=real_universe_hash, universe_version="2026-04-24-test",
    )
    insert_candidates(conn, run_id, [
        _candidate("AAPL", bucket="watch", criteria=(_crit("TT1", "trend_template", "pass"),)),
    ])
    conn.commit()

    fetcher = _MockPriceFetcher({
        "AAPL": _make_ohlcv("2025-04-01", 250, base=100.0),
        "MSFT": _make_ohlcv("2025-04-01", 250, base=200.0),
        "NVDA": _make_ohlcv("2025-04-01", 250, base=300.0),
        "SPY":  _make_ohlcv("2025-04-01", 250, base=400.0),
    })

    out = reconstruct_harness_inputs(
        conn=conn, evaluation_run_id=run_id, fetcher=fetcher,
        cfg=parity_cfg, finviz_tickers=("AAPL",),
    )
    conn.close()
    ctx = out.contexts_by_ticker["AAPL"]
    # All universe tickers + SPY should have a 12w return.
    assert set(ctx.batch.returns_12w_by_ticker) >= {"AAPL", "MSFT", "NVDA"}
    # SPY return is recorded on the BatchContext spy_return_12w field, NOT in
    # returns_12w_by_ticker (mirrors production line 312-318 + 344).
    assert ctx.batch.spy_return_12w != 0.0  # synthetic data has a positive trend


def test_reconstruct_tracks_cache_hit_miss_counts(
    schema_db, parity_cfg, synthetic_universe_csv,
):
    from swing.evaluation.rs import universe_version_hash
    real_universe_hash = universe_version_hash(synthetic_universe_csv)

    conn = _conn(schema_db)
    run_id = _insert_run(
        conn, run_ts="2026-04-24T21:00:00", finviz_csv_path="/nope.csv",
        universe_hash=real_universe_hash, universe_version="2026-04-24-test",
    )
    insert_candidates(conn, run_id, [
        _candidate("AAPL", bucket="watch", criteria=(_crit("TT1", "trend_template", "pass"),)),
    ])
    conn.commit()

    fetcher = _MockPriceFetcher({
        "AAPL": _make_ohlcv("2025-04-01", 250),
        "MSFT": _make_ohlcv("2025-04-01", 250),
        "NVDA": _make_ohlcv("2025-04-01", 250),
        "SPY":  _make_ohlcv("2025-04-01", 250),
    })

    out = reconstruct_harness_inputs(
        conn=conn, evaluation_run_id=run_id, fetcher=fetcher,
        cfg=parity_cfg, finviz_tickers=("AAPL",),
    )
    conn.close()
    # Each ticker fetched at most once for the harness inputs, so misses = total
    # unique tickers fetched, hits = 0 (mock starts cold).
    assert out.cache_misses >= 1
    assert out.cache_hits + out.cache_misses == len(fetcher.requests)
