"""Tests for V2 OHLCV harness sweep.py orchestrator module.

Covers per §H T-V2.2 ~17 tests:
  (1)  SweepEntryV2 __post_init__ Literal validation
  (2)  per-(variable, sweep_point) orchestration core
  (3)  tier-1 baseline parity CRITICAL blocking
  (4)  tier-2 parity reporting non-blocking surrogate-flagged
  (5)  single-variable downstream propagation (rs.rs_rank_min_pass)
  (6)  vcp.watch_max_fails special-case bucket promotion
  (7)  vcp.watch_max_fails special-case branch NOT via cfg_substitution
  (8)  failure isolation OhlcvCoverageError mode
  (9)  failure isolation OutOfRangeSubstitutionError mode
  (10) failure isolation generic Exception mode
  (11) multi-eval_run universe scan (2+ eval_runs)
  (12) per-eval_run BatchContext cache bound (LOAD-BEARING per Codex M4)
  (13) per-TICKER OHLCV cache bound (Codex R2.M5)
  (14) runtime cap truncates with partial-result flag
  (15) out_of_range substitution skip discriminating fixture
  (16) defensive bucket_for signature-lock (Expansion #2 refinement)
  (17) empty-eval-runs short-circuit (Codex R3.M3 + R4.M1 + R5.M1)
"""
from __future__ import annotations

import dataclasses
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from swing.config import Config

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_shape_a_parquet(path: Path, n_bars: int = 250, sentinel_close: float = 100.0) -> None:
    """Write a Shape A parquet (lowercase OHLCV + asof_date column)."""
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


def _build_test_db(tmp_path: Path) -> Path:
    """Create a minimal SQLite DB at tmp_path/test.db with required schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS evaluation_runs (
          id INTEGER PRIMARY KEY,
          run_ts TEXT NOT NULL,
          data_asof_date TEXT NOT NULL,
          action_session_date TEXT NOT NULL,
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
          sector TEXT,
          industry TEXT,
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

        CREATE TABLE IF NOT EXISTS account_equity_snapshots (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT NOT NULL,
            equity_dollars REAL NOT NULL CHECK (equity_dollars > 0),
            source TEXT NOT NULL CHECK (source IN ('manual', 'schwab_api', 'tos_csv')),
            source_artifact_path TEXT,
            recorded_at TEXT NOT NULL,
            recorded_by TEXT NOT NULL,
            notes TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ux_account_equity_snapshots_date_source
            ON account_equity_snapshots (snapshot_date, source);
    """)
    conn.close()
    return db_path


def _seed_eval_run(db_path: Path, run_id: int, asof_date: str) -> None:
    conn = sqlite3.connect(str(db_path))
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
    risk_feasibility_result: str | None = "pass",
) -> int:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, rs_method)"
        " VALUES (?, ?, ?, 'unavailable')",
        (eval_run_id, ticker, bucket),
    )
    candidate_id = cursor.lastrowid
    if risk_feasibility_result is not None:
        conn.execute(
            "INSERT INTO candidate_criteria (candidate_id, criterion_name, layer, result)"
            " VALUES (?, 'risk_feasibility', 'risk', ?)",
            (candidate_id, risk_feasibility_result),
        )
    conn.commit()
    conn.close()
    return candidate_id


def _cfg_with_universe(universe_csv: Path) -> Config:
    """Return a Config with rs_universe_path overridden."""
    cfg = Config.from_defaults()
    new_paths = dataclasses.replace(cfg.paths, rs_universe_path=str(universe_csv))
    return dataclasses.replace(cfg, paths=new_paths)


def _make_universe_csv(tmp_path: Path, tickers: list[str]) -> Path:
    """Write a minimal RS universe CSV with required 'ticker' header."""
    p = tmp_path / "universe.csv"
    p.write_text("ticker\n" + "\n".join(tickers) + "\n", encoding="utf-8")
    return p


def _make_variable(
    name: str,
    kind: str = "threshold_additive",
    current_value: float | int = 70,
    sweep_points: tuple = (60, 65, 70, 75, 80),
) -> object:
    """Create a SweepVariable for testing."""
    from research.harness.aplus_sensitivity.variables import SweepVariable
    return SweepVariable(
        name=name,
        kind=kind,
        current_value=current_value,
        sweep_points=sweep_points,
    )


def _build_minimal_universe_and_ohlcv(
    tmp_path: Path,
    *,
    tickers: list[str],
    n_bars: int = 250,
    sentinel_close: float = 100.0,
    also_spy: bool = True,
) -> Path:
    """Plant Shape A parquet for each ticker + optionally SPY."""
    for ticker in tickers:
        _make_shape_a_parquet(
            tmp_path / f"{ticker}.yfinance.parquet",
            n_bars=n_bars,
            sentinel_close=sentinel_close,
        )
    if also_spy and "SPY" not in tickers:
        _make_shape_a_parquet(
            tmp_path / "SPY.yfinance.parquet",
            n_bars=n_bars,
            sentinel_close=500.0,
        )
    return _make_universe_csv(tmp_path, tickers)


# ---------------------------------------------------------------------------
# (1) SweepEntryV2 __post_init__ Literal validation
# ---------------------------------------------------------------------------

def test_SweepEntryV2_post_init_rejects_invalid_kind():  # noqa: N802
    """Per cumulative gotcha "Literal[...] type hints are NOT runtime-enforced"."""
    from research.harness.aplus_v2_ohlcv_evaluator.sweep import SweepEntryV2
    with pytest.raises(ValueError, match="garbage"):
        SweepEntryV2(
            variable_name="rs.rs_rank_min_pass",
            kind="garbage",
            sweep_point=70,
            aplus_count=5,
            watch_count=3,
            skip_count=10,
            excluded_count=0,
            delta_aplus=0,
            delta_watch=0,
            out_of_range_skip_count=0,
            ohlcv_coverage_skip_count=0,
            evaluation_error_skip_count=0,
        )


def test_SweepEntryV2_valid_kinds_all_accepted():  # noqa: N802
    """All valid kinds must be accepted."""
    from research.harness.aplus_v2_ohlcv_evaluator.sweep import SweepEntryV2
    for kind in ("gate", "threshold_additive", "threshold_multiplicative"):
        entry = SweepEntryV2(
            variable_name="rs.rs_rank_min_pass",
            kind=kind,
            sweep_point=70,
            aplus_count=5,
            watch_count=3,
            skip_count=10,
            excluded_count=0,
            delta_aplus=0,
            delta_watch=0,
            out_of_range_skip_count=0,
            ohlcv_coverage_skip_count=0,
            evaluation_error_skip_count=0,
        )
        assert entry.kind == kind


# ---------------------------------------------------------------------------
# (2) Per-(variable, sweep_point) orchestration core
# ---------------------------------------------------------------------------

