"""T-V2.4 discriminating tests for run.py + CLI subcommand registration.

Tests (11 per plan §H T-V2.4):
  (1)  run_harness returns (md_path, csv_path) + both files exist
  (2)  --eval-runs out-of-range ValueError (0 + 101)
  (3)  --variables-filter unknown raises ValueError listing unknown names
  (4)  --min-universe-size out-of-range ValueError
  (5)  --max-runtime-seconds out-of-range ValueError + accepted
  (6)  ClickException wrapping ValueError (no traceback in output)
  (7)  output file path conventions (name prefix + ISO timestamp)
  (8)  baseline smoke with operator-shape in-memory fixture
  (9)  CLI subcommand --help smoke (aplus-sensitivity-v2)
  (10) subprocess stdout cp1252 safety
  (11) DB opened read-only via URI mode=ro (INSERT raises OperationalError)
  (12) bonus: V1 back-compat --help unchanged (aplus-sensitivity)
  (13) bonus: git diff swing/ gate (env-var guarded)
"""
from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from click.testing import CliRunner

from swing.cli import main as cli

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_shape_a_parquet(path: Path, n_bars: int = 250, close: float = 100.0) -> None:
    dates = pd.date_range(end="2026-04-30", periods=n_bars, freq="B")
    df = pd.DataFrame({
        "asof_date": [d.date().isoformat() for d in dates],
        "open": [close] * n_bars,
        "high": [close + 1.0] * n_bars,
        "low": [close - 1.0] * n_bars,
        "close": [close] * n_bars,
        "volume": [1_000_000] * n_bars,
    })
    df.to_parquet(path, index=False)


_RS_UNIVERSE_CSV = "\n".join(["ticker"] + [f"TK{i:03d}" for i in range(110)]) + "\n"

# Minimal schema subset needed by V2 (subset of production migrations).
_DDL = (
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
         rs_method TEXT NOT NULL CHECK (rs_method IN ('universe','fallback_spy','unavailable')),
         pattern_tag TEXT,
         notes TEXT,
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
         notes TEXT
       )""",
)


def _plant_smoke_db(conn: sqlite3.Connection, n_eval_runs: int = 3) -> None:
    """Plant a minimal smoke DB: N eval_runs x 2 candidates per run."""
    for ddl in _DDL:
        conn.execute(ddl)
    conn.execute(
        "INSERT INTO account_equity_snapshots "
        "(snapshot_date, equity_dollars, source, recorded_at, recorded_by) "
        "VALUES ('2026-01-01', 10000.0, 'manual', '2026-01-01T00:00:00Z', 'test')"
    )
    for run_id in range(1, n_eval_runs + 1):
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, action_session_date) "
            "VALUES (?, ?, ?, ?)",
            (run_id, f"2026-04-{run_id:02d}T00:00:00Z",
             f"2026-04-{run_id:02d}", f"2026-04-{run_id + 1:02d}"),
        )
        for j, (ticker, bucket) in enumerate(
            [("AAPL", "watch"), ("MSFT", "skip")], start=1
        ):
            cid = (run_id - 1) * 2 + j
            conn.execute(
                "INSERT INTO candidates (id, evaluation_run_id, ticker, bucket, rs_method) "
                "VALUES (?, ?, ?, ?, 'universe')",
                (cid, run_id, ticker, bucket),
            )
            conn.execute(
                "INSERT INTO candidate_criteria "
                "(candidate_id, criterion_name, layer, result) "
                "VALUES (?, 'risk_feasibility', 'risk', 'pass')",
                (cid,),
            )
    conn.commit()


def _plant_smoke_ohlcv(cache_dir: Path, n_bars: int = 250) -> None:
    """Plant Shape A parquet files for tickers + RS universe tickers."""
    tickers = ["AAPL", "MSFT", "SPY"] + [f"TK{i:03d}" for i in range(110)]
    for ticker in tickers:
        _make_shape_a_parquet(
            cache_dir / f"{ticker}.yfinance.parquet", n_bars=n_bars
        )


@pytest.fixture
def smoke_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Return (db_path, cfg) for smoke tests; monkeypatches USERPROFILE + HOME
    + rewrites swing.config.toml pointer to use tmp RS universe path."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    # Write RS universe CSV.
    rs_path = tmp_path / "rs_universe.csv"
    rs_path.write_text(_RS_UNIVERSE_CSV, encoding="utf-8")

    # Plant OHLCV parquets.
    cache_dir = tmp_path / "ohlcv_cache"
    cache_dir.mkdir()
    _plant_smoke_ohlcv(cache_dir)

    # Plant DB.
    db_path = tmp_path / "smoke.db"
    conn = sqlite3.connect(str(db_path))
    _plant_smoke_db(conn, n_eval_runs=3)
    conn.close()

    # Monkeypatch Config.from_defaults so tests don't need a real swing.config.toml.
    from swing.config import Config
    real_from_defaults = Config.from_defaults.__func__  # type: ignore[attr-defined]
    cfg = real_from_defaults(Config)
    # Override paths to point at tmp fixtures.
    import dataclasses
    new_paths = dataclasses.replace(
        cfg.paths,
        rs_universe_path=rs_path,
        prices_cache_dir=cache_dir,
    )
    patched_cfg = dataclasses.replace(cfg, paths=new_paths)
    monkeypatch.setattr(
        "research.harness.aplus_v2_ohlcv_evaluator.run._get_cfg",
        lambda: patched_cfg,
    )
    return db_path, patched_cfg


# ---------------------------------------------------------------------------
# Test 1: run_harness returns (md_path, csv_path) + both files exist
# ---------------------------------------------------------------------------


def test_run_harness_returns_md_csv_paths_that_exist(
    tmp_path: Path, smoke_env
) -> None:
    """T-V2.4 #1: run_harness returns (md_path, csv_path) + both files exist."""
    db_path, _ = smoke_env
    out_dir = tmp_path / "out"

    from research.harness.aplus_v2_ohlcv_evaluator.run import run_harness

    md_path, csv_path = run_harness(
        db_path=db_path, eval_runs=3, output_dir=out_dir
    )
    assert md_path.exists(), f"md file not found: {md_path}"
    assert csv_path.exists(), f"csv file not found: {csv_path}"
    assert md_path.suffix == ".md"
    assert csv_path.suffix == ".csv"


