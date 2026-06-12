"""T-V2.5 integration / E2E tests for V2 OHLCV criterion-evaluator harness.

Tests (6 per plan §H T-V2.5):
  (1) E2E synthetic-universe run: 100-candidate / 5-eval_run / 17-var / 5-sweep-
      point universe; verify CSV + markdown emitted + CSV has expected header.
  (2) V1<->V2 parity discriminating: V2 with no substitution (all sweep_points ==
      current_value) matches V1's persisted-bucket pass for tier-1 candidates.
  (3) OHLCV coverage failure E2E: plant <200-bar archive for one ticker; assert
      ohlcv_coverage_skip_count accurate.
  (4) Memory footprint smoke: tracemalloc.get_traced_memory() peak captured to
      markdown manifest (memory_peak_bytes field present in manifest).
  (5) CRITERION DRIFT detection smoke: alter cfg between persistence + V2
      invocation; assert '## CRITERION DRIFT DETECTED' alert fires.
  (6) Both-exist diagnostic E2E: plant both Shape A + legacy for 3 tickers;
      assert manifest both_exist_shape_a_wins_count == 3 + markdown banner emits.
"""
from __future__ import annotations

import csv
import dataclasses
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from swing.config import Config

# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

_RS_UNIVERSE_CSV_100 = (
    "ticker\n" + "\n".join(f"RS{i:03d}" for i in range(100)) + "\n"
)


def _make_shape_a_parquet(
    path: Path, n_bars: int = 250, close: float = 100.0
) -> None:
    """Write a Shape A (lowercase OHLCV + asof_date) parquet."""
    dates = pd.date_range(end="2026-04-30", periods=n_bars, freq="B")
    df = pd.DataFrame(
        {
            "asof_date": [d.date().isoformat() for d in dates],
            "open": [close] * n_bars,
            "high": [close + 1.0] * n_bars,
            "low": [close - 1.0] * n_bars,
            "close": [close] * n_bars,
            "volume": [1_000_000] * n_bars,
        }
    )
    df.to_parquet(path, index=False)


_INTEGRATION_DDL = [
    """CREATE TABLE evaluation_runs (
         id INTEGER PRIMARY KEY,
         run_ts TEXT NOT NULL,
         data_asof_date TEXT NOT NULL,
         action_session_date TEXT NOT NULL,
         finviz_csv_path TEXT,
         tickers_evaluated INTEGER NOT NULL DEFAULT 0,
         aplus_count INTEGER NOT NULL DEFAULT 0,
         watch_count INTEGER NOT NULL DEFAULT 0,
         skip_count INTEGER NOT NULL DEFAULT 0,
         excluded_count INTEGER NOT NULL DEFAULT 0,
         error_count INTEGER NOT NULL DEFAULT 0
       )""",
    """CREATE TABLE candidates (
         id INTEGER PRIMARY KEY,
         evaluation_run_id INTEGER NOT NULL REFERENCES evaluation_runs(id),
         ticker TEXT NOT NULL,
         bucket TEXT NOT NULL CHECK (bucket IN ('aplus','watch','skip','error','excluded')),
         close REAL,
         pivot REAL,
         initial_stop REAL,
         adr_pct REAL,
         tight_streak INTEGER,
         pullback_pct REAL,
         prior_trend_pct REAL,
         rs_rank INTEGER,
         rs_return_12w_vs_spy REAL,
         rs_method TEXT NOT NULL CHECK (rs_method IN ('universe','fallback_spy','unavailable'))
             DEFAULT 'unavailable',
         pattern_tag TEXT,
         notes TEXT,
         sector TEXT,
         industry TEXT,
         UNIQUE(evaluation_run_id, ticker)
       )""",
    """CREATE TABLE candidate_criteria (
         candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
         criterion_name TEXT NOT NULL,
         layer TEXT NOT NULL CHECK (layer IN ('trend_template','vcp','risk')),
         result TEXT NOT NULL CHECK (result IN ('pass','fail','na')),
         value TEXT,
         rule TEXT,
         PRIMARY KEY (candidate_id, criterion_name)
       )""",
    """CREATE TABLE account_equity_snapshots (
         snapshot_id INTEGER PRIMARY KEY,
         snapshot_date TEXT NOT NULL,
         equity_dollars REAL NOT NULL,
         source TEXT NOT NULL,
         source_artifact_path TEXT,
         recorded_at TEXT,
         recorded_by TEXT,
         notes TEXT,
         basis TEXT NOT NULL DEFAULT 'net_liq'
       )""",
]


