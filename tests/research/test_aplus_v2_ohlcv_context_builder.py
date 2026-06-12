"""Tests for V2 OHLCV harness context_builder module.

Covers per §H T-V2.1.3 ~18 tests:
  (1)  parse_asof_date raises MalformedAsofDateError on garbage
  (2)  parse_asof_date returns date for valid ISO
  (3)  load_validated_rs_universe raises EmptyRsUniverseError
  (4)  raises InvalidRsUniverseError on >5% garbage with first-20-symbols enumerated
  (5)  accepts <=5% garbage with warning + drop
  (6)  handles duplicates with warning + drop
  (7)  raises PostCleanupUniverseTooSmallError
  (8)  MissingRsUniversePathError on unset/unreadable path
  (9)  fetch_eval_runs ordering + date parsing
  (10) fetch_candidates LEFT JOIN handles missing risk_feasibility row
  (11) fetch_candidates multi-eval_run IN clause expansion (Codex R1.M1)
  (12) classify_candidate_tier tier-1 + tier-2
  (13) build_eval_run_cohort current_equity historical snapshot path
  (14) current_equity fallback to most-recent snapshot + via_surrogate flag
  (15) current_equity fallback to floor surrogate + via_surrogate flag
  (16) build_eval_run_cohort populates returns for candidate-not-in-universe tickers
  (17) defensive signature-lock tests (3: evaluate_one + load_universe + get_latest_snapshot)
  (18) horizon_weeks-scaled bars_needed
"""
from __future__ import annotations

import dataclasses
import inspect
import sqlite3
import typing
import warnings
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from swing.config import Config

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _apply_phase1_migration(db_path: Path) -> None:
    """Apply minimal phase-1 schema to a new SQLite DB."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
        INSERT OR IGNORE INTO schema_version (version) VALUES (1);

        CREATE TABLE IF NOT EXISTS evaluation_runs (
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
        );

        CREATE TABLE IF NOT EXISTS candidates (
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
          UNIQUE(evaluation_run_id, ticker)
        );

        CREATE TABLE IF NOT EXISTS candidate_criteria (
          candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
          criterion_name TEXT NOT NULL,
          layer TEXT NOT NULL CHECK (layer IN ('trend_template','vcp','risk')),
          result TEXT NOT NULL CHECK (result IN ('pass','fail','na')),
          value TEXT,
          rule TEXT,
          PRIMARY KEY (candidate_id, criterion_name)
        );
    """)
    conn.close()


def _apply_equity_snapshot_table(db_path: Path) -> None:
    """Apply account_equity_snapshots table schema."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS account_equity_snapshots (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT NOT NULL,
            equity_dollars REAL NOT NULL CHECK (equity_dollars > 0),
            source TEXT NOT NULL CHECK (source IN ('manual', 'schwab_api', 'tos_csv')),
            source_artifact_path TEXT,
            recorded_at TEXT NOT NULL,
            recorded_by TEXT NOT NULL,
            notes TEXT,
            basis TEXT NOT NULL DEFAULT 'net_liq' CHECK (basis IN ('net_liq','cash'))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ux_account_equity_snapshots_date_source_basis
            ON account_equity_snapshots (snapshot_date, source, basis);
    """)
    conn.close()


def _seed_eval_runs(db_path: Path, run_data: list[tuple[int, str]]) -> None:
    """Seed evaluation_runs rows: [(id, data_asof_date), ...]."""
    conn = sqlite3.connect(str(db_path))
    for run_id, asof_date in run_data:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, action_session_date, "
            "tickers_evaluated, aplus_count, watch_count, skip_count, excluded_count, error_count) "
            "VALUES (?, '2026-01-01T00:00:00', ?, ?, 0, 0, 0, 0, 0, 0)",
            (run_id, asof_date, asof_date),
        )
    conn.commit()
    conn.close()