# ---------------------------------------------------------------------------
# Test 2: --eval-runs out-of-range ValueError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_eval_runs", [0, 101])
def test_run_harness_eval_runs_out_of_range_raises_value_error(
    bad_eval_runs: int, tmp_path: Path
) -> None:
    """T-V2.4 #2: eval_runs outside [1,100] raises ValueError."""
    from research.harness.aplus_v2_ohlcv_evaluator.run import run_harness

    with pytest.raises(ValueError, match="eval_runs"):
        run_harness(
            db_path=tmp_path / "x.db",
            eval_runs=bad_eval_runs,
            output_dir=tmp_path,
        )


# ---------------------------------------------------------------------------
# Test 3: --variables-filter unknown raises ValueError listing unknown names
# ---------------------------------------------------------------------------


def test_run_harness_variables_filter_unknown_raises_value_error_listing_names(
    tmp_path: Path,
) -> None:
    """T-V2.4 #3: variables_filter with unknown names raises ValueError that
    enumerates the unknown names in the message."""
    from research.harness.aplus_v2_ohlcv_evaluator.run import run_harness

    with pytest.raises(ValueError, match="unknown.*variable") as exc_info:
        run_harness(
            db_path=tmp_path / "x.db",
            eval_runs=20,
            output_dir=tmp_path,
            variables_filter=("rs.rs_rank_min_pass", "bogus.unknown_field"),
        )
    assert "bogus.unknown_field" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 4: --min-universe-size out-of-range ValueError
# ---------------------------------------------------------------------------


def test_run_harness_min_universe_size_zero_raises_value_error(
    tmp_path: Path,
) -> None:
    """T-V2.4 #4: min_universe_size < 1 raises ValueError."""
    from research.harness.aplus_v2_ohlcv_evaluator.run import run_harness

    with pytest.raises(ValueError, match="min_universe_size"):
        run_harness(
            db_path=tmp_path / "x.db",
            eval_runs=20,
            output_dir=tmp_path,
            min_universe_size=0,
        )


# ---------------------------------------------------------------------------
# Test 5: --max-runtime-seconds out-of-range ValueError + accepted
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_secs", [-1.0, 0.0])
def test_run_harness_max_runtime_seconds_nonpositive_raises_value_error(
    bad_secs: float, tmp_path: Path
) -> None:
    """T-V2.4 #5a: max_runtime_seconds <= 0 raises ValueError."""
    from research.harness.aplus_v2_ohlcv_evaluator.run import run_harness

    with pytest.raises(ValueError, match="max_runtime_seconds"):
        run_harness(
            db_path=tmp_path / "x.db",
            eval_runs=20,
            output_dir=tmp_path,
            max_runtime_seconds=bad_secs,
        )