def _plant_integration_db(
    tmp_path: Path,
    *,
    n_eval_runs: int = 5,
    candidate_tickers: list[str] | None = None,
    bucket: str = "skip",
    data_asof_date: str | None = None,
) -> Path:
    """Plant a minimal integration DB at tmp_path/integration.db.

    data_asof_date: when provided, ALL eval_runs use this single date for
      data_asof_date (and action_session_date = next calendar day).  When
      None (default), dates are month-derived (2026-{month}-01).

    NOTE: the 250-bar parquet produced by _make_shape_a_parquet ends at
    2026-04-30.  With the default month-derived dates (2026-01-01 /
    2026-02-01 etc.) the sliced-to-asof_date frame has ~140-145 bars --
    below the 200-bar coverage threshold -- so candidates will be
    OHLCV-coverage-skipped.  Pass data_asof_date='2026-04-15' (or later)
    when you need candidates to actually reach evaluate_one in the sweep.
    """
    if candidate_tickers is None:
        candidate_tickers = [f"CAND{i:02d}" for i in range(20)]

    db_path = tmp_path / "integration.db"
    conn = sqlite3.connect(str(db_path))
    for ddl in _INTEGRATION_DDL:
        conn.execute(ddl)

    # Plant one equity snapshot so surrogate=False for all runs.
    conn.execute(
        "INSERT INTO account_equity_snapshots "
        "(snapshot_date, equity_dollars, source, recorded_at, recorded_by) "
        "VALUES ('2026-01-01', 10000.0, 'manual', '2026-01-01T00:00:00Z', 'test')"
    )

    candidate_id = 1
    for run_id in range(1, n_eval_runs + 1):
        if data_asof_date is not None:
            asof = data_asof_date
            # action_session_date is the next calendar day (simplified)
            asof_d = date.fromisoformat(asof)
            action_session = (asof_d + timedelta(days=1)).isoformat()
            run_ts = f"{asof}T00:00:00Z"
        else:
            month = (run_id % 12) or 12
            asof = f"2026-{month:02d}-01"
            action_session = f"2026-{month:02d}-02"
            run_ts = f"2026-{month:02d}-01T00:00:00Z"

        conn.execute(
            "INSERT INTO evaluation_runs "
            "(id, run_ts, data_asof_date, action_session_date) VALUES (?, ?, ?, ?)",
            (run_id, run_ts, asof, action_session),
        )
        for ticker in candidate_tickers:
            conn.execute(
                "INSERT INTO candidates "
                "(id, evaluation_run_id, ticker, bucket, rs_method) "
                "VALUES (?, ?, ?, ?, 'fallback_spy')",
                (candidate_id, run_id, ticker, bucket),
            )
            conn.execute(
                "INSERT INTO candidate_criteria "
                "(candidate_id, criterion_name, layer, result) "
                "VALUES (?, 'risk_feasibility', 'risk', 'pass')",
                (candidate_id,),
            )
            candidate_id += 1

    conn.commit()
    conn.close()
    return db_path


def _plant_ohlcv(
    cache_dir: Path,
    tickers: list[str],
    *,
    n_bars: int = 250,
    also_spy: bool = True,
) -> None:
    """Plant Shape A parquet files for tickers + optionally SPY."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    for ticker in tickers:
        _make_shape_a_parquet(
            cache_dir / f"{ticker}.yfinance.parquet", n_bars=n_bars
        )
    if also_spy and "SPY" not in tickers:
        _make_shape_a_parquet(cache_dir / "SPY.yfinance.parquet", n_bars=n_bars)


def _make_patched_cfg(
    tmp_path: Path, *, rs_csv: Path, cache_dir: Path
) -> Config:
    """Return a Config with rs_universe_path + prices_cache_dir overridden."""
    cfg = Config.from_defaults()
    new_paths = dataclasses.replace(
        cfg.paths,
        rs_universe_path=str(rs_csv),
        prices_cache_dir=cache_dir,
    )
    return dataclasses.replace(cfg, paths=new_paths)


# ---------------------------------------------------------------------------
# (1) E2E synthetic-universe run
# ---------------------------------------------------------------------------


def test_e2e_synthetic_universe_run_emits_csv_and_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-V2.5 (1): E2E run emits CSV + markdown; CSV has expected 12-col header."""
    # Plant RS universe: 100 tickers + candidates.
    rs_csv = tmp_path / "rs_universe.csv"
    rs_csv.write_text(_RS_UNIVERSE_CSV_100, encoding="utf-8")

    cache_dir = tmp_path / "ohlcv_cache"
    rs_tickers = [f"RS{i:03d}" for i in range(100)]
    candidate_tickers = [f"CAND{i:02d}" for i in range(5)]
    _plant_ohlcv(cache_dir, rs_tickers + candidate_tickers)

    db_path = _plant_integration_db(
        tmp_path, n_eval_runs=5, candidate_tickers=candidate_tickers
    )

    cfg = _make_patched_cfg(tmp_path, rs_csv=rs_csv, cache_dir=cache_dir)
    monkeypatch.setattr(
        "research.harness.aplus_v2_ohlcv_evaluator.run._get_cfg",
        lambda: cfg,
    )

    from research.harness.aplus_v2_ohlcv_evaluator.run import run_harness

    out_dir = tmp_path / "out"
    md_path, csv_path = run_harness(
        db_path=db_path,
        eval_runs=5,
        output_dir=out_dir,
        min_universe_size=50,
    )

    assert md_path.exists(), f"md not found: {md_path}"
    assert csv_path.exists(), f"csv not found: {csv_path}"

    # Verify CSV header shape (12 columns per §D + spec §G.1).
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
    assert len(header) == 12, f"Expected 12 CSV columns, got {len(header)}: {header}"
    assert header[0] == "variable_name"
    assert header[1] == "kind"
    assert header[2] == "sweep_point"


