"""Tests for pattern cohort harness run.py orchestrator + CLI registration."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from research.harness.pattern_cohort_evaluator.exceptions import (
    BothCohortModesSuppliedError,
    NeitherCohortModeSuppliedError,
)
from research.harness.pattern_cohort_evaluator.run import (
    _resolve_cohort,
    run_harness,
)

# ---------------------------------------------------------------------------
# _resolve_cohort
# ---------------------------------------------------------------------------

def test_resolve_cohort_both_modes_raises():
    with pytest.raises(BothCohortModesSuppliedError):
        _resolve_cohort(
            cohort_csv=Path("/tmp/whatever.csv"),
            cohort_inline="RLMD:2026-04-15",
        )


def test_resolve_cohort_neither_mode_raises():
    with pytest.raises(NeitherCohortModeSuppliedError):
        _resolve_cohort(cohort_csv=None, cohort_inline=None)


def test_resolve_cohort_inline_returns_entries():
    entries, mode, path = _resolve_cohort(
        cohort_csv=None, cohort_inline="RLMD:2026-04-15",
    )
    assert mode == "inline"
    assert path is None
    assert len(entries) == 1
    assert entries[0].ticker == "RLMD"


def test_resolve_cohort_csv_returns_entries(tmp_path):
    p = tmp_path / "cohort.csv"
    p.write_text("ticker,asof_date\nRLMD,2026-04-15\n", encoding="utf-8")
    entries, mode, path = _resolve_cohort(cohort_csv=p, cohort_inline=None)
    assert mode == "csv"
    assert path == p
    assert len(entries) == 1


# ---------------------------------------------------------------------------
# run_harness validation gates
# ---------------------------------------------------------------------------

def test_run_harness_bad_window_mode_raises(tmp_path):
    with pytest.raises(ValueError, match="window_mode"):
        run_harness(
            cohort_csv=None, cohort_inline="RLMD:2026-04-15",
            db_path=tmp_path / "db.sqlite",
            output_dir=tmp_path,
            window_mode="bogus",
        )


def test_run_harness_bad_template_match_mode_raises(tmp_path):
    with pytest.raises(ValueError, match="template_match_mode"):
        run_harness(
            cohort_csv=None, cohort_inline="RLMD:2026-04-15",
            db_path=tmp_path / "db.sqlite",
            output_dir=tmp_path,
            template_match_mode="bogus",
        )


def test_run_harness_unknown_pattern_class_filter_raises(tmp_path):
    with pytest.raises(ValueError, match="unknown pattern_class"):
        run_harness(
            cohort_csv=None, cohort_inline="RLMD:2026-04-15",
            db_path=tmp_path / "db.sqlite",
            output_dir=tmp_path,
            cli_pattern_class_filter=("not_a_real_class",),
        )


# ---------------------------------------------------------------------------
# run_harness end-to-end with stubbed invoke_cohort
# ---------------------------------------------------------------------------

def _make_min_db(path: Path) -> None:
    """Write a minimal sqlite DB with the schemas run_harness's invoke_cohort
    needs (pattern_exemplars + candidates + evaluation_runs + candidate_criteria).
    Empty tables; harness emits header-only CSV.
    """
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


def test_run_harness_writes_three_files_under_timestamped_dir(tmp_path, monkeypatch):
    """End-to-end: run_harness emits results.csv + summary.md + manifest.json
    under a fresh `pattern-cohort-detection-<ISO>/` subdir."""
    db_path = tmp_path / "swing.db"
    _make_min_db(db_path)
    cache_dir = tmp_path / "prices_cache"
    cache_dir.mkdir()
    output_dir = tmp_path / "exports"

    fake_cfg = SimpleNamespace(paths=SimpleNamespace(prices_cache_dir=cache_dir))
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.run._get_cfg",
        lambda: fake_cfg,
    )

    csv_p, md_p, manifest_p = run_harness(
        cohort_csv=None,
        cohort_inline="ZZNONE:2026-04-15",  # no archive -> coverage_skip
        db_path=db_path,
        output_dir=output_dir,
        window_mode="per-window",
        template_match_mode="off",
    )
    assert csv_p.exists()
    assert md_p.exists()
    assert manifest_p.exists()
    assert csv_p.parent.name.startswith("pattern-cohort-detection-")
    assert csv_p.name == "results.csv"
    assert md_p.name == "summary.md"
    assert manifest_p.name == "manifest.json"

    # Manifest sanity
    manifest = json.loads(manifest_p.read_text())
    assert manifest["l2_lock_preserved"] is True
    assert manifest["cohort_input_mode"] == "inline"
    assert manifest["cohort_entries_count"] == 1
    assert manifest["skipped_entries"]["coverage_skip"] == 1


def test_run_harness_csv_mode_propagates_sha(tmp_path, monkeypatch):
    db_path = tmp_path / "swing.db"
    _make_min_db(db_path)
    cache_dir = tmp_path / "prices_cache"
    cache_dir.mkdir()
    cohort_csv = tmp_path / "cohort.csv"
    cohort_csv.write_text("ticker,asof_date\nZZNONE,2026-04-15\n", encoding="utf-8")

    fake_cfg = SimpleNamespace(paths=SimpleNamespace(prices_cache_dir=cache_dir))
    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.run._get_cfg",
        lambda: fake_cfg,
    )

    _csv_p, _md_p, manifest_p = run_harness(
        cohort_csv=cohort_csv,
        cohort_inline=None,
        db_path=db_path,
        output_dir=tmp_path / "exports",
        window_mode="per-window",
        template_match_mode="off",
    )
    manifest = json.loads(manifest_p.read_text())
    assert manifest["cohort_input_mode"] == "csv"
    assert manifest["cohort_input_sha256"] is not None
    assert len(manifest["cohort_input_sha256"]) == 64


# ---------------------------------------------------------------------------
# CLI subcommand registration (OQ-13 carve-out)
# ---------------------------------------------------------------------------

def test_cli_subcommand_registered():
    """OQ-13: `swing diagnose pattern-cohort-detect` exists in CLI."""
    from click.testing import CliRunner

    from swing.cli import main as cli
    runner = CliRunner()
    result = runner.invoke(cli, ["diagnose", "pattern-cohort-detect", "--help"])
    assert result.exit_code == 0
    assert "pattern-cohort-detect" in result.output.lower() or \
           "Pattern cohort" in result.output


def test_cli_subcommand_requires_db(tmp_path):
    from click.testing import CliRunner

    from swing.cli import main as cli
    runner = CliRunner()
    result = runner.invoke(
        cli, ["diagnose", "pattern-cohort-detect", "--cohort-inline", "RLMD:2026-04-15"],
    )
    assert result.exit_code != 0
    assert "--db" in result.output


def test_cli_subcommand_both_modes_rejected(tmp_path, monkeypatch):
    """Both --cohort-csv AND --cohort-inline supplied -> ClickException."""
    from click.testing import CliRunner

    from swing.cli import main as cli
    db_path = tmp_path / "swing.db"
    _make_min_db(db_path)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cohort_csv = tmp_path / "cohort.csv"
    cohort_csv.write_text("ticker,asof_date\nA,2026-04-15\n", encoding="utf-8")

    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.run._get_cfg",
        lambda: SimpleNamespace(paths=SimpleNamespace(prices_cache_dir=cache_dir)),
    )

    runner = CliRunner()
    result = runner.invoke(cli, [
        "diagnose", "pattern-cohort-detect",
        "--db", str(db_path),
        "--cohort-csv", str(cohort_csv),
        "--cohort-inline", "RLMD:2026-04-15",
        "--output-dir", str(tmp_path / "out"),
    ])
    assert result.exit_code != 0
    assert "both supplied" in result.output.lower() or \
           "Exactly one" in result.output


def test_cli_subcommand_neither_mode_rejected(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from swing.cli import main as cli
    db_path = tmp_path / "swing.db"
    _make_min_db(db_path)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.run._get_cfg",
        lambda: SimpleNamespace(paths=SimpleNamespace(prices_cache_dir=cache_dir)),
    )

    runner = CliRunner()
    result = runner.invoke(cli, [
        "diagnose", "pattern-cohort-detect",
        "--db", str(db_path),
        "--output-dir", str(tmp_path / "out"),
    ])
    assert result.exit_code != 0
    assert "neither supplied" in result.output.lower() or \
           "Exactly one" in result.output


def test_cli_subcommand_happy_path(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from swing.cli import main as cli
    db_path = tmp_path / "swing.db"
    _make_min_db(db_path)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    output_dir = tmp_path / "out"

    monkeypatch.setattr(
        "research.harness.pattern_cohort_evaluator.run._get_cfg",
        lambda: SimpleNamespace(paths=SimpleNamespace(prices_cache_dir=cache_dir)),
    )

    runner = CliRunner()
    result = runner.invoke(cli, [
        "diagnose", "pattern-cohort-detect",
        "--db", str(db_path),
        "--cohort-inline", "ZZNONE:2026-04-15",
        "--output-dir", str(output_dir),
        "--template-match", "off",
    ])
    assert result.exit_code == 0, f"stdout={result.output}\nexc={result.exception}"
    assert "Results CSV:" in result.output
    assert "Summary MD:" in result.output
    assert "Manifest:" in result.output