def test_run_harness_max_runtime_seconds_accepted_as_none(
    tmp_path: Path, smoke_env
) -> None:
    """T-V2.4 #5b: max_runtime_seconds=None (default) is accepted."""
    db_path, _ = smoke_env
    out_dir = tmp_path / "out"
    from research.harness.aplus_v2_ohlcv_evaluator.run import run_harness

    md_path, csv_path = run_harness(
        db_path=db_path,
        eval_runs=3,
        output_dir=out_dir,
        max_runtime_seconds=None,
    )
    assert md_path.exists()
    assert csv_path.exists()


# ---------------------------------------------------------------------------
# Test 6: ClickException wrapping ValueError (no traceback)
# ---------------------------------------------------------------------------


def test_cli_eval_runs_out_of_range_yields_click_error_not_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-V2.4 #6: CLI surfaces ValueError as ClickException (no Traceback)."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    runner = CliRunner()
    result = runner.invoke(cli, [
        "--config", "swing.config.toml",
        "diagnose", "aplus-sensitivity-v2",
        "--db", str(tmp_path / "x.db"),
        "--eval-runs", "0",
    ])
    assert result.exit_code != 0
    combined = result.output + (getattr(result, "stderr", "") or "")
    assert "Traceback" not in combined, (
        f"Got raw traceback (expected Click error): {combined}"
    )
    # Click renders ValueError-wrapped as "Error: <message>" OR via IntRange
    # "Invalid value" (CLI uses IntRange check via Click options layer).
    assert (
        "Error" in combined
        or "Invalid value" in combined
        or "between" in combined
    ), f"Expected an error message; got: {combined}"


# ---------------------------------------------------------------------------
# Test 7: output file path conventions
# ---------------------------------------------------------------------------


def test_run_harness_output_file_path_conventions(
    tmp_path: Path, smoke_env
) -> None:
    """T-V2.4 #7: output files named aplus-sensitivity-v2-<ISO>.{csv,md}."""
    db_path, _ = smoke_env
    out_dir = tmp_path / "out"
    from research.harness.aplus_v2_ohlcv_evaluator.run import run_harness

    md_path, csv_path = run_harness(
        db_path=db_path, eval_runs=3, output_dir=out_dir
    )
    iso_pattern = re.compile(r"aplus-sensitivity-v2-\d{8}T\d{6}Z\.(md|csv)$")
    assert iso_pattern.match(md_path.name), (
        f"md filename {md_path.name!r} does not match expected pattern"
    )
    assert iso_pattern.match(csv_path.name), (
        f"csv filename {csv_path.name!r} does not match expected pattern"
    )
    assert md_path.parent == out_dir
    assert csv_path.parent == out_dir


# ---------------------------------------------------------------------------
# Test 8: baseline smoke with operator-shape fixture
# ---------------------------------------------------------------------------


def test_run_harness_baseline_smoke_emits_well_formed_csv_and_markdown(
    tmp_path: Path, smoke_env
) -> None:
    """T-V2.4 #8: baseline smoke run emits valid CSV (12 cols) + markdown."""
    db_path, _ = smoke_env
    out_dir = tmp_path / "out"
    from research.harness.aplus_v2_ohlcv_evaluator.output import _CSV_HEADERS_V2
    from research.harness.aplus_v2_ohlcv_evaluator.run import run_harness

    md_path, csv_path = run_harness(
        db_path=db_path, eval_runs=3, output_dir=out_dir
    )

    # Verify CSV has 12-col header.
    import csv as _csv
    with csv_path.open(encoding="utf-8", newline="") as fh:
        reader = _csv.DictReader(fh)
        assert list(reader.fieldnames) == list(_CSV_HEADERS_V2), (
            f"CSV headers mismatch: {reader.fieldnames}"
        )

    # Verify markdown has key sections.
    md_text = md_path.read_text(encoding="utf-8")
    assert "## Sensitivity Matrix" in md_text
    assert "## Manifest" in md_text
    # ASCII-only (cp1252 round-trip).
    md_text.encode("cp1252")


# ---------------------------------------------------------------------------
# Test 9: CLI subcommand --help smoke
# ---------------------------------------------------------------------------


def test_cli_aplus_sensitivity_v2_help_smoke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-V2.4 #9: swing diagnose aplus-sensitivity-v2 --help exits 0."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(cli, [
        "--config", "swing.config.toml",
        "diagnose", "aplus-sensitivity-v2",
        "--help",
    ])
    assert result.exit_code == 0, result.output
    assert "aplus-sensitivity-v2" in result.output or "eval-runs" in result.output


# ---------------------------------------------------------------------------
# Test 10: subprocess stdout cp1252 safety
# ---------------------------------------------------------------------------