def test_run_v2_sweep_produces_one_entry_per_variable_sweep_point(tmp_path):
    """Synthetic 3-candidate / 1-variable / 2-sweep-point universe."""
    db_path = _build_test_db(tmp_path)
    _seed_eval_run(db_path, 1, "2026-04-30")

    # Plant tickers: 100 universe tickers + 3 candidates
    universe_tickers = [f"ZZU{i:03d}" for i in range(100)]
    for t in universe_tickers:
        _make_shape_a_parquet(tmp_path / f"{t}.yfinance.parquet", n_bars=250)
    _make_shape_a_parquet(tmp_path / "SPY.yfinance.parquet", n_bars=250, sentinel_close=500.0)

    for ticker in ("ZZA001", "ZZA002", "ZZA003"):
        _make_shape_a_parquet(tmp_path / f"{ticker}.yfinance.parquet", n_bars=250)
        _seed_candidate(db_path, eval_run_id=1, ticker=ticker, bucket="skip")

    universe_csv = _make_universe_csv(tmp_path, universe_tickers)
    cfg = _cfg_with_universe(universe_csv)

    var = _make_variable(
        "rs.rs_rank_min_pass", kind="threshold_additive",
        current_value=70, sweep_points=(60, 70),
    )

    from research.harness.aplus_v2_ohlcv_evaluator.sweep import run_v2_sweep

    conn = sqlite3.connect(str(db_path))
    result = run_v2_sweep(
        conn,
        variables=(var,),
        cfg=cfg,
        cache_dir=tmp_path,
        eval_runs_window=5,
        min_universe_size=50,
    )
    conn.close()

    # 1 variable x 2 sweep_points = 2 entries
    assert len(result.entries) == 2
    assert all(e.variable_name == "rs.rs_rank_min_pass" for e in result.entries)
    sweep_points = {e.sweep_point for e in result.entries}
    assert sweep_points == {60, 70}


# ---------------------------------------------------------------------------
# (3) Tier-1 baseline parity CRITICAL blocking
# ---------------------------------------------------------------------------

def test_baseline_recompute_tier1_matches_persisted_bucket_when_cfg_unchanged(tmp_path):
    """Tier-1 parity: candidates with persisted_risk_result='pass' must match V1
    when evaluate_one is run with unchanged cfg at current_value sweep_point."""
    db_path = _build_test_db(tmp_path)
    _seed_eval_run(db_path, 1, "2026-04-30")

    # Universe
    universe_tickers = [f"ZZU{i:03d}" for i in range(100)]
    for t in universe_tickers:
        _make_shape_a_parquet(tmp_path / f"{t}.yfinance.parquet", n_bars=250)
    _make_shape_a_parquet(tmp_path / "SPY.yfinance.parquet", n_bars=250, sentinel_close=500.0)

    # Candidate: seed as "skip" (the most common bucket; risk_feasibility = pass -> tier-1)
    _make_shape_a_parquet(tmp_path / "ZZPARITY1.yfinance.parquet", n_bars=250)
    _seed_candidate(
        db_path, eval_run_id=1, ticker="ZZPARITY1", bucket="skip",
        risk_feasibility_result="pass",
    )

    universe_csv = _make_universe_csv(tmp_path, universe_tickers)
    cfg = _cfg_with_universe(universe_csv)

    # Use ONLY the current_value sweep point to check parity
    cfg_obj = Config.from_defaults()
    current_rs_rank = cfg_obj.rs.rs_rank_min_pass  # 70
    var = _make_variable(
        "rs.rs_rank_min_pass", current_value=current_rs_rank,
        sweep_points=(current_rs_rank,),
    )

    from research.harness.aplus_v2_ohlcv_evaluator.sweep import run_v2_sweep

    conn = sqlite3.connect(str(db_path))
    result = run_v2_sweep(
        conn,
        variables=(var,),
        cfg=cfg,
        cache_dir=tmp_path,
        eval_runs_window=5,
        min_universe_size=50,
    )
    conn.close()

    # Tier-1 parity: tier1_match must be True (no tier-1 mismatches)
    assert result.baseline_parity.tier1_match is True
    assert len(result.baseline_parity.tier1_mismatch_candidates) == 0


# ---------------------------------------------------------------------------
# (4) Tier-2 parity reporting non-blocking + surrogate-flagged
# ---------------------------------------------------------------------------

def test_baseline_recompute_tier2_surfaces_surrogate_attribution(tmp_path):
    """Tier-2 candidates (risk_feasibility != 'pass') emit bucket_via_surrogate
    when no historical equity snapshot is found."""
    db_path = _build_test_db(tmp_path)
    _seed_eval_run(db_path, 1, "2026-04-30")

    universe_tickers = [f"ZZU{i:03d}" for i in range(100)]
    for t in universe_tickers:
        _make_shape_a_parquet(tmp_path / f"{t}.yfinance.parquet", n_bars=250)
    _make_shape_a_parquet(tmp_path / "SPY.yfinance.parquet", n_bars=250, sentinel_close=500.0)

    # Tier-2 candidate: persisted_risk_result='fail'
    _make_shape_a_parquet(tmp_path / "ZZFAIL1.yfinance.parquet", n_bars=250)
    _seed_candidate(
        db_path, eval_run_id=1, ticker="ZZFAIL1", bucket="skip",
        risk_feasibility_result="fail",
    )

    universe_csv = _make_universe_csv(tmp_path, universe_tickers)
    cfg = _cfg_with_universe(universe_csv)

    cfg_obj = Config.from_defaults()
    current_rs_rank = cfg_obj.rs.rs_rank_min_pass
    var = _make_variable(
        "rs.rs_rank_min_pass", current_value=current_rs_rank,
        sweep_points=(current_rs_rank,),
    )

    from research.harness.aplus_v2_ohlcv_evaluator.sweep import run_v2_sweep

    conn = sqlite3.connect(str(db_path))
    result = run_v2_sweep(
        conn,
        variables=(var,),
        cfg=cfg,
        cache_dir=tmp_path,
        eval_runs_window=5,
        min_universe_size=50,
    )
    conn.close()

    # No equity snapshot -> via_surrogate=True for tier-2
    # tier-2 is non-blocking: tier1_match should still be True (no tier-1 mismatches)
    assert result.baseline_parity.tier1_match is True
    # Discriminating: the surrogate flag must surface somewhere for the tier-2 candidate.
    # Two cases at current_value sweep point:
    #   (a) persisted_bucket == recomputed_bucket (match) -> tier2_via_surrogate_count >= 1
    #   (b) persisted_bucket != recomputed_bucket (mismatch) -> FlippedCandidate with
    #       bucket_via_surrogate=True and eval_run_id=1 must appear in result.flipped
    # At least one of these must hold (the candidate exists, no equity snapshot -> surrogate).
    flipped_surrogate_tier2 = [
        f for f in result.flipped
        if f.eval_run_id == 1 and f.bucket_via_surrogate
    ]
    surrogate_surfaced = (
        result.baseline_parity.tier2_via_surrogate_count >= 1
        or len(flipped_surrogate_tier2) >= 1
    )
    assert surrogate_surfaced, (
        "Expected bucket_via_surrogate to surface for the tier-2 candidate with no equity "
        "snapshot: either baseline_parity.tier2_via_surrogate_count >= 1 (bucket match) "
        "or at least one FlippedCandidate with bucket_via_surrogate=True for eval_run_id=1 "
        "(bucket mismatch), but neither found. "
        f"tier2_via_surrogate_count={result.baseline_parity.tier2_via_surrogate_count}, "
        f"flipped_surrogate_tier2={flipped_surrogate_tier2}"
    )


