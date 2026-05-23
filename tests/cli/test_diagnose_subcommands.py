"""T-T4.SB.1 §B.1 Sub-task 1G — ``swing diagnose`` CLI subcommand tests."""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

# NOTE: project CLI group is named ``main`` per swing/cli.py (entry-point
# `swing = "swing.cli:main"` in pyproject.toml). Plan §B.1 step 1G.1 wrote
# `from swing.cli import cli` but the project convention (see e.g.
# tests/cli/test_cli_advisory.py + test_cli_pipeline.py) imports ``main``.
from swing.cli import main as cli

# ---------------------------------------------------------------------------
# Inline fixture helpers (plant production-shape DB rows matching
# swing/data/migrations/0001_phase1_initial.sql).
# ---------------------------------------------------------------------------

_SCHEMA_DDL = (
    """
    CREATE TABLE evaluation_runs (
      id INTEGER PRIMARY KEY,
      run_ts TEXT NOT NULL,
      data_asof_date TEXT NOT NULL,
      action_session_date TEXT NOT NULL,
      finviz_csv_path TEXT,
      tickers_evaluated INTEGER NOT NULL,
      aplus_count INTEGER NOT NULL,
      watch_count INTEGER NOT NULL,
      skip_count INTEGER NOT NULL,
      excluded_count INTEGER NOT NULL,
      error_count INTEGER NOT NULL
    );
    """,
    """
    CREATE TABLE candidates (
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
    );
    """,
    """
    CREATE TABLE candidate_criteria (
      candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
      criterion_name TEXT NOT NULL,
      layer TEXT NOT NULL CHECK (layer IN ('trend_template','vcp','risk')),
      result TEXT NOT NULL CHECK (result IN ('pass','fail','na')),
      value TEXT,
      rule TEXT,
      PRIMARY KEY (candidate_id, criterion_name)
    );
    """,
)


def _plant_minimal_db(conn: sqlite3.Connection) -> None:
    for ddl in _SCHEMA_DDL:
        conn.execute(ddl)
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, action_session_date,"
        " tickers_evaluated, aplus_count, watch_count, skip_count, excluded_count,"
        " error_count) VALUES (1, '2026-05-22T00:00:00Z', '2026-05-21', '2026-05-22',"
        " 0, 0, 0, 0, 0, 0)"
    )
    # 1 aplus + 2 watch + 1 skip candidate with criteria.
    fixtures = [
        ("A0", "aplus", 7, ("TT8_rs_rank",), 0, True),
        ("W0", "watch", 8, (), 1, True),
        ("W1", "watch", 8, (), 2, True),
        ("S0", "skip", 8, (), 0, False),
    ]
    for i, (ticker, bucket, tt_pass, tt_fail, vcp_fails, risk_ok) in enumerate(
        fixtures, start=1,
    ):
        conn.execute(
            "INSERT INTO candidates (id, evaluation_run_id, ticker, bucket,"
            " rs_method) VALUES (?, 1, ?, ?, 'universe')",
            (i, ticker, bucket),
        )
        tt_names = [
            "TT1", "TT2", "TT3", "TT4", "TT5", "TT6", "TT7", "TT8_rs_rank",
        ]
        fail_set = set(tt_fail)
        pass_count = 0
        for name in tt_names:
            if name in fail_set:
                result = "fail"
            elif pass_count < tt_pass:
                result = "pass"
                pass_count += 1
            else:
                result = "fail"
            conn.execute(
                "INSERT INTO candidate_criteria (candidate_id, criterion_name,"
                " layer, result) VALUES (?, ?, 'trend_template', ?)",
                (i, name, result),
            )
        vcp_names = [
            "vcp_prior_trend", "vcp_adr", "vcp_pullback", "vcp_proximity",
            "vcp_tightness_days", "vcp_tightness_range",
            "vcp_orderliness_bar", "vcp_orderliness_cv",
        ]
        for j, name in enumerate(vcp_names):
            result = "fail" if j < vcp_fails else "pass"
            conn.execute(
                "INSERT INTO candidate_criteria (candidate_id, criterion_name,"
                " layer, result) VALUES (?, ?, 'vcp', ?)",
                (i, name, result),
            )
        conn.execute(
            "INSERT INTO candidate_criteria (candidate_id, criterion_name,"
            " layer, result) VALUES (?, 'risk_max_pct', 'risk', ?)",
            (i, "pass" if risk_ok else "fail"),
        )
    conn.commit()