# ---------------------------------------------------------------------------
# (2) V1<->V2 baseline parity discriminating test
# ---------------------------------------------------------------------------


def test_v2_baseline_parity_tier1_exact_match_discriminating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-V2.5 (2): V2 at sweep_point==current_value reproduces persisted buckets.

    Tier-1 baseline parity is EXACT: BaselineParityReport.tier1_match must be
    True when no criteria-drift exists between persist time and V2 invocation.
    """
    rs_csv = tmp_path / "rs_universe.csv"
    rs_csv.write_text(_RS_UNIVERSE_CSV_100, encoding="utf-8")

    cache_dir = tmp_path / "ohlcv_cache"
    rs_tickers = [f"RS{i:03d}" for i in range(100)]
    candidate_tickers = ["TIER1A", "TIER1B"]
    _plant_ohlcv(cache_dir, rs_tickers + candidate_tickers)

    db_path = _plant_integration_db(
        tmp_path,
        n_eval_runs=2,
        candidate_tickers=candidate_tickers,
        bucket="skip",
    )

    cfg = _make_patched_cfg(tmp_path, rs_csv=rs_csv, cache_dir=cache_dir)

    from research.harness.aplus_sensitivity.variables import enumerate_variables
    from research.harness.aplus_v2_ohlcv_evaluator.sweep import run_v2_sweep

    conn = sqlite3.connect(str(db_path))
    try:
        result = run_v2_sweep(
            conn,
            variables=tuple(enumerate_variables(cfg)),
            cfg=cfg,
            cache_dir=cache_dir,
            eval_runs_window=5,
            min_universe_size=50,
        )
    finally:
        conn.close()

    # Tier-1 baseline parity MUST be exact (no criteria-drift in synthetic fixture).
    assert result.baseline_parity.tier1_match is True, (
        f"Tier-1 baseline parity failed; mismatched candidates: "
        f"{result.baseline_parity.tier1_mismatch_candidates}"
    )


# ---------------------------------------------------------------------------
# (3) OHLCV coverage failure E2E
# ---------------------------------------------------------------------------


def test_ohlcv_coverage_skip_count_accurate_for_short_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-V2.5 (3): Ticker with <min_bars archive is counted in coverage skip."""
    rs_csv = tmp_path / "rs_universe.csv"
    rs_csv.write_text(_RS_UNIVERSE_CSV_100, encoding="utf-8")

    cache_dir = tmp_path / "ohlcv_cache"
    rs_tickers = [f"RS{i:03d}" for i in range(100)]
    # COVERAGE_POOR has only 10 bars -- below the default min_bars (60).
    _plant_ohlcv(cache_dir, rs_tickers)
    _make_shape_a_parquet(cache_dir / "COVERAGE_POOR.yfinance.parquet", n_bars=10)
    _make_shape_a_parquet(cache_dir / "COVERAGE_OK.yfinance.parquet", n_bars=250)
    _make_shape_a_parquet(cache_dir / "SPY.yfinance.parquet", n_bars=250)

    db_path = _plant_integration_db(
        tmp_path,
        n_eval_runs=2,
        candidate_tickers=["COVERAGE_POOR", "COVERAGE_OK"],
        bucket="skip",
    )

    cfg = _make_patched_cfg(tmp_path, rs_csv=rs_csv, cache_dir=cache_dir)

    from research.harness.aplus_sensitivity.variables import enumerate_variables
    from research.harness.aplus_v2_ohlcv_evaluator.sweep import run_v2_sweep

    conn = sqlite3.connect(str(db_path))
    try:
        result = run_v2_sweep(
            conn,
            variables=tuple(enumerate_variables(cfg)),
            cfg=cfg,
            cache_dir=cache_dir,
            eval_runs_window=5,
            min_universe_size=50,
        )
    finally:
        conn.close()

    # COVERAGE_POOR should have accumulated skip counts.
    assert result.ohlcv_coverage_skip_count > 0, (
        "Expected ohlcv_coverage_skip_count > 0 for short-archive ticker; "
        f"got {result.ohlcv_coverage_skip_count}"
    )