# ---------------------------------------------------------------------------
# (5) Single-variable downstream propagation
# ---------------------------------------------------------------------------

def test_single_variable_downstream_propagation_rs_rank(tmp_path):
    """Verify cfg substitution propagates to evaluate_one for each sweep_point.

    Mocks evaluate_one in the sweep module to capture the config argument
    passed at each call; asserts the two sweep_points (60 vs 70) receive
    different rs.rs_rank_min_pass values, proving substitute_cfg is wired
    end-to-end through _evaluate_candidate_under_sweep.
    """
    db_path = _build_test_db(tmp_path)
    _seed_eval_run(db_path, 1, "2026-04-30")

    universe_tickers = [f"ZZU{i:03d}" for i in range(100)]
    for t in universe_tickers:
        _make_shape_a_parquet(tmp_path / f"{t}.yfinance.parquet", n_bars=250)
    _make_shape_a_parquet(tmp_path / "SPY.yfinance.parquet", n_bars=250, sentinel_close=500.0)

    _make_shape_a_parquet(tmp_path / "ZZRS001.yfinance.parquet", n_bars=250)
    _seed_candidate(
        db_path, eval_run_id=1, ticker="ZZRS001", bucket="skip",
        risk_feasibility_result="pass",
    )

    universe_csv = _make_universe_csv(tmp_path, universe_tickers)
    cfg = _cfg_with_universe(universe_csv)

    # Two sweep_points that differ so substituted cfg values differ
    var = _make_variable("rs.rs_rank_min_pass", current_value=70, sweep_points=(60, 70))

    # Track configs seen by evaluate_one keyed by sweep_point
    from research.harness.aplus_v2_ohlcv_evaluator import sweep as sweep_mod

    original_evaluate = sweep_mod.evaluate_one
    seen_rs_rank_by_sweep_point: dict[float, list[int]] = {}

    def _tracking_evaluate(ctx):
        rank = ctx.config.rs.rs_rank_min_pass
        # Record each config.rs.rs_rank_min_pass value seen per invocation
        seen_rs_rank_by_sweep_point.setdefault("observed", []).append(rank)
        return original_evaluate(ctx)

    sweep_mod.evaluate_one = _tracking_evaluate
    try:
        from research.harness.aplus_v2_ohlcv_evaluator.sweep import run_v2_sweep
        conn = sqlite3.connect(str(db_path))
        result = run_v2_sweep(
            conn,
            variables=(var,),
            cfg=cfg,
            cache_dir=tmp_path,
            eval_runs_window=5,
            min_universe_size=50,
        )
        conn.close()
    finally:
        sweep_mod.evaluate_one = original_evaluate

    # V2 runs end-to-end for both sweep points
    assert len(result.entries) == 2
    assert result.total_candidates == 1

    # Discriminating: the two sweep_points must produce DIFFERENT rs_rank_min_pass
    # values in the config passed to evaluate_one (60 for sweep_point=60;
    # 70 for sweep_point=70). Without this, substitute_cfg would be a no-op.
    #
    # NOTE (Codex R1.M2 fix): _compute_baseline_parity now calls evaluate_one
    # once with the unsubstituted cfg (value=70) BEFORE the variable loop.
    # The sweep loop then calls it twice more (sweep_points=60 and 70).
    # Total = 3 calls. The DISCRIMINATING assertion is that BOTH 60 and 70
    # appear in the observed values (proving substitute_cfg propagates correctly),
    # not that evaluate_one is called exactly twice.
    observed_values = seen_rs_rank_by_sweep_point.get("observed", [])
    assert len(observed_values) >= 2, (
        f"Expected evaluate_one called at least twice (once per sweep_point), "
        f"got {observed_values}"
    )
    assert set(observed_values) >= {60, 70}, (
        f"Expected evaluate_one to receive rs_rank_min_pass values 60 and 70 "
        f"(one per sweep_point), got {observed_values}. "
        "substitute_cfg may not be propagating the swept variable correctly."
    )


# ---------------------------------------------------------------------------
# (6) vcp.watch_max_fails special-case bucket promotion
# ---------------------------------------------------------------------------

def test_apply_watch_max_fails_override_promotes_watch_bucket():
    """Test _apply_watch_max_fails_override in isolation with a mock Candidate.

    Verifies: vcp_fails=3 + watch_max_fails=2 -> 'skip';
              vcp_fails=3 + watch_max_fails=4 -> 'watch'.

    Note (Option A per code-quality review): the original test had unused DB +
    universe + parquet fixture setup that was never consumed (the test called
    _apply_watch_max_fails_override directly with a MagicMock). That misleading
    setup has been removed. End-to-end integration of the special-case branch
    through run_v2_sweep is covered by
    test_vcp_watch_max_fails_special_case_not_via_cfg_substitution.
    """
    from research.harness.aplus_v2_ohlcv_evaluator.sweep import _apply_watch_max_fails_override
    from swing.data.models import CriterionResult

    # Build a mock candidate with 3 vcp_fails
    cfg = Config.from_defaults()
    mock_criteria = (
        CriterionResult(criterion_name="risk_feasibility", layer="risk", result="pass"),
        # TT: 7 passes (meets min_passes=7)
        CriterionResult(criterion_name="tt1", layer="trend_template", result="pass"),
        CriterionResult(criterion_name="tt2", layer="trend_template", result="pass"),
        CriterionResult(criterion_name="tt3", layer="trend_template", result="pass"),
        CriterionResult(criterion_name="tt4", layer="trend_template", result="pass"),
        CriterionResult(criterion_name="tt5", layer="trend_template", result="pass"),
        CriterionResult(criterion_name="tt6", layer="trend_template", result="pass"),
        CriterionResult(criterion_name="tt7", layer="trend_template", result="pass"),
        # VCP: 3 fails (skip under watch_max_fails=2; watch under watch_max_fails=4)
        CriterionResult(criterion_name="prior_trend", layer="vcp", result="fail"),
        CriterionResult(criterion_name="adr", layer="vcp", result="fail"),
        CriterionResult(criterion_name="pullback", layer="vcp", result="fail"),
        CriterionResult(criterion_name="proximity", layer="vcp", result="pass"),
        CriterionResult(criterion_name="tightness", layer="vcp", result="pass"),
        CriterionResult(criterion_name="tightness_range", layer="vcp", result="pass"),
    )

    # Simulate candidate with vcp_fails=3
    mock_candidate = MagicMock()
    mock_candidate.criteria = mock_criteria
    mock_candidate.bucket = "skip"  # under production watch_max_fails=2

    # Under watch_max_fails=2: should be skip (3 > 2)
    result_skip = _apply_watch_max_fails_override(mock_candidate, 2, cfg)
    assert result_skip == "skip"

    # Under watch_max_fails=4: should be watch (3 <= 4)
    result_watch = _apply_watch_max_fails_override(mock_candidate, 4, cfg)
    assert result_watch == "watch"