@pytest.fixture
def cfg_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Repo-root swing.config.toml works fine for the CLI's ``--config`` -- but
    the CLI's group also runs the TOML-divergence hook which reads user-config.
    Monkeypatch USERPROFILE + HOME to ``tmp_path`` to keep the hook isolated
    (per the existing cumulative gotcha)."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    return Path("swing.config.toml")


def test_diagnose_aplus_sensitivity_invokes_harness(
    cfg_path: Path, tmp_path: Path,
) -> None:
    db_path = tmp_path / "harness.db"
    conn = sqlite3.connect(str(db_path))
    _plant_minimal_db(conn)
    conn.close()
    out_dir = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(cli, [
        "--config", str(cfg_path),
        "diagnose", "aplus-sensitivity",
        "--db", str(db_path),
        "--eval-runs", "10",
        "--output-dir", str(out_dir),
    ])
    assert result.exit_code == 0, result.output
    csvs = list(out_dir.glob("aplus-sensitivity-*.csv"))
    mds = list(out_dir.glob("aplus-sensitivity-*.md"))
    assert len(csvs) == 1
    assert len(mds) == 1


def test_diagnose_aplus_sensitivity_rejects_eval_runs_out_of_range(
    cfg_path: Path, tmp_path: Path,
) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, [
        "--config", str(cfg_path),
        "diagnose", "aplus-sensitivity",
        "--db", str(tmp_path / "x.db"),
        "--eval-runs", "0",
    ])
    assert result.exit_code != 0
    combined = result.output + (getattr(result, "stderr", "") or "")
    assert (
        "between 1 and 100" in combined
        or "1<=" in combined
        or "Invalid value" in combined
    )


def test_diagnose_metrics_wiring_emits_markdown(
    cfg_path: Path, tmp_path: Path,
) -> None:
    runner = CliRunner()
    out_path = tmp_path / "audit.md"
    # Codex R1 m#2: --db must exist (no auto-create); plant an empty
    # SQLite file (the V1 audit ignores conn per V1 stub but the
    # pre-validation gate requires the file to be present).
    db_path = tmp_path / "empty.db"
    sqlite3.connect(str(db_path)).close()
    result = runner.invoke(cli, [
        "--config", str(cfg_path),
        "diagnose", "metrics-wiring",
        "--db", str(db_path),
        "--output", str(out_path),
    ])
    assert result.exit_code == 0, result.output
    text = out_path.read_text(encoding="utf-8")
    text.encode("cp1252")
    assert "| Surface | File:line |" in text


def test_diagnose_aplus_sensitivity_stdout_is_ascii_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Subprocess invocation through PowerShell-equivalent path verifies
    stdout cp1252 safety per the cumulative Windows-stdout gotcha (pytest
    capsys bypasses the Windows encoder so a synthetic-fixture test that
    passes in pytest may still crash in production)."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    db_path = tmp_path / "harness.db"
    conn = sqlite3.connect(str(db_path))
    _plant_minimal_db(conn)
    conn.close()
    out_dir = tmp_path / "out"
    proc = subprocess.run(
        [sys.executable, "-m", "swing.cli",
         "diagnose", "aplus-sensitivity",
         "--db", str(db_path),
         "--eval-runs", "5",
         "--output-dir", str(out_dir)],
        capture_output=True, text=True, check=False, timeout=120,
    )
    assert proc.returncode == 0, (proc.stdout + proc.stderr)
    # Stdout must be cp1252-encodable (Windows safety).
    proc.stdout.encode("cp1252")
    proc.stderr.encode("cp1252")


def test_diagnose_aplus_sensitivity_v2_help_smoke(
    cfg_path: Path, tmp_path: Path,
) -> None:
    """V2 subcommand registered + --help exits 0 per OQ-10 CLI surface name."""
    runner = CliRunner()
    result = runner.invoke(cli, [
        "--config", str(cfg_path),
        "diagnose", "aplus-sensitivity-v2",
        "--help",
    ])
    assert result.exit_code == 0, result.output
    assert "aplus-sensitivity-v2" in result.output or "eval-runs" in result.output


def test_diagnose_aplus_sensitivity_v2_eval_runs_out_of_range(
    cfg_path: Path, tmp_path: Path,
) -> None:
    """V2 subcommand rejects --eval-runs 0 per Click IntRange(1, 100)."""
    runner = CliRunner()
    result = runner.invoke(cli, [
        "--config", str(cfg_path),
        "diagnose", "aplus-sensitivity-v2",
        "--db", str(tmp_path / "x.db"),
        "--eval-runs", "0",
    ])
    assert result.exit_code != 0
    combined = result.output + (getattr(result, "stderr", "") or "")
    assert (
        "between 1 and 100" in combined
        or "1<=" in combined
        or "Invalid value" in combined
    )