def test_subprocess_aplus_sensitivity_v2_help_cp1252_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-V2.4 #10: subprocess stdout must be cp1252-encodable.
    Discriminating per cumulative Windows cp1252 stdout gotcha: pytest capsys
    bypasses the Windows encoder so synthetic-fixture tests pass in pytest
    but crash in production on non-ASCII output.
    """
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    proc = subprocess.run(
        [sys.executable, "-m", "swing.cli",
         "diagnose", "aplus-sensitivity-v2", "--help"],
        capture_output=True, text=True, check=False, timeout=60,
        env={**os.environ, "USERPROFILE": str(tmp_path), "HOME": str(tmp_path)},
    )
    assert proc.returncode == 0, (proc.stdout + proc.stderr)
    proc.stdout.encode("cp1252")
    proc.stderr.encode("cp1252")


# ---------------------------------------------------------------------------
# Test 11: DB opened read-only via URI mode=ro
# ---------------------------------------------------------------------------


def test_run_harness_db_connection_is_readonly_uri_mode(
    tmp_path: Path,
) -> None:
    """T-V2.4 #11: DB opened via URI mode=ro; INSERT raises OperationalError.
    Discriminating: monkey-patch run_v2_sweep to attempt INSERT within the
    connection passed from run_harness; assert sqlite3.OperationalError raised
    with 'readonly' in message (Codex R2.M2 RESOLVED + R3.m2 path-escape safe).

    The INSERT is attempted INSIDE the spy (before conn is closed by the
    finally block in run_harness) so the test catches the read-only enforcement
    at the point the connection is live.
    """
    # Plant a minimal DB (just needs to be a valid SQLite file with
    # evaluation_runs table for fetch_eval_runs to return empty list).
    db_path = tmp_path / "ro_test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE evaluation_runs ("
        "id INTEGER PRIMARY KEY, run_ts TEXT NOT NULL, "
        "data_asof_date TEXT NOT NULL, action_session_date TEXT NOT NULL, "
        "finviz_csv_path TEXT, tickers_evaluated INTEGER NOT NULL DEFAULT 0, "
        "aplus_count INTEGER NOT NULL DEFAULT 0, watch_count INTEGER NOT NULL DEFAULT 0, "
        "skip_count INTEGER NOT NULL DEFAULT 0, excluded_count INTEGER NOT NULL DEFAULT 0, "
        "error_count INTEGER NOT NULL DEFAULT 0)"
    )
    conn.commit()
    conn.close()

    # Monkeypatch run_v2_sweep to attempt a write via the connection INSIDE the
    # spy (while the conn is still live, before run_harness closes it).
    write_error: list[sqlite3.OperationalError] = []

    def _spy_sweep(conn_arg, **kwargs):
        # Attempt INSERT inside the spy to verify the connection is read-only.
        try:
            conn_arg.execute(
                "INSERT INTO evaluation_runs "
                "(id, run_ts, data_asof_date, action_session_date, "
                "tickers_evaluated, aplus_count, watch_count, "
                "skip_count, excluded_count, error_count) "
                "VALUES (999, 'x', 'x', 'x', 0, 0, 0, 0, 0, 0)"
            )
        except sqlite3.OperationalError as exc:
            write_error.append(exc)

        # Return minimal valid SweepResultV2 (empty-DB short-circuit shape).
        from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import BothExistDiagnostic
        from research.harness.aplus_v2_ohlcv_evaluator.sweep import (
            BaselineParityReport,
            SweepResultV2,
        )
        return SweepResultV2(
            eval_runs_window=kwargs.get("eval_runs_window", 20),
            eval_run_id_range=(0, 0),
            total_candidates=0,
            universe_size=0,
            v2_universe_hash="empty_no_eval_runs",
            entries=(),
            flipped=(),
            baseline_parity=BaselineParityReport(
                tier1_match=True,
                tier1_mismatch_candidates=(),
                tier2_match_count=0,
                tier2_mismatch_count=0,
                tier2_via_surrogate_count=0,
            ),
            ohlcv_coverage_skip_count=0,
            universe_skipped_ticker_count=0,
            both_exist_diagnostic=BothExistDiagnostic(),
            runtime_seconds=0.0,
            truncated_by_runtime_cap=False,
        )

    import unittest.mock as _mock

    out_dir = tmp_path / "out"
    with _mock.patch(
        "research.harness.aplus_v2_ohlcv_evaluator.run.run_v2_sweep",
        side_effect=_spy_sweep,
    ):
        from research.harness.aplus_v2_ohlcv_evaluator.run import run_harness

        run_harness(db_path=db_path, eval_runs=20, output_dir=out_dir)

    # The spy must have captured exactly one OperationalError with "readonly".
    assert len(write_error) == 1, (
        f"Expected 1 readonly OperationalError; got {len(write_error)} errors: {write_error}"
    )
    assert "readonly" in str(write_error[0]).lower(), (
        f"Expected 'readonly' in error message; got: {write_error[0]}"
    )


# ---------------------------------------------------------------------------
# Test 11b (discriminating): tracemalloc stopped on sweep exception path
# ---------------------------------------------------------------------------


def test_run_harness_tracemalloc_stopped_when_sweep_raises(
    tmp_path: Path,
) -> None:
    """T-V2.4 #11b: tracemalloc.stop() is called even when run_v2_sweep raises.

    Discriminating test for the tracemalloc-not-stopped-on-exception bug.
    Pre-fix: tracemalloc.stop() is inside the try block BEFORE the exception
    propagates the finally; tracemalloc remains tracing after the call.
    Post-fix: nested try/finally guarantees stop() runs on the exception path.

    Invariant: tracemalloc.is_tracing() == False after run_harness raises.
    """
    import tracemalloc
    import unittest.mock as _mock

    # Plant a minimal valid SQLite file so URI-mode open succeeds.
    db_path = tmp_path / "fail_test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE evaluation_runs ("
        "id INTEGER PRIMARY KEY, run_ts TEXT NOT NULL, "
        "data_asof_date TEXT NOT NULL, action_session_date TEXT NOT NULL, "
        "finviz_csv_path TEXT, tickers_evaluated INTEGER NOT NULL DEFAULT 0, "
        "aplus_count INTEGER NOT NULL DEFAULT 0, watch_count INTEGER NOT NULL DEFAULT 0, "
        "skip_count INTEGER NOT NULL DEFAULT 0, excluded_count INTEGER NOT NULL DEFAULT 0, "
        "error_count INTEGER NOT NULL DEFAULT 0)"
    )
    conn.commit()
    conn.close()

    # Ensure tracemalloc is NOT tracing before we start.
    if tracemalloc.is_tracing():
        tracemalloc.stop()
    assert not tracemalloc.is_tracing(), "Precondition: tracemalloc should not be tracing"

    class _SweepError(RuntimeError):
        pass

    def _raising_sweep(*args, **kwargs):
        raise _SweepError("deliberate failure for tracemalloc test")

    with _mock.patch(
        "research.harness.aplus_v2_ohlcv_evaluator.run.run_v2_sweep",
        side_effect=_raising_sweep,
    ):
        from research.harness.aplus_v2_ohlcv_evaluator.run import run_harness

        with pytest.raises(_SweepError, match="deliberate failure"):
            run_harness(db_path=db_path, eval_runs=20, output_dir=tmp_path / "out")

    # KEY ASSERTION: tracemalloc must NOT still be tracing after the exception.
    assert not tracemalloc.is_tracing(), (
        "tracemalloc.stop() was not called on the exception path; "
        "tracemalloc is still tracing after run_harness raised."
    )


# ---------------------------------------------------------------------------
# Test 12 (bonus): V1 back-compat --help unchanged (OQ-10)
# ---------------------------------------------------------------------------


def test_v1_aplus_sensitivity_help_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-V2.4 #12 (bonus): V1 swing diagnose aplus-sensitivity --help still works."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(cli, [
        "--config", "swing.config.toml",
        "diagnose", "aplus-sensitivity",
        "--help",
    ])
    assert result.exit_code == 0, result.output
    # V1 help text should mention the V1 sweep.
    assert "sensitivity" in result.output.lower()


# ---------------------------------------------------------------------------
# Test 13 (bonus): git diff swing/ gate (env-var guarded per plan §G T-V2.4.8)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("SWING_TRADING_V2_GIT_DIFF_GATE_ENABLED"),
    reason="Set SWING_TRADING_V2_GIT_DIFF_GATE_ENABLED=1 to enable git diff gate",
)
def test_v2_only_modifies_swing_cli_py_file() -> None:
    """T-V2.4 #13 (bonus): git diff main -- swing/ shows ONLY swing/cli.py.
    Guarded by SWING_TRADING_V2_GIT_DIFF_GATE_ENABLED env var per plan §G.
    """
    proc = subprocess.run(
        ["git", "diff", "--name-only", "main", "--", "swing/"],
        capture_output=True, text=True, check=False, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    modified = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    assert modified == ["swing/cli.py"], (
        f"Expected only swing/cli.py; got: {modified}"
    )