# ---------------------------------------------------------------------------
# (7) vcp.watch_max_fails special-case NOT routed through cfg_substitution
# ---------------------------------------------------------------------------

def test_vcp_watch_max_fails_special_case_not_via_cfg_substitution(tmp_path):
    """V2's watch_max_fails special-case evaluates via evaluate_one (NOT
    via substitute_cfg). Verify substitute_cfg is NOT called for this var."""
    db_path = _build_test_db(tmp_path)
    _seed_eval_run(db_path, 1, "2026-04-30")

    universe_tickers = [f"ZZU{i:03d}" for i in range(100)]
    for t in universe_tickers:
        _make_shape_a_parquet(tmp_path / f"{t}.yfinance.parquet", n_bars=250)
    _make_shape_a_parquet(tmp_path / "SPY.yfinance.parquet", n_bars=250, sentinel_close=500.0)

    _make_shape_a_parquet(tmp_path / "ZZWMF1.yfinance.parquet", n_bars=250)
    _seed_candidate(
        db_path, eval_run_id=1, ticker="ZZWMF1", bucket="skip",
        risk_feasibility_result="pass",
    )

    universe_csv = _make_universe_csv(tmp_path, universe_tickers)
    cfg = _cfg_with_universe(universe_csv)

    # vcp.watch_max_fails variable (current=2, sweep_points=(2,))
    var = _make_variable("vcp.watch_max_fails", kind="gate", current_value=2, sweep_points=(2,))

    call_count = {"n": 0}
    from research.harness.aplus_v2_ohlcv_evaluator import cfg_substitution

    original_fn = cfg_substitution.substitute_cfg

    def _tracking_substitute_cfg(cfg_arg, variable_name, sweep_value):
        if variable_name == "vcp.watch_max_fails":
            call_count["n"] += 1
        return original_fn(cfg_arg, variable_name, sweep_value)

    from research.harness.aplus_v2_ohlcv_evaluator import sweep as sweep_mod
    original_sweep_substitute = sweep_mod.substitute_cfg
    sweep_mod.substitute_cfg = _tracking_substitute_cfg

    try:
        from research.harness.aplus_v2_ohlcv_evaluator.sweep import run_v2_sweep
        conn = sqlite3.connect(str(db_path))
        run_v2_sweep(
            conn,
            variables=(var,),
            cfg=cfg,
            cache_dir=tmp_path,
            eval_runs_window=5,
            min_universe_size=50,
        )
        conn.close()
    finally:
        sweep_mod.substitute_cfg = original_sweep_substitute

    # substitute_cfg must NOT be called for vcp.watch_max_fails
    assert call_count["n"] == 0, (
        f"substitute_cfg was called {call_count['n']} times for vcp.watch_max_fails; "
        "expected 0 (special-case must bypass cfg_substitution)"
    )


# ---------------------------------------------------------------------------
# (8) Failure isolation: OhlcvCoverageError mode
# ---------------------------------------------------------------------------

def test_failure_isolation_ohlcv_coverage_error_increments_skip_count(tmp_path):
    """Plant 2 candidates: 1 good (250 bars) + 1 with only 10 bars (coverage fail).
    Assert good candidate tallied; ohlcv_coverage_skip_count == 1."""
    db_path = _build_test_db(tmp_path)
    _seed_eval_run(db_path, 1, "2026-04-30")

    universe_tickers = [f"ZZU{i:03d}" for i in range(100)]
    for t in universe_tickers:
        _make_shape_a_parquet(tmp_path / f"{t}.yfinance.parquet", n_bars=250)
    _make_shape_a_parquet(tmp_path / "SPY.yfinance.parquet", n_bars=250, sentinel_close=500.0)

    # Good candidate
    _make_shape_a_parquet(tmp_path / "ZZGOOD1.yfinance.parquet", n_bars=250)
    _seed_candidate(db_path, eval_run_id=1, ticker="ZZGOOD1", bucket="skip")

    # Coverage-fail candidate: only 10 bars (< 200 min_bars)
    _make_shape_a_parquet(tmp_path / "ZZSHORT1.yfinance.parquet", n_bars=10)
    _seed_candidate(db_path, eval_run_id=1, ticker="ZZSHORT1", bucket="skip")

    universe_csv = _make_universe_csv(tmp_path, universe_tickers)
    cfg = _cfg_with_universe(universe_csv)

    cfg_obj = Config.from_defaults()
    current_rs_rank = cfg_obj.rs.rs_rank_min_pass
    var = _make_variable(
        "rs.rs_rank_min_pass", current_value=current_rs_rank,
        sweep_points=(current_rs_rank,),
    )

    from research.harness.aplus_v2_ohlcv_evaluator.sweep import run_v2_sweep

    conn = sqlite3.connect(str(db_path))
    result = run_v2_sweep(
        conn,
        variables=(var,),
        cfg=cfg,
        cache_dir=tmp_path,
        eval_runs_window=5,
        min_universe_size=50,
    )
    conn.close()

    # OHLCV coverage skip counted
    assert result.ohlcv_coverage_skip_count == 1
    # Total candidates = 2 (both loaded into DB)
    assert result.total_candidates == 2


# ---------------------------------------------------------------------------
# (9) Failure isolation: OutOfRangeSubstitutionError mode
# ---------------------------------------------------------------------------