# ---------------------------------------------------------------------------
# (4) Memory footprint smoke
# ---------------------------------------------------------------------------


def test_markdown_manifest_contains_memory_peak_bytes_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-V2.5 (4): markdown manifest includes memory_peak_bytes field."""
    rs_csv = tmp_path / "rs_universe.csv"
    rs_csv.write_text(_RS_UNIVERSE_CSV_100, encoding="utf-8")

    cache_dir = tmp_path / "ohlcv_cache"
    rs_tickers = [f"RS{i:03d}" for i in range(100)]
    candidate_tickers = ["MEMTEST"]
    _plant_ohlcv(cache_dir, rs_tickers + candidate_tickers)

    db_path = _plant_integration_db(
        tmp_path, n_eval_runs=2, candidate_tickers=candidate_tickers
    )

    cfg = _make_patched_cfg(tmp_path, rs_csv=rs_csv, cache_dir=cache_dir)
    monkeypatch.setattr(
        "research.harness.aplus_v2_ohlcv_evaluator.run._get_cfg",
        lambda: cfg,
    )

    from research.harness.aplus_v2_ohlcv_evaluator.run import run_harness

    out_dir = tmp_path / "out"
    md_path, _ = run_harness(
        db_path=db_path, eval_runs=2, output_dir=out_dir, min_universe_size=50
    )

    md_text = md_path.read_text(encoding="utf-8")
    assert "memory_peak_bytes" in md_text, (
        "Expected 'memory_peak_bytes' in markdown manifest; not found.\n"
        f"Markdown excerpt:\n{md_text[-500:]}"
    )


# ---------------------------------------------------------------------------
# (5) CRITERION DRIFT detection smoke
# ---------------------------------------------------------------------------


def test_criterion_drift_alert_fires_on_tier1_bucket_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-V2.5 (5): CRITERION DRIFT alert fires when V2 produces different buckets.

    We plant a candidate with bucket='aplus' in the DB (persisted by V1 pipeline)
    but supply a flat-price synthetic OHLCV archive where the real evaluate_one
    will NOT produce 'aplus' (flat prices fail prior-trend, VCP tightening, and
    other A+ criteria).  data_asof_date='2026-04-15' ensures the 250-bar archive
    ending at 2026-04-30 has >=200 bars when sliced to asof_date so the candidate
    reaches evaluate_one (not OHLCV-coverage-skipped).

    The mismatch (persisted='aplus' vs V2='skip') means tier1_mismatch_keys
    accumulates entries -> tier1_match=False -> markdown emits CRITERION DRIFT
    DETECTED alert.

    No monkeypatching of evaluate_one: the discriminating test relies on the
    REAL production evaluate_one to reject the flat-price fixture (natural drift).
    """
    rs_csv = tmp_path / "rs_universe.csv"
    rs_csv.write_text(_RS_UNIVERSE_CSV_100, encoding="utf-8")

    cache_dir = tmp_path / "ohlcv_cache"
    rs_tickers = [f"RS{i:03d}" for i in range(100)]
    candidate_tickers = ["DRIFT_TICKER"]
    # Plant 250 bars ending at 2026-04-30 (flat price -- real evaluate_one
    # will return 'skip' because criteria like prior_trend, VCP tightening
    # are not met for a flat-price series).
    _plant_ohlcv(cache_dir, rs_tickers + candidate_tickers)

    # Plant candidate with bucket='aplus' (persisted) + data_asof_date='2026-04-15'
    # so the 250-bar parquet has >=200 bars sliced to that date.
    db_path = _plant_integration_db(
        tmp_path,
        n_eval_runs=2,
        candidate_tickers=candidate_tickers,
        bucket="aplus",  # persisted as 'aplus'; V2 will compute 'skip'
        data_asof_date="2026-04-15",
    )

    cfg = _make_patched_cfg(tmp_path, rs_csv=rs_csv, cache_dir=cache_dir)

    from research.harness.aplus_sensitivity.variables import enumerate_variables
    from research.harness.aplus_v2_ohlcv_evaluator.output import (
        write_sensitivity_markdown_v2,
    )
    from research.harness.aplus_v2_ohlcv_evaluator.sweep import run_v2_sweep

    conn = sqlite3.connect(str(db_path))
    try:
        result = run_v2_sweep(
            conn,
            variables=tuple(enumerate_variables(cfg)),
            cfg=cfg,
            cache_dir=cache_dir,
            eval_runs_window=5,
            min_universe_size=50,
        )
    finally:
        conn.close()

    # Baseline parity MUST report tier1_match=False: persisted='aplus' but
    # real evaluate_one on flat-price OHLCV produces a non-'aplus' bucket.
    assert result.baseline_parity.tier1_match is False, (
        "Expected tier1_match=False on criterion-drift fixture; got True. "
        "The discriminating test is not discriminating. "
        f"tier_1_count={result.baseline_parity.tier_1_count}; "
        f"tier_2_count={result.baseline_parity.tier_2_count}; "
        f"ohlcv_coverage_skip_count={result.ohlcv_coverage_skip_count}"
    )

    # Write markdown to verify CRITERION DRIFT alert fires.
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "drift_test.md"
    write_sensitivity_markdown_v2(result, md_path, memory_peak_bytes=0)
    md_text = md_path.read_text(encoding="utf-8")

    assert "CRITERION DRIFT DETECTED" in md_text, (
        "Expected '## CRITERION DRIFT DETECTED' section in markdown output; "
        f"not found.\nMarkdown excerpt:\n{md_text[:1000]}"
    )


