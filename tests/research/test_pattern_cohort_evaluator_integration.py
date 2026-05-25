"""Integration tests for pattern cohort harness — end-to-end through CLI."""
from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from click.testing import CliRunner

from swing.cli import main as cli


def _make_min_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE pattern_exemplars (
            id INTEGER PRIMARY KEY,
            ticker TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            proposed_pattern_class TEXT NOT NULL,
            final_pattern_class TEXT,
            label_source TEXT NOT NULL,
            label_source_actor TEXT NOT NULL,
            final_decision TEXT NOT NULL,
            labeler_evidence_json TEXT,
            reviewer_evidence_json TEXT,
            review_state TEXT NOT NULL,
            review_state_changed_ts TEXT,
            reviewed_ts TEXT,
            created_ts TEXT NOT NULL,
            silver_decision TEXT,
            silver_decided_ts TEXT,
            cli_filter_signature_hash TEXT,
            reviewer_decision TEXT,
            structural_evidence_json TEXT
        );
        CREATE TABLE evaluation_runs (
            id INTEGER PRIMARY KEY,
            session_date TEXT NOT NULL,
            started_ts TEXT NOT NULL
        );
        CREATE TABLE candidates (
            id INTEGER PRIMARY KEY,
            evaluation_run_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            bucket TEXT NOT NULL
        );
        CREATE TABLE candidate_criteria (
            id INTEGER PRIMARY KEY,
            candidate_id INTEGER NOT NULL,
            criterion_key TEXT NOT NULL,
            pass_flag INTEGER NOT NULL
        );
    """)
    conn.commit()
    conn.close()


def _make_shape_a_parquet(path: Path, n_bars: int = 250):
    dates = pd.date_range(end="2026-04-30", periods=n_bars, freq="B")
    df = pd.DataFrame({
        "asof_date": [d.date().isoformat() for d in dates],
        "open": [100.0] * n_bars,
        "high": [101.0] * n_bars,
        "low": [99.0] * n_bars,
        "close": [100.0] * n_bars,
        "volume": [1_000_000] * n_bars,
    })
    df.to_parquet(path, index=False)


# ---------------------------------------------------------------------------
# E2E synthetic 3-ticker cohort -- all 3 will land coverage_skip since no
# Shape A archives planted in tmp cache_dir (skip-discipline E2E exercise)
# ---------------------------------------------------------------------------

def test_e2e_synthetic_3_ticker_cohort_skips_emit_audit_rows(tmp_path, monkeypatch):
    db = tmp_path / "swing.db"
    _make_min_db(db)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.run._get_cfg",
        lambda: SimpleNamespace(paths=SimpleNamespace(prices_cache_dir=cache_dir)),
    )

    runner = CliRunner()
    result = runner.invoke(cli, [
        "diagnose", "pattern-cohort-detect",
        "--db", str(db),
        "--cohort-inline", "RLMD:2026-04-15,DNTH:2026-04-15,RNG:2026-04-15",
        "--output-dir", str(tmp_path / "out"),
        "--template-match", "off",
    ])
    assert result.exit_code == 0, result.output

    # Locate the timestamped output dir
    out_dirs = list((tmp_path / "out").glob("pattern-cohort-detection-*"))
    assert len(out_dirs) == 1
    out = out_dirs[0]
    assert (out / "results.csv").exists()
    assert (out / "summary.md").exists()
    assert (out / "manifest.json").exists()

    # Manifest l2_lock_preserved + skip counters
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["l2_lock_preserved"] is True
    assert manifest["cohort_entries_count"] == 3
    assert manifest["cohort_unique_tickers_count"] == 3
    assert manifest["skipped_entries"]["coverage_skip"] == 3

    # Per gotcha #27 silent-skip-without-audit discipline: skip rows MUST
    # appear in CSV as audit rows (3 rows + 1 header).
    with (out / "results.csv").open() as f:
        rows = list(csv.reader(f))
    assert len(rows) == 4
    skip_col = rows[0].index("skip_reason")
    skip_reasons = [r[skip_col] for r in rows[1:]]
    assert all(s == "coverage_skip" for s in skip_reasons)


# ---------------------------------------------------------------------------
# Idempotency: two runs against same fixture -> identical results CSV bytes
# ---------------------------------------------------------------------------

def test_e2e_idempotent_against_static_fixture(tmp_path, monkeypatch):
    """Per spec §D.6 + §F.4: identical input -> byte-equal results.csv."""
    db = tmp_path / "swing.db"
    _make_min_db(db)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.run._get_cfg",
        lambda: SimpleNamespace(paths=SimpleNamespace(prices_cache_dir=cache_dir)),
    )

    runner = CliRunner()

    def _run(out_subdir: str) -> Path:
        result = runner.invoke(cli, [
            "diagnose", "pattern-cohort-detect",
            "--db", str(db),
            "--cohort-inline", "X:2026-04-15,Y:2026-04-15",
            "--output-dir", str(tmp_path / out_subdir),
            "--template-match", "off",
        ])
        assert result.exit_code == 0, result.output
        out_dirs = list((tmp_path / out_subdir).glob("pattern-cohort-detection-*"))
        assert len(out_dirs) == 1
        return out_dirs[0]

    out_a = _run("a")
    out_b = _run("b")
    assert (out_a / "results.csv").read_bytes() == (out_b / "results.csv").read_bytes()


# ---------------------------------------------------------------------------
# pattern-class filter via CLI
# ---------------------------------------------------------------------------

def test_e2e_pattern_class_filter_via_cli_accepts_known_classes(tmp_path, monkeypatch):
    db = tmp_path / "swing.db"
    _make_min_db(db)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.run._get_cfg",
        lambda: SimpleNamespace(paths=SimpleNamespace(prices_cache_dir=cache_dir)),
    )

    runner = CliRunner()
    result = runner.invoke(cli, [
        "diagnose", "pattern-cohort-detect",
        "--db", str(db),
        "--cohort-inline", "X:2026-04-15",
        "--output-dir", str(tmp_path / "out"),
        "--template-match", "off",
        "--pattern-class-filter", "vcp,flat_base",
    ])
    assert result.exit_code == 0, result.output


def test_e2e_pattern_class_filter_via_cli_rejects_unknown(tmp_path, monkeypatch):
    db = tmp_path / "swing.db"
    _make_min_db(db)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.run._get_cfg",
        lambda: SimpleNamespace(paths=SimpleNamespace(prices_cache_dir=cache_dir)),
    )

    runner = CliRunner()
    result = runner.invoke(cli, [
        "diagnose", "pattern-cohort-detect",
        "--db", str(db),
        "--cohort-inline", "X:2026-04-15",
        "--output-dir", str(tmp_path / "out"),
        "--pattern-class-filter", "not_a_real_class",
    ])
    assert result.exit_code != 0
    assert "unknown pattern_class" in result.output.lower()


# ---------------------------------------------------------------------------
# brief-framing first-cohort target size lock (per spec §F.7)
# ---------------------------------------------------------------------------

def test_e2e_brief_framing_first_cohort_target_size():
    """Skip if the operator-supplied cohort CSV is not yet committed.

    Per spec §F.7 + OQ-9 LOCK + cumulative gotcha #27 brief-framing-accuracy:
    when committed, the cohort CSV must have exactly 67 rows + 15 unique tickers.
    """
    cohort_csv = (
        Path(__file__).resolve().parents[2]
        / "exports" / "research" / "cohorts" / "tightness_1.005_flips_67.csv"
    )
    if not cohort_csv.exists():
        pytest.skip(
            "operator-supplied first-cohort CSV not yet committed at "
            f"{cohort_csv}; awaiting operator smoke run per spec §L.4",
        )
    with cohort_csv.open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 67, f"first-cohort size drift: {len(rows)} != 67"
    tickers = {r["ticker"].upper() for r in rows}
    assert len(tickers) == 15, f"first-cohort unique-ticker drift: {len(tickers)} != 15"