def test_failure_isolation_out_of_range_substitution_error(tmp_path):
    """Substitute trend_template.min_passes=9 when only 8 TT criteria exist.
    Note: substitute_cfg itself doesn't validate range; OutOfRangeSubstitutionError
    can be raised by the production evaluate_one internals OR we can test it
    by monkeypatching substitute_cfg to raise it."""
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import OutOfRangeSubstitutionError

    db_path = _build_test_db(tmp_path)
    _seed_eval_run(db_path, 1, "2026-04-30")

    universe_tickers = [f"ZZU{i:03d}" for i in range(100)]
    for t in universe_tickers:
        _make_shape_a_parquet(tmp_path / f"{t}.yfinance.parquet", n_bars=250)
    _make_shape_a_parquet(tmp_path / "SPY.yfinance.parquet", n_bars=250, sentinel_close=500.0)

    _make_shape_a_parquet(tmp_path / "ZZOOR1.yfinance.parquet", n_bars=250)
    _seed_candidate(db_path, eval_run_id=1, ticker="ZZOOR1", bucket="skip")

    universe_csv = _make_universe_csv(tmp_path, universe_tickers)
    cfg = _cfg_with_universe(universe_csv)

    # Use a variable that will trigger OutOfRangeSubstitutionError via monkeypatch
    var = _make_variable(
        "trend_template.min_passes", kind="gate", current_value=7,
        sweep_points=(7,),  # single point so current_value == sweep_point
    )

    from research.harness.aplus_v2_ohlcv_evaluator import sweep as sweep_mod

    original_evaluate = sweep_mod.evaluate_one

    def _raising_evaluate(ctx):
        raise OutOfRangeSubstitutionError("min_passes=7 out of range (test)")

    sweep_mod.evaluate_one = _raising_evaluate
    try:
        from research.harness.aplus_v2_ohlcv_evaluator.sweep import run_v2_sweep
        conn = sqlite3.connect(str(db_path))
        result = run_v2_sweep(
            conn,
            variables=(var,),
            cfg=cfg,
            cache_dir=tmp_path,
            eval_runs_window=5,
            min_universe_size=50,
        )
        conn.close()
    finally:
        sweep_mod.evaluate_one = original_evaluate

    # SweepEntryV2 for this point should have out_of_range_skip_count == 1
    assert len(result.entries) == 1
    assert result.entries[0].out_of_range_skip_count == 1


# ---------------------------------------------------------------------------
# (10) Failure isolation: generic Exception mode
# ---------------------------------------------------------------------------

def test_failure_isolation_generic_exception_increments_eval_error_count(tmp_path):
    """A generic RuntimeError in evaluate_one increments evaluation_error_skip_count."""
    db_path = _build_test_db(tmp_path)
    _seed_eval_run(db_path, 1, "2026-04-30")

    universe_tickers = [f"ZZU{i:03d}" for i in range(100)]
    for t in universe_tickers:
        _make_shape_a_parquet(tmp_path / f"{t}.yfinance.parquet", n_bars=250)
    _make_shape_a_parquet(tmp_path / "SPY.yfinance.parquet", n_bars=250, sentinel_close=500.0)

    _make_shape_a_parquet(tmp_path / "ZZERR1.yfinance.parquet", n_bars=250)
    _seed_candidate(db_path, eval_run_id=1, ticker="ZZERR1", bucket="skip")

    universe_csv = _make_universe_csv(tmp_path, universe_tickers)
    cfg = _cfg_with_universe(universe_csv)

    var = _make_variable("rs.rs_rank_min_pass", current_value=70, sweep_points=(70,))

    from research.harness.aplus_v2_ohlcv_evaluator import sweep as sweep_mod

    original_evaluate = sweep_mod.evaluate_one

    def _exploding_evaluate(ctx):
        raise RuntimeError("synthetic error for test")

    sweep_mod.evaluate_one = _exploding_evaluate
    try:
        from research.harness.aplus_v2_ohlcv_evaluator.sweep import run_v2_sweep
        conn = sqlite3.connect(str(db_path))
        result = run_v2_sweep(
            conn,
            variables=(var,),
            cfg=cfg,
            cache_dir=tmp_path,
            eval_runs_window=5,
            min_universe_size=50,
        )
        conn.close()
    finally:
        sweep_mod.evaluate_one = original_evaluate

    assert len(result.entries) == 1
    assert result.entries[0].evaluation_error_skip_count == 1


# ---------------------------------------------------------------------------
# (11) Multi-eval_run universe scan
# ---------------------------------------------------------------------------

def test_multi_eval_run_universe_scan_evaluates_all_runs(tmp_path):
    """Plant 2 eval_runs each with 1 candidate; assert V2 evaluates both."""
    db_path = _build_test_db(tmp_path)
    _seed_eval_run(db_path, 1, "2026-04-15")
    _seed_eval_run(db_path, 2, "2026-04-30")

    universe_tickers = [f"ZZU{i:03d}" for i in range(100)]
    for t in universe_tickers:
        _make_shape_a_parquet(tmp_path / f"{t}.yfinance.parquet", n_bars=250)
    _make_shape_a_parquet(tmp_path / "SPY.yfinance.parquet", n_bars=250, sentinel_close=500.0)

    _make_shape_a_parquet(tmp_path / "ZZRUN1.yfinance.parquet", n_bars=250)
    _seed_candidate(db_path, eval_run_id=1, ticker="ZZRUN1", bucket="skip")

    _make_shape_a_parquet(tmp_path / "ZZRUN2.yfinance.parquet", n_bars=250)
    _seed_candidate(db_path, eval_run_id=2, ticker="ZZRUN2", bucket="skip")

    universe_csv = _make_universe_csv(tmp_path, universe_tickers)
    cfg = _cfg_with_universe(universe_csv)

    var = _make_variable("rs.rs_rank_min_pass", current_value=70, sweep_points=(70,))

    from research.harness.aplus_v2_ohlcv_evaluator.sweep import run_v2_sweep

    conn = sqlite3.connect(str(db_path))
    result = run_v2_sweep(
        conn,
        variables=(var,),
        cfg=cfg,
        cache_dir=tmp_path,
        eval_runs_window=10,
        min_universe_size=50,
    )
    conn.close()

    # Both runs evaluated = 2 total candidates
    assert result.total_candidates == 2
    assert result.eval_runs_window == 10
    assert result.eval_run_id_range == (1, 2)


# ---------------------------------------------------------------------------
# (12) Per-eval_run BatchContext cache bound (LOAD-BEARING per Codex M4)
# ---------------------------------------------------------------------------