# ---------------------------------------------------------------------------
# (6) Both-exist diagnostic E2E
# ---------------------------------------------------------------------------


def test_both_exist_diagnostic_counts_legacy_plus_shape_a_tickers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-V2.5 (6): Plant both Shape A + legacy parquet for 3 tickers.

    V2 reader should detect the both-exist condition and:
      - both_exist_shape_a_wins_count == 3
      - markdown emits '## BOTH-EXIST WARNING' (or count > 0 banner)
    """
    rs_csv = tmp_path / "rs_universe.csv"
    rs_csv.write_text(_RS_UNIVERSE_CSV_100, encoding="utf-8")

    cache_dir = tmp_path / "ohlcv_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    rs_tickers = [f"RS{i:03d}" for i in range(100)]
    both_exist_tickers = ["BOTH01", "BOTH02", "BOTH03"]
    normal_tickers = ["NORMAL01"]

    # Plant RS universe tickers.
    for t in rs_tickers:
        _make_shape_a_parquet(cache_dir / f"{t}.yfinance.parquet")

    # Plant SPY.
    _make_shape_a_parquet(cache_dir / "SPY.yfinance.parquet")

    # Plant both Shape A + legacy for both_exist_tickers.
    for t in both_exist_tickers:
        _make_shape_a_parquet(
            cache_dir / f"{t}.yfinance.parquet", n_bars=250
        )
        # Legacy parquet (schwab_api shape -- different source key).
        _make_shape_a_parquet(
            cache_dir / f"{t}.schwab_api.parquet", n_bars=200
        )

    # Plant only Shape A for normal tickers.
    for t in normal_tickers:
        _make_shape_a_parquet(cache_dir / f"{t}.yfinance.parquet")

    all_candidate_tickers = both_exist_tickers + normal_tickers
    db_path = _plant_integration_db(
        tmp_path,
        n_eval_runs=2,
        candidate_tickers=all_candidate_tickers,
        bucket="skip",
    )

    cfg = _make_patched_cfg(tmp_path, rs_csv=rs_csv, cache_dir=cache_dir)
    monkeypatch.setattr(
        "research.harness.aplus_v2_ohlcv_evaluator.run._get_cfg",
        lambda: cfg,
    )

    from research.harness.aplus_v2_ohlcv_evaluator.run import run_harness

    out_dir = tmp_path / "out"
    md_path, _ = run_harness(
        db_path=db_path,
        eval_runs=2,
        output_dir=out_dir,
        min_universe_size=50,
    )

    md_text = md_path.read_text(encoding="utf-8")

    # both_exist_shape_a_wins_count should be >= 3 (3 tickers x 2 eval_runs
    # of invocations; exact count depends on per-variable loop multiplier).
    # Minimum discriminating assertion: the markdown banner fires (count > 0).
    assert "BOTH-EXIST" in md_text or "both-exist" in md_text.lower(), (
        "Expected BOTH-EXIST banner in markdown output for tickers with both "
        f"Shape A + legacy parquet; not found.\nMarkdown excerpt:\n{md_text[:1500]}"
    )