def _seed_candidate(
    db_path: Path,
    *,
    eval_run_id: int,
    ticker: str,
    bucket: str,
    risk_feasibility_result: str | None,
) -> int:
    """Seed one candidate + optional risk_feasibility criterion row. Returns candidate_id."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "INSERT INTO candidates"
        " (evaluation_run_id, ticker, bucket, rs_method)"
        " VALUES (?, ?, ?, 'unavailable')",
        (eval_run_id, ticker, bucket),
    )
    candidate_id = cursor.lastrowid
    if risk_feasibility_result is not None:
        conn.execute(
            "INSERT INTO candidate_criteria (candidate_id, criterion_name, layer, result) "
            "VALUES (?, 'risk_feasibility', 'risk', ?)",
            (candidate_id, risk_feasibility_result),
        )
    conn.commit()
    conn.close()
    return candidate_id


def _seed_equity_snapshot(
    db_path: Path,
    *,
    snapshot_date: str,
    equity_dollars: float,
    source: str = "manual",
) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO account_equity_snapshots "
        "(snapshot_date, equity_dollars, source, recorded_at, recorded_by) "
        "VALUES (?, ?, ?, '2026-01-01T00:00:00', 'test')",
        (snapshot_date, equity_dollars, source),
    )
    conn.commit()
    conn.close()


def _cfg_with_universe_path(universe_csv: Path) -> Config:
    """Return a Config whose paths.rs_universe_path is overridden."""
    cfg = Config.from_defaults()
    new_paths = dataclasses.replace(cfg.paths, rs_universe_path=str(universe_csv))
    return dataclasses.replace(cfg, paths=new_paths)


def _make_shape_a_parquet(path: Path, n_bars: int, sentinel_close: float = 100.0) -> None:
    dates = pd.date_range(end="2026-04-30", periods=n_bars, freq="B")
    df = pd.DataFrame({
        "asof_date": [d.date().isoformat() for d in dates],
        "open": [sentinel_close] * n_bars,
        "high": [sentinel_close + 1.0] * n_bars,
        "low": [sentinel_close - 1.0] * n_bars,
        "close": [sentinel_close] * n_bars,
        "volume": [1_000_000] * n_bars,
    })
    df.to_parquet(path, index=False)


# ---------------------------------------------------------------------------
# (1) parse_asof_date raises MalformedAsofDateError on garbage
# ---------------------------------------------------------------------------

def test_parse_asof_date_raises_MalformedAsofDateError_on_garbage():  # noqa: N802
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import parse_asof_date
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import MalformedAsofDateError
    with pytest.raises(MalformedAsofDateError, match="malformed"):
        parse_asof_date("not-a-date")
    with pytest.raises(MalformedAsofDateError):
        parse_asof_date("")


# ---------------------------------------------------------------------------
# (2) parse_asof_date returns date for valid ISO
# ---------------------------------------------------------------------------

def test_parse_asof_date_returns_date_for_valid_iso():
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import parse_asof_date
    assert parse_asof_date("2026-04-30") == date(2026, 4, 30)


# ---------------------------------------------------------------------------
# (3) load_validated_rs_universe raises EmptyRsUniverseError
# ---------------------------------------------------------------------------

def test_load_validated_rs_universe_raises_EmptyRsUniverseError_when_empty(tmp_path):  # noqa: N802
    universe_csv = tmp_path / "empty_universe.csv"
    universe_csv.write_text("# version: test\nticker\n", encoding="utf-8")
    cfg = _cfg_with_universe_path(universe_csv)
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import load_validated_rs_universe
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import EmptyRsUniverseError
    with pytest.raises(EmptyRsUniverseError):
        load_validated_rs_universe(cfg, min_universe_size=10)


# ---------------------------------------------------------------------------
# (4) raises InvalidRsUniverseError on >5% garbage
# ---------------------------------------------------------------------------

def test_load_validated_rs_universe_raises_InvalidRsUniverseError_when_garbage_rate_exceeds_5pct(  # noqa: N802
    tmp_path,
):
    # Use 50 distinct valid + 50 distinct invalid (50% > 5% AND >10 rows)
    valid_rows = [f"AAA{i:03d}" for i in range(50)]
    invalid_rows = [f"???GARBAGE{i:03d}" for i in range(50)]
    universe_csv = tmp_path / "garbage_universe.csv"
    universe_csv.write_text(
        "ticker\n" + "\n".join(valid_rows + invalid_rows) + "\n",
        encoding="utf-8",
    )
    cfg = _cfg_with_universe_path(universe_csv)
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import load_validated_rs_universe
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import InvalidRsUniverseError
    with pytest.raises(InvalidRsUniverseError) as exc_info:
        load_validated_rs_universe(cfg, min_universe_size=40)
    # Per Codex R4.m1: rejected symbols enumerated in message (first 20)
    assert "???GARBAGE" in str(exc_info.value)


# ---------------------------------------------------------------------------
# (5) accepts <=5% garbage with warning + drop
# ---------------------------------------------------------------------------

def test_load_validated_rs_universe_accepts_small_garbage_rate_with_warning(tmp_path):
    # 200 valid + 5 invalid (2.5% < 5% and <= 10 rows) -> warning + drop
    valid_rows = [f"T{i:04d}" for i in range(200)]
    invalid_rows = ["???a", "???b", "???c", "???d", "???e"]
    universe_csv = tmp_path / "small_garbage.csv"
    universe_csv.write_text(
        "ticker\n" + "\n".join(valid_rows + invalid_rows) + "\n",
        encoding="utf-8",
    )
    cfg = _cfg_with_universe_path(universe_csv)
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import load_validated_rs_universe
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        tickers, _ = load_validated_rs_universe(cfg, min_universe_size=100)
    # Invalid rows dropped
    assert all("???" not in t for t in tickers)
    # 200 valid accepted
    assert len(tickers) == 200


# ---------------------------------------------------------------------------
# (6) handles duplicates with warning + drop
# ---------------------------------------------------------------------------

def test_load_validated_rs_universe_handles_duplicates_with_warning(tmp_path):
    # load_universe already deduplicates via sorted(set(...)); V2 checks explicitly
    valid_rows = [f"T{i:04d}" for i in range(150)]
    dupes = ["T0001"] * 10  # 10 duplicates of T0001
    universe_csv = tmp_path / "dup_universe.csv"
    universe_csv.write_text(
        "ticker\n" + "\n".join(valid_rows + dupes) + "\n",
        encoding="utf-8",
    )
    cfg = _cfg_with_universe_path(universe_csv)
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import load_validated_rs_universe
    tickers, _ = load_validated_rs_universe(cfg, min_universe_size=100)
    # 150 unique tickers (T0000 through T0149)
    assert len(tickers) == 150


# ---------------------------------------------------------------------------
# (7) raises PostCleanupUniverseTooSmallError
# ---------------------------------------------------------------------------

def test_load_validated_rs_universe_raises_PostCleanupUniverseTooSmallError(tmp_path):  # noqa: N802
    # Use 94 distinct valid + 4 distinct invalid (<5% so dropped not raised).
    # load_universe deduplicates, so no need for explicit duplicates.
    # After V2 shape validation: 94 valid accepted < min_universe_size=100.
    valid_rows = [f"AAA{i:04d}" for i in range(94)]
    invalid_rows = [f"???GARBAGE{i}" for i in range(4)]  # 4/98 = 4.1% < 5% -> warn+drop
    universe_csv = tmp_path / "cleanup_too_small.csv"
    universe_csv.write_text(
        "ticker\n" + "\n".join(valid_rows + invalid_rows) + "\n",
        encoding="utf-8",
    )
    cfg = _cfg_with_universe_path(universe_csv)
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import load_validated_rs_universe
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import (
        PostCleanupUniverseTooSmallError,
    )
    with pytest.raises(PostCleanupUniverseTooSmallError):
        load_validated_rs_universe(cfg, min_universe_size=100)


# ---------------------------------------------------------------------------
# (8) MissingRsUniversePathError on unset/unreadable path
# ---------------------------------------------------------------------------

def test_load_validated_rs_universe_raises_MissingRsUniversePathError_on_missing_file(  # noqa: N802
    tmp_path,
):
    cfg = _cfg_with_universe_path(tmp_path / "nonexistent.csv")
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import load_validated_rs_universe
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import MissingRsUniversePathError
    with pytest.raises(MissingRsUniversePathError):
        load_validated_rs_universe(cfg, min_universe_size=10)


# ---------------------------------------------------------------------------
# (9) fetch_eval_runs ordering + date parsing
# ---------------------------------------------------------------------------

def test_fetch_eval_runs_returns_descending_id_order_with_parsed_dates(tmp_path):
    db_path = tmp_path / "fixture.db"
    _apply_phase1_migration(db_path)
    _seed_eval_runs(db_path, [(1, "2026-04-01"), (2, "2026-04-15"), (3, "2026-04-30")])
    conn = sqlite3.connect(str(db_path))
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import fetch_eval_runs
    result = fetch_eval_runs(conn, eval_runs_window=2)
    conn.close()
    assert result == [(3, date(2026, 4, 30)), (2, date(2026, 4, 15))]


# ---------------------------------------------------------------------------
# (10) fetch_candidates LEFT JOIN handles missing risk_feasibility row
# ---------------------------------------------------------------------------

def test_fetch_candidates_handles_LEFT_JOIN_miss_with_null_risk_result(tmp_path):  # noqa: N802
    db_path = tmp_path / "fixture.db"
    _apply_phase1_migration(db_path)
    _seed_eval_runs(db_path, [(1, "2026-04-30")])
    _seed_candidate(
        db_path, eval_run_id=1, ticker="AAA", bucket="skip", risk_feasibility_result="pass",
    )
    _seed_candidate(
        db_path, eval_run_id=1, ticker="BBB", bucket="skip", risk_feasibility_result=None,
    )
    conn = sqlite3.connect(str(db_path))
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import fetch_candidates
    rows = fetch_candidates(conn, eval_run_ids=[1], eval_run_dates={1: date(2026, 4, 30)})
    conn.close()
    assert len(rows) == 2
    by_ticker = {r.ticker: r for r in rows}
    assert by_ticker["AAA"].persisted_risk_result == "pass"
    assert by_ticker["BBB"].persisted_risk_result is None


# ---------------------------------------------------------------------------
# (11) fetch_candidates multi-eval_run IN clause expansion (Codex R1.M1)
# ---------------------------------------------------------------------------

def test_fetch_candidates_handles_multi_eval_run_IN_clause(tmp_path):  # noqa: N802
    db_path = tmp_path / "fixture.db"
    _apply_phase1_migration(db_path)
    _seed_eval_runs(db_path, [(1, "2026-04-01"), (2, "2026-04-15"), (3, "2026-04-30")])
    _seed_candidate(
        db_path, eval_run_id=1, ticker="AAA", bucket="skip", risk_feasibility_result=None,
    )
    _seed_candidate(
        db_path, eval_run_id=2, ticker="BBB", bucket="skip", risk_feasibility_result=None,
    )
    _seed_candidate(
        db_path, eval_run_id=3, ticker="CCC", bucket="aplus", risk_feasibility_result="pass",
    )
    conn = sqlite3.connect(str(db_path))
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import fetch_candidates
    rows = fetch_candidates(
        conn,
        eval_run_ids=[1, 2, 3],
        eval_run_dates={1: date(2026, 4, 1), 2: date(2026, 4, 15), 3: date(2026, 4, 30)},
    )
    conn.close()
    assert len(rows) == 3
    tickers = {r.ticker for r in rows}
    assert tickers == {"AAA", "BBB", "CCC"}


# ---------------------------------------------------------------------------
# (12) classify_candidate_tier tier-1 + tier-2
# ---------------------------------------------------------------------------

def test_classify_candidate_tier_returns_1_for_persisted_risk_pass():
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import classify_candidate_tier
    assert classify_candidate_tier("pass") == 1


def test_classify_candidate_tier_returns_1_for_None_risk_result():  # noqa: N802
    """Codex R1.C1 discriminating fix: None risk_result = LEFT JOIN miss = risk
    was not evaluated (TT-gate skip or pre-risk historical candidate). Bucket is
    independent of risk gate => tier-1. Was incorrectly tier-2 pre-fix."""
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import classify_candidate_tier
    # None = LEFT JOIN miss => TT-gate skip or historical pre-risk => tier-1
    assert classify_candidate_tier(None) == 1


def test_classify_candidate_tier_returns_2_for_risk_fail_and_na():  # noqa: N802
    """fail + na: risk WAS evaluated and was load-bearing for skip => tier-2."""
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import classify_candidate_tier
    assert classify_candidate_tier("fail") == 2
    assert classify_candidate_tier("na") == 2


def test_classify_candidate_tier_all_four_discriminating_cases():
    """Codex R1.C1 four-case fixture (spec §E.4 discriminating test pattern):
      1. None  -> 1 (TT-gate skip; pre-risk historical)
      2. pass  -> 1 (risk passed; bucket determined by TT/VCP)
      3. fail  -> 2 (risk blocked candidate)
      4. na    -> 2 (insufficient data; treated as fail by bucket_for)
    """
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import classify_candidate_tier
    assert classify_candidate_tier(None) == 1,  "None (TT-gate skip) must be tier-1"
    assert classify_candidate_tier("pass") == 1, "pass must be tier-1"
    assert classify_candidate_tier("fail") == 2, "fail (risk blocked) must be tier-2"
    assert classify_candidate_tier("na") == 2,   "na (risk returned na) must be tier-2"


# ---------------------------------------------------------------------------
# (13) build_eval_run_cohort: current_equity historical snapshot path
# ---------------------------------------------------------------------------

def test_build_eval_run_cohort_uses_historical_equity_snapshot(tmp_path):
    db_path = tmp_path / "fixture.db"
    _apply_phase1_migration(db_path)
    _apply_equity_snapshot_table(db_path)
    _seed_equity_snapshot(db_path, snapshot_date="2026-04-28", equity_dollars=10000.0)

    # Create minimal OHLCV files for SPY (benchmark)
    _make_shape_a_parquet(tmp_path / "SPY.yfinance.parquet", n_bars=250)

    conn = sqlite3.connect(str(db_path))
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import build_eval_run_cohort
    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import BothExistDiagnostic
    cfg = Config.from_defaults()
    diag = BothExistDiagnostic()
    cohort = build_eval_run_cohort(
        conn,
        eval_run_id=1,
        data_asof_date=date(2026, 4, 30),
        cfg=cfg,
        universe_tickers=(),
        candidate_tickers=(),
        universe_hash="test_hash",
        cache_dir=tmp_path,
        horizon_weeks=12,
        diagnostic=diag,
    )
    conn.close()
    # Historical snapshot exists at or before 2026-04-30 -> not via surrogate
    assert cohort.current_equity == max(7500.0, 10000.0)
    assert not cohort.current_equity_via_surrogate


# ---------------------------------------------------------------------------
# (14) current_equity fallback to most-recent snapshot + via_surrogate flag
# ---------------------------------------------------------------------------

def test_build_eval_run_cohort_falls_back_to_most_recent_snapshot(tmp_path):
    db_path = tmp_path / "fixture.db"
    _apply_phase1_migration(db_path)
    _apply_equity_snapshot_table(db_path)
    # Only a FUTURE snapshot (no historical at asof)
    _seed_equity_snapshot(db_path, snapshot_date="2026-05-15", equity_dollars=12000.0)

    _make_shape_a_parquet(tmp_path / "SPY.yfinance.parquet", n_bars=250)

    conn = sqlite3.connect(str(db_path))
    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import BothExistDiagnostic
    cfg = Config.from_defaults()
    diag = BothExistDiagnostic()
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import build_eval_run_cohort
    cohort = build_eval_run_cohort(
        conn,
        eval_run_id=1,
        data_asof_date=date(2026, 4, 30),  # before 2026-05-15
        cfg=cfg,
        universe_tickers=(),
        candidate_tickers=(),
        universe_hash="test_hash",
        cache_dir=tmp_path,
        horizon_weeks=12,
        diagnostic=diag,
    )
    conn.close()
    # No snapshot on-or-before; falls back to most-recent (12000) -> via_surrogate
    assert cohort.current_equity == max(7500.0, 12000.0)
    assert cohort.current_equity_via_surrogate


# ---------------------------------------------------------------------------
# (15) current_equity fallback to floor surrogate + via_surrogate flag
# ---------------------------------------------------------------------------

def test_build_eval_run_cohort_falls_back_to_floor_when_no_snapshots(tmp_path):
    db_path = tmp_path / "fixture.db"
    _apply_phase1_migration(db_path)
    _apply_equity_snapshot_table(db_path)
    # No snapshots at all

    _make_shape_a_parquet(tmp_path / "SPY.yfinance.parquet", n_bars=250)

    conn = sqlite3.connect(str(db_path))
    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import BothExistDiagnostic
    cfg = Config.from_defaults()
    diag = BothExistDiagnostic()
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import build_eval_run_cohort
    cohort = build_eval_run_cohort(
        conn,
        eval_run_id=1,
        data_asof_date=date(2026, 4, 30),
        cfg=cfg,
        universe_tickers=(),
        candidate_tickers=(),
        universe_hash="test_hash",
        cache_dir=tmp_path,
        horizon_weeks=12,
        diagnostic=diag,
    )
    conn.close()
    # No snapshots -> floor surrogate ($7500 per auto-memory)
    assert cohort.current_equity == 7500.0
    assert cohort.current_equity_via_surrogate


# ---------------------------------------------------------------------------
# (16) candidate-not-in-universe populates returns for fallback_spy path
# ---------------------------------------------------------------------------

def test_build_eval_run_cohort_populates_returns_for_candidate_not_in_universe(tmp_path):
    """Codex R2.M1 RESOLVED: candidate tickers outside universe_tickers MUST
    still have returns_12w populated so compute_rs returns 'fallback_spy'
    NOT 'unavailable' -- which would break TT8 criterion.
    """
    db_path = tmp_path / "fixture.db"
    _apply_phase1_migration(db_path)
    _apply_equity_snapshot_table(db_path)

    # Plant parquet for SPY + candidate NOT in universe
    _make_shape_a_parquet(tmp_path / "SPY.yfinance.parquet", n_bars=250)
    _make_shape_a_parquet(tmp_path / "EXTCAND.yfinance.parquet", n_bars=250)

    conn = sqlite3.connect(str(db_path))
    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import BothExistDiagnostic
    cfg = Config.from_defaults()
    diag = BothExistDiagnostic()
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import build_eval_run_cohort
    cohort = build_eval_run_cohort(
        conn,
        eval_run_id=1,
        data_asof_date=date(2026, 4, 30),
        cfg=cfg,
        universe_tickers=(),  # EXTCAND is NOT in universe
        candidate_tickers=("EXTCAND",),  # but IS in candidate_tickers
        universe_hash="test_hash",
        cache_dir=tmp_path,
        horizon_weeks=12,
        diagnostic=diag,
    )
    conn.close()
    # EXTCAND must have a return populated so compute_rs doesn't yield 'unavailable'
    assert "EXTCAND" in cohort.batch.returns_12w_by_ticker


# ---------------------------------------------------------------------------
# (17) defensive signature-lock tests
# ---------------------------------------------------------------------------

def test_evaluate_one_signature_unchanged_via_inspect_signature():
    """Per Codex R1.M5 RESOLVED: evaluator.py uses `from __future__ import
    annotations` so raw return_annotation is the string 'Candidate' not the
    class object. Use typing.get_type_hints to resolve.
    """
    from swing.data.models import Candidate
    from swing.evaluation.evaluator import evaluate_one
    params = list(inspect.signature(evaluate_one).parameters.keys())
    assert params == ["ctx"]
    hints = typing.get_type_hints(evaluate_one)
    assert hints.get("return") is Candidate


def test_load_universe_signature_unchanged_via_inspect_signature():
    from swing.evaluation.rs import load_universe
    params = list(inspect.signature(load_universe).parameters.keys())
    assert params == ["path"]


def test_get_latest_snapshot_on_or_before_signature_unchanged():
    from swing.data.repos.account_equity_snapshots import get_latest_snapshot_on_or_before
    params = inspect.signature(get_latest_snapshot_on_or_before).parameters
    assert "asof_date" in params
    assert params["asof_date"].kind == inspect.Parameter.KEYWORD_ONLY


# ---------------------------------------------------------------------------
# (18) horizon_weeks-scaled bars_needed
# ---------------------------------------------------------------------------

def test_build_eval_run_cohort_horizon_weeks_scales_bars_needed(tmp_path):
    """Codex R3.M1 RESOLVED: bars_needed = horizon_weeks * 5.

    Ticker with 65 bars:
      - horizon_weeks=14 -> bars_needed=70 -> 65 <= 70 -> SKIP (not in returns)
      - horizon_weeks=12 -> bars_needed=60 -> 65 > 60 -> INCLUDED (in returns)
    """
    db_path = tmp_path / "fixture.db"
    _apply_phase1_migration(db_path)
    _apply_equity_snapshot_table(db_path)

    # Plant SPY (250 bars, always included) + ZZSHORT (65 bars, borderline)
    _make_shape_a_parquet(tmp_path / "SPY.yfinance.parquet", n_bars=250)
    _make_shape_a_parquet(tmp_path / "ZZSHORT.yfinance.parquet", n_bars=65)

    conn = sqlite3.connect(str(db_path))
    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import BothExistDiagnostic
    cfg = Config.from_defaults()
    diag_14 = BothExistDiagnostic()
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import build_eval_run_cohort
    cohort_hw14 = build_eval_run_cohort(
        conn,
        eval_run_id=1,
        data_asof_date=date(2026, 4, 30),
        cfg=cfg,
        universe_tickers=("ZZSHORT",),
        candidate_tickers=(),
        universe_hash="test_hash",
        cache_dir=tmp_path,
        horizon_weeks=14,  # bars_needed = 70; 65 <= 70 -> skip
        diagnostic=diag_14,
    )

    diag_12 = BothExistDiagnostic()
    cohort_hw12 = build_eval_run_cohort(
        conn,
        eval_run_id=1,
        data_asof_date=date(2026, 4, 30),
        cfg=cfg,
        universe_tickers=("ZZSHORT",),
        candidate_tickers=(),
        universe_hash="test_hash",
        cache_dir=tmp_path,
        horizon_weeks=12,  # bars_needed = 60; 65 > 60 -> included
        diagnostic=diag_12,
    )
    conn.close()

    # With horizon_weeks=14: ZZSHORT skipped (65 <= 70)
    assert "ZZSHORT" not in cohort_hw14.batch.returns_12w_by_ticker

    # With horizon_weeks=12: ZZSHORT included (65 > 60)
    assert "ZZSHORT" in cohort_hw12.batch.returns_12w_by_ticker


# ---------------------------------------------------------------------------
# (19) build_eval_run_cohort uses ohlcv_getter cache when provided (Codex R1.M3)
# ---------------------------------------------------------------------------

def test_build_eval_run_cohort_uses_ohlcv_getter_cache_when_provided(tmp_path):
    """Codex R1.M3 discriminating test: when ohlcv_getter is provided,
    build_eval_run_cohort uses it to get full-history frames rather than
    calling read_yfinance_shape_a / read_yfinance_shape_a_sliced directly.

    This verifies the dependency-injection path (Option A) is wired correctly:
    the per-ticker OHLCV cache from sweep.py's _get_ohlcv closure is shared
    with build_eval_run_cohort to avoid double-reading parquet files.

    Discriminating fixture: getter_call_count increments each time the
    injected ohlcv_getter is called. After calling build_eval_run_cohort
    with ohlcv_getter=injected, assert getter_call_count > 0 (the injected
    getter was used). Also verify read_yfinance_shape_a_sliced was NOT called
    by monkeypatching the fallback path to raise if invoked.
    """
    db_path = tmp_path / "fixture.db"
    _apply_phase1_migration(db_path)
    _apply_equity_snapshot_table(db_path)

    # Plant Shape A parquet for SPY + one universe ticker
    _make_shape_a_parquet(tmp_path / "SPY.yfinance.parquet", n_bars=250)
    _make_shape_a_parquet(tmp_path / "ZZGETTER1.yfinance.parquet", n_bars=250)

    conn = sqlite3.connect(str(db_path))

    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import (
        BothExistDiagnostic,
        read_yfinance_shape_a,
    )

    # Build a pre-loaded frame cache (mirrors what sweep.py's _get_ohlcv does)
    cache: dict[str, object] = {}
    getter_call_count = {"n": 0}

    def injected_getter(ticker: str):
        getter_call_count["n"] += 1
        if ticker not in cache:
            diag = BothExistDiagnostic()
            cache[ticker] = read_yfinance_shape_a(ticker, tmp_path, diagnostic=diag)
        return cache[ticker]

    cfg = Config.from_defaults()
    import research.harness.aplus_v2_ohlcv_evaluator.context_builder as cb_mod
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import build_eval_run_cohort

    # Monkeypatch read_yfinance_shape_a_sliced to assert it is NOT called
    # (when ohlcv_getter is provided the fallback path should be bypassed).

    original_sliced = cb_mod.read_yfinance_shape_a_sliced
    fallback_called = {"n": 0}

    def _never_called_sliced(*args, **kwargs):
        fallback_called["n"] += 1
        return original_sliced(*args, **kwargs)

    cb_mod.read_yfinance_shape_a_sliced = _never_called_sliced
    try:
        diag = BothExistDiagnostic()
        cohort = build_eval_run_cohort(
            conn,
            eval_run_id=1,
            data_asof_date=date(2026, 4, 30),
            cfg=cfg,
            universe_tickers=("ZZGETTER1",),
            candidate_tickers=(),
            universe_hash="test_hash",
            cache_dir=tmp_path,
            horizon_weeks=12,
            diagnostic=diag,
            ohlcv_getter=injected_getter,  # Codex R1.M3: injected cache
        )
    finally:
        cb_mod.read_yfinance_shape_a_sliced = original_sliced

    conn.close()

    # Discriminating: injected getter was called (not the fallback)
    assert getter_call_count["n"] > 0, (
        "ohlcv_getter was never called; build_eval_run_cohort must use the "
        "injected cache when ohlcv_getter is provided (Codex R1.M3 Option A)"
    )
    # Discriminating: fallback (read_yfinance_shape_a_sliced) was NOT called
    assert fallback_called["n"] == 0, (
        f"read_yfinance_shape_a_sliced was called {fallback_called['n']} times "
        "when ohlcv_getter was provided; fallback must be bypassed when "
        "ohlcv_getter is injected (Codex R1.M3 Option A)"
    )
    # Cohort built successfully
    assert cohort.eval_run_id == 1