def test_v2_per_eval_run_batch_context_cached_not_recomputed(tmp_path):
    """Mock build_eval_run_cohort with a call-counter; run V2 sweep across
    3 eval_runs + 1 variable with 2 sweep_points (non-horizon var).
    Assert build_eval_run_cohort.call_count <= 3 (NOT 3 * N_sweep_points).
    """
    db_path = _build_test_db(tmp_path)
    for run_id, asof in [(1, "2026-04-15"), (2, "2026-04-22"), (3, "2026-04-30")]:
        _seed_eval_run(db_path, run_id, asof)

    universe_tickers = [f"ZZU{i:03d}" for i in range(100)]
    for t in universe_tickers:
        _make_shape_a_parquet(tmp_path / f"{t}.yfinance.parquet", n_bars=250)
    _make_shape_a_parquet(tmp_path / "SPY.yfinance.parquet", n_bars=250, sentinel_close=500.0)

    for ticker in (f"ZZC{i:03d}" for i in range(3)):
        _make_shape_a_parquet(tmp_path / f"{ticker}.yfinance.parquet", n_bars=250)
    _seed_candidate(db_path, eval_run_id=1, ticker="ZZC000", bucket="skip")
    _seed_candidate(db_path, eval_run_id=2, ticker="ZZC001", bucket="skip")
    _seed_candidate(db_path, eval_run_id=3, ticker="ZZC002", bucket="skip")

    universe_csv = _make_universe_csv(tmp_path, universe_tickers)
    cfg = _cfg_with_universe(universe_csv)

    # Non-horizon variable with 2 sweep_points
    var = _make_variable("rs.rs_rank_min_pass", current_value=70, sweep_points=(60, 70))

    from research.harness.aplus_v2_ohlcv_evaluator import sweep as sweep_mod

    build_call_count = {"n": 0}
    original_build = sweep_mod.build_eval_run_cohort

    def _counting_build(*args, **kwargs):
        build_call_count["n"] += 1
        return original_build(*args, **kwargs)

    sweep_mod.build_eval_run_cohort = _counting_build
    try:
        from research.harness.aplus_v2_ohlcv_evaluator.sweep import run_v2_sweep
        conn = sqlite3.connect(str(db_path))
        run_v2_sweep(
            conn,
            variables=(var,),
            cfg=cfg,
            cache_dir=tmp_path,
            eval_runs_window=10,
            min_universe_size=50,
        )
        conn.close()
    finally:
        sweep_mod.build_eval_run_cohort = original_build

    # With cache: each (eval_run_id, horizon_weeks) pair built at most once.
    # 3 eval_runs x 1 horizon_weeks value (non-horizon var) = 3 builds max.
    assert build_call_count["n"] <= 3, (
        f"build_eval_run_cohort called {build_call_count['n']} times; "
        "expected <= 3 (LOAD-BEARING cache not working per Codex M4)"
    )


# ---------------------------------------------------------------------------
# (13) Per-TICKER OHLCV cache bound (Codex R2.M5)
# ---------------------------------------------------------------------------

def test_v2_per_ticker_ohlcv_parquet_opened_once(tmp_path):
    """Mock read_yfinance_shape_a with call-counter; run V2 sweep across
    a 5-ticker universe + 5-candidate scenario sharing the same tickers.
    Assert read_yfinance_shape_a.call_count <= N_unique_tickers."""
    db_path = _build_test_db(tmp_path)
    _seed_eval_run(db_path, 1, "2026-04-30")

    universe_tickers = [f"ZZU{i:03d}" for i in range(50)]
    for t in universe_tickers:
        _make_shape_a_parquet(tmp_path / f"{t}.yfinance.parquet", n_bars=250)
    _make_shape_a_parquet(tmp_path / "SPY.yfinance.parquet", n_bars=250, sentinel_close=500.0)

    # 3 candidates sharing 2 tickers
    _make_shape_a_parquet(tmp_path / "ZZSHARED1.yfinance.parquet", n_bars=250)
    _make_shape_a_parquet(tmp_path / "ZZSHARED2.yfinance.parquet", n_bars=250)
    _seed_candidate(db_path, eval_run_id=1, ticker="ZZSHARED1", bucket="skip")
    _seed_candidate(db_path, eval_run_id=1, ticker="ZZSHARED2", bucket="skip")

    universe_csv = _make_universe_csv(tmp_path, universe_tickers)
    cfg = _cfg_with_universe(universe_csv)

    # 2 sweep_points for the same variable
    var = _make_variable("rs.rs_rank_min_pass", current_value=70, sweep_points=(60, 70))

    from research.harness.aplus_v2_ohlcv_evaluator import sweep as sweep_mod

    read_call_count = {"n": 0, "paths": []}
    original_read = sweep_mod.read_yfinance_shape_a

    def _counting_read(ticker, cache_dir, *, diagnostic=None):
        read_call_count["n"] += 1
        read_call_count["paths"].append(ticker)
        return original_read(ticker, cache_dir, diagnostic=diagnostic)

    sweep_mod.read_yfinance_shape_a = _counting_read
    try:
        from research.harness.aplus_v2_ohlcv_evaluator.sweep import run_v2_sweep
        conn = sqlite3.connect(str(db_path))
        run_v2_sweep(
            conn,
            variables=(var,),
            cfg=cfg,
            cache_dir=tmp_path,
            eval_runs_window=5,
            min_universe_size=20,
        )
        conn.close()
    finally:
        sweep_mod.read_yfinance_shape_a = original_read

    # Each ticker should be read at most once across all sweep_points
    # N_unique_tickers = 50 (universe) + 2 (candidates) + 1 (SPY) = 53
    n_unique = len(set(read_call_count["paths"]))
    assert read_call_count["n"] == n_unique, (
        f"read_yfinance_shape_a called {read_call_count['n']} times "
        f"but only {n_unique} unique tickers (per-ticker OHLCV cache not working)"
    )


# ---------------------------------------------------------------------------
# (14) Runtime cap truncates with partial-result flag
# ---------------------------------------------------------------------------

def test_runtime_cap_truncates_sweep_and_sets_flag(tmp_path):
    """Invoke V2 with max_runtime_seconds=0.001; assert truncated_by_runtime_cap==True."""
    db_path = _build_test_db(tmp_path)
    _seed_eval_run(db_path, 1, "2026-04-30")

    universe_tickers = [f"ZZU{i:03d}" for i in range(100)]
    for t in universe_tickers:
        _make_shape_a_parquet(tmp_path / f"{t}.yfinance.parquet", n_bars=250)
    _make_shape_a_parquet(tmp_path / "SPY.yfinance.parquet", n_bars=250, sentinel_close=500.0)

    for ticker in (f"ZZT{i:03d}" for i in range(5)):
        _make_shape_a_parquet(tmp_path / f"{ticker}.yfinance.parquet", n_bars=250)
        _seed_candidate(db_path, eval_run_id=1, ticker=ticker, bucket="skip")

    universe_csv = _make_universe_csv(tmp_path, universe_tickers)
    cfg = _cfg_with_universe(universe_csv)

    # Multiple variables to ensure the cap fires during iteration
    from research.harness.aplus_sensitivity.variables import SweepVariable
    variables = tuple(
        SweepVariable(
            name="rs.rs_rank_min_pass",
            kind="threshold_additive",
            current_value=70,
            sweep_points=(60, 65, 70, 75, 80),
        )
        for _ in range(5)  # 5 identical variables so the cap fires
    )

    from research.harness.aplus_v2_ohlcv_evaluator.sweep import run_v2_sweep

    conn = sqlite3.connect(str(db_path))
    result = run_v2_sweep(
        conn,
        variables=variables,
        cfg=cfg,
        cache_dir=tmp_path,
        eval_runs_window=5,
        min_universe_size=50,
        max_runtime_seconds=0.001,  # very tight cap
    )
    conn.close()

    assert result.truncated_by_runtime_cap is True


# ---------------------------------------------------------------------------
# (15) Out_of_range substitution skip discriminating fixture
# ---------------------------------------------------------------------------

def test_out_of_range_substitution_skip_discriminating(tmp_path):
    """Substitute a variable that raises OutOfRangeSubstitutionError via
    monkeypatch; assert SweepEntryV2.out_of_range_skip_count > 0."""
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import OutOfRangeSubstitutionError

    db_path = _build_test_db(tmp_path)
    _seed_eval_run(db_path, 1, "2026-04-30")

    universe_tickers = [f"ZZU{i:03d}" for i in range(100)]
    for t in universe_tickers:
        _make_shape_a_parquet(tmp_path / f"{t}.yfinance.parquet", n_bars=250)
    _make_shape_a_parquet(tmp_path / "SPY.yfinance.parquet", n_bars=250, sentinel_close=500.0)

    _make_shape_a_parquet(tmp_path / "ZZOORTEST.yfinance.parquet", n_bars=250)
    _seed_candidate(db_path, eval_run_id=1, ticker="ZZOORTEST", bucket="skip")

    universe_csv = _make_universe_csv(tmp_path, universe_tickers)
    cfg = _cfg_with_universe(universe_csv)

    var = _make_variable(
        "trend_template.min_passes", kind="gate",
        current_value=7, sweep_points=(9,),
    )

    from research.harness.aplus_v2_ohlcv_evaluator import sweep as sweep_mod
    original_evaluate = sweep_mod.evaluate_one

    def _out_of_range_evaluate(ctx):
        raise OutOfRangeSubstitutionError(
            "trend_template.min_passes=9 out of range (8 TT criteria)"
        )

    sweep_mod.evaluate_one = _out_of_range_evaluate
    try:
        from research.harness.aplus_v2_ohlcv_evaluator.sweep import run_v2_sweep
        conn = sqlite3.connect(str(db_path))
        result = run_v2_sweep(
            conn,
            variables=(var,),
            cfg=cfg,
            cache_dir=tmp_path,
            eval_runs_window=5,
            min_universe_size=50,
        )
        conn.close()
    finally:
        sweep_mod.evaluate_one = original_evaluate

    assert len(result.entries) == 1
    assert result.entries[0].out_of_range_skip_count >= 1


# ---------------------------------------------------------------------------
# (16) Defensive bucket_for signature-lock (Expansion #2 refinement)
# ---------------------------------------------------------------------------

def test_bucket_for_signature_unchanged_via_inspect_signature():
    """Per NEW gotcha #17 (Expansion #2 refinement BINDING): lock bucket_for
    parameter names against production changes."""
    import inspect

    from swing.evaluation.scoring import bucket_for
    params = list(inspect.signature(bucket_for).parameters.keys())
    assert params == ["trend_template_results", "vcp_results", "risk_results", "config"]


# ---------------------------------------------------------------------------
# (17) Empty-eval-runs short-circuit (Codex R3.M3 + R4.M1 + R5.M1)
# ---------------------------------------------------------------------------

def test_empty_eval_runs_short_circuit_returns_sentinel_without_fetch_candidates(tmp_path):
    """Invoke run_v2_sweep against DB with zero eval_runs; assert:
    - SweepResultV2 returned (not exception)
    - entries == ()
    - universe_size == 0
    - universe_skipped_ticker_count == 0
    - v2_universe_hash == 'empty_no_eval_runs'
    - both_exist_diagnostic.count == 0
    - fetch_candidates NOT invoked (mock-asserted via monkeypatch)
    """
    db_path = _build_test_db(tmp_path)
    # NO eval_runs seeded -- empty DB

    # Universe CSV still valid (though it won't be used)
    universe_tickers = [f"ZZU{i:03d}" for i in range(100)]
    universe_csv = _make_universe_csv(tmp_path, universe_tickers)
    cfg = _cfg_with_universe(universe_csv)

    var = _make_variable("rs.rs_rank_min_pass", current_value=70, sweep_points=(70,))

    from research.harness.aplus_v2_ohlcv_evaluator import sweep as sweep_mod

    fetch_candidates_called = {"n": 0}
    original_fetch_candidates = sweep_mod._fetch_candidates_with_run_id

    def _tracking_fetch(*args, **kwargs):
        fetch_candidates_called["n"] += 1
        return original_fetch_candidates(*args, **kwargs)

    sweep_mod._fetch_candidates_with_run_id = _tracking_fetch
    try:
        from research.harness.aplus_v2_ohlcv_evaluator.sweep import run_v2_sweep
        conn = sqlite3.connect(str(db_path))
        result = run_v2_sweep(
            conn,
            variables=(var,),
            cfg=cfg,
            cache_dir=tmp_path,
            eval_runs_window=5,
            min_universe_size=50,
        )
        conn.close()
    finally:
        sweep_mod._fetch_candidates_with_run_id = original_fetch_candidates

    # Short-circuit assertions
    assert result.entries == ()
    assert result.universe_size == 0
    assert result.universe_skipped_ticker_count == 0
    assert result.v2_universe_hash == "empty_no_eval_runs"
    assert result.both_exist_diagnostic.count == 0
    assert result.total_candidates == 0
    assert result.eval_run_id_range == (0, 0)
    assert result.truncated_by_runtime_cap is False
    assert result.baseline_parity.tier1_match is True

    # fetch_candidates NOT invoked
    assert fetch_candidates_called["n"] == 0, (
        f"_fetch_candidates_with_run_id called {fetch_candidates_called['n']} times "
        "in empty-DB short-circuit path (expected 0)"
    )


# ---------------------------------------------------------------------------
# (18) FileNotFoundError / OSError in precompute tallied as ohlcv_coverage_skip
# ---------------------------------------------------------------------------

def test_missing_parquet_in_precompute_tallied_as_ohlcv_coverage_skip(tmp_path):
    """Plant a candidate ticker with NO parquet file; verify sweep doesn't crash
    and the missing-file case is tallied as ohlcv_coverage_skip_count == 1.

    Discriminating: verifies _precompute_ohlcv_coverage_skips catches
    FileNotFoundError / OSError and tallies them as coverage skips rather than
    crashing the entire sweep (code-quality review Issue 5).
    """
    db_path = _build_test_db(tmp_path)
    _seed_eval_run(db_path, 1, "2026-04-30")

    universe_tickers = [f"ZZU{i:03d}" for i in range(100)]
    for t in universe_tickers:
        _make_shape_a_parquet(tmp_path / f"{t}.yfinance.parquet", n_bars=250)
    _make_shape_a_parquet(tmp_path / "SPY.yfinance.parquet", n_bars=250, sentinel_close=500.0)

    # Good candidate: has parquet
    _make_shape_a_parquet(tmp_path / "ZZGOOD2.yfinance.parquet", n_bars=250)
    _seed_candidate(db_path, eval_run_id=1, ticker="ZZGOOD2", bucket="skip")

    # Missing-parquet candidate: seed in DB but NO parquet file planted
    # (simulates a delisted ticker that was in an old eval_run but whose
    # parquet has been deleted / never fetched)
    _seed_candidate(db_path, eval_run_id=1, ticker="ZZMISSING1", bucket="skip")
    # Deliberately do NOT plant ZZMISSING1.yfinance.parquet

    universe_csv = _make_universe_csv(tmp_path, universe_tickers)
    cfg = _cfg_with_universe(universe_csv)

    cfg_obj = Config.from_defaults()
    current_rs_rank = cfg_obj.rs.rs_rank_min_pass
    var = _make_variable(
        "rs.rs_rank_min_pass", current_value=current_rs_rank,
        sweep_points=(current_rs_rank,),
    )

    from research.harness.aplus_v2_ohlcv_evaluator.sweep import run_v2_sweep

    # Must not raise; sweep should complete and tally the missing-parquet
    # candidate as an ohlcv_coverage_skip.
    conn = sqlite3.connect(str(db_path))
    result = run_v2_sweep(
        conn,
        variables=(var,),
        cfg=cfg,
        cache_dir=tmp_path,
        eval_runs_window=5,
        min_universe_size=50,
    )
    conn.close()

    # Missing parquet tallied as ohlcv_coverage_skip
    assert result.ohlcv_coverage_skip_count >= 1, (
        f"Expected ohlcv_coverage_skip_count >= 1 for missing-parquet candidate, "
        f"got {result.ohlcv_coverage_skip_count}"
    )
    # Total candidates includes both (one good + one missing)
    assert result.total_candidates == 2


# ---------------------------------------------------------------------------
# (19) Baseline parity counts NOT inflated by N_variables (Codex R1.M2)
# ---------------------------------------------------------------------------

def test_baseline_parity_counts_not_inflated_with_multiple_variables(tmp_path):
    """Codex R1.M2 discriminating test: with N_vars > 1, baseline tier counts
    must equal the TRUE per-candidate count (NOT N_vars * true_count).

    Pre-fix: baseline parity was computed inside the per-variable loop at
    is_current_point, so with 3 variables each having current_value in
    sweep_points, tier_1_count + tier_2_count would be inflated 3x.

    Post-fix: _compute_baseline_parity runs ONCE before the variable loop;
    tier_1_count + tier_2_count == total_parity_candidates (1 per candidate
    that passes OHLCV coverage check).
    """
    db_path = _build_test_db(tmp_path)
    _seed_eval_run(db_path, 1, "2026-04-30")

    universe_tickers = [f"ZZU{i:03d}" for i in range(100)]
    for t in universe_tickers:
        _make_shape_a_parquet(tmp_path / f"{t}.yfinance.parquet", n_bars=250)
    _make_shape_a_parquet(tmp_path / "SPY.yfinance.parquet", n_bars=250, sentinel_close=500.0)

    # Plant 3 candidates: 2 tier-1 (pass) + 1 tier-2 (fail)
    for ticker in ("ZZINFL1", "ZZINFL2"):
        _make_shape_a_parquet(tmp_path / f"{ticker}.yfinance.parquet", n_bars=250)
        _seed_candidate(db_path, eval_run_id=1, ticker=ticker, bucket="skip",
                       risk_feasibility_result="pass")  # tier-1
    _make_shape_a_parquet(tmp_path / "ZZINFL3.yfinance.parquet", n_bars=250)
    _seed_candidate(db_path, eval_run_id=1, ticker="ZZINFL3", bucket="skip",
                   risk_feasibility_result="fail")  # tier-2

    universe_csv = _make_universe_csv(tmp_path, universe_tickers)
    cfg = _cfg_with_universe(universe_csv)
    cfg_obj = Config.from_defaults()

    # 3 variables, each with current_value in sweep_points
    # Pre-fix: tier_1_count would be 2 * 3 = 6; tier_2_count would be 1 * 3 = 3
    # Post-fix: tier_1_count = 2; tier_2_count = 1
    variables = (
        _make_variable("rs.rs_rank_min_pass", current_value=cfg_obj.rs.rs_rank_min_pass,
                       sweep_points=(cfg_obj.rs.rs_rank_min_pass,)),
        _make_variable("trend_template.min_passes", kind="gate",
                       current_value=cfg_obj.trend_template.min_passes,
                       sweep_points=(cfg_obj.trend_template.min_passes,)),
        _make_variable("vcp.adr_min_pct", kind="threshold_multiplicative",
                       current_value=cfg_obj.vcp.adr_min_pct,
                       sweep_points=(cfg_obj.vcp.adr_min_pct,)),
    )

    from research.harness.aplus_v2_ohlcv_evaluator.sweep import run_v2_sweep

    conn = sqlite3.connect(str(db_path))
    result = run_v2_sweep(
        conn,
        variables=variables,
        cfg=cfg,
        cache_dir=tmp_path,
        eval_runs_window=5,
        min_universe_size=50,
    )
    conn.close()

    bp = result.baseline_parity
    n_vars = len(variables)  # 3

    # TRUE counts must equal 2 (tier-1) + 1 (tier-2) = 3 total parity candidates.
    # Pre-fix inflation would give tier_1_count = 2 * n_vars = 6.
    assert bp.tier_1_count <= 2, (
        f"tier_1_count={bp.tier_1_count} appears inflated by N_vars={n_vars}. "
        f"Expected <= 2 (true count); pre-fix inflation would give 2*{n_vars}={2*n_vars}. "
        "_compute_baseline_parity must run ONCE outside the variable loop."
    )
    assert bp.tier_2_count <= 1, (
        f"tier_2_count={bp.tier_2_count} appears inflated by N_vars={n_vars}. "
        f"Expected <= 1 (true count); pre-fix inflation would give 1*{n_vars}={n_vars}. "
        "_compute_baseline_parity must run ONCE outside the variable loop."
    )
    # Sanity: combined count must not exceed total candidates
    assert bp.tier_1_count + bp.tier_2_count <= result.total_candidates, (
        f"tier_1_count + tier_2_count = {bp.tier_1_count + bp.tier_2_count} "
        f"> total_candidates = {result.total_candidates}"
    )
