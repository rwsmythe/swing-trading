"""End-to-end smoke test for the Finviz-pool aggregation CLI.

Schema-applied SQLite DB pre-populated with a small set of qualifying +
skipped evaluation_runs and a tmp finviz-inbox. Asserts CSV schemas and
manifest fields per D1 §"Outputs" and §"Provenance commitments".
"""
from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

import pytest

from research.finviz_pool_analysis.run import run_finviz_pool_aggregation
from swing.data.db import ensure_schema
from swing.data.models import Candidate, CriterionResult, EvaluationRun
from swing.data.repos.candidates import insert_candidates, insert_evaluation_run


_TT_NAMES = (
    "TT1_above_150_200",
    "TT2_150_above_200",
    "TT3_200_rising",
    "TT4_50_above_150_200",
    "TT5_above_50",
    "TT6_above_52w_low_30pct",
    "TT7_within_52w_high_25pct",
    "TT8_rs_rank",
)
_VCP_NAMES = (
    "prior_trend",
    "ma_stack_10_20_50",
    "ma_short_rising",
    "proximity_20ma",
    "adr",
    "pullback",
    "tightness",
    "vcp_volume_contraction",
    "orderliness",
)
_RISK_NAMES = ("risk_feasibility",)


def _crits(overrides: dict[str, str] | None = None) -> tuple[CriterionResult, ...]:
    overrides = overrides or {}
    out = []
    for name in _TT_NAMES:
        out.append(CriterionResult(name, "trend_template", overrides.get(name, "pass")))
    for name in _VCP_NAMES:
        out.append(CriterionResult(name, "vcp", overrides.get(name, "pass")))
    for name in _RISK_NAMES:
        out.append(CriterionResult(name, "risk", overrides.get(name, "pass")))
    return tuple(out)


def _candidate(
    *, ticker: str, bucket: str, overrides: dict[str, str] | None = None
) -> Candidate:
    return Candidate(
        ticker=ticker,
        bucket=bucket,
        close=10.0,
        pivot=None,
        initial_stop=None,
        adr_pct=None,
        tight_streak=None,
        pullback_pct=None,
        prior_trend_pct=None,
        rs_rank=None,
        rs_return_12w_vs_spy=None,
        rs_method="universe",
        pattern_tag=None,
        notes=None,
        criteria=_crits(overrides),
    )


@pytest.fixture
def populated_db(tmp_path: Path) -> tuple[Path, Path]:
    """Returns (db_path, finviz_inbox_dir). Two qualifying runs + one
    skipped (CSV missing)."""
    db_path = tmp_path / "fpa.db"
    conn = ensure_schema(db_path)
    conn.close()

    inbox = tmp_path / "finviz-inbox"
    (inbox / "rejected").mkdir(parents=True)
    (inbox / "finviz20Apr2026.csv").write_text("ignored\n")
    (inbox / "finviz21Apr2026.csv").write_text("ignored\n")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        # Run 1 — qualifying (CSV present): 1 aplus, 2 watch (defensible+incompatible).
        rid1 = insert_evaluation_run(
            conn,
            EvaluationRun(
                id=None,
                run_ts="2026-04-20T15:00",
                data_asof_date="2026-04-20",
                action_session_date="2026-04-21",
                finviz_csv_path="data/finviz-inbox/finviz20Apr2026.csv",
                tickers_evaluated=3,
                aplus_count=1,
                watch_count=2,
                skip_count=0,
                excluded_count=0,
                error_count=0,
            ),
        )
        insert_candidates(
            conn,
            rid1,
            [
                _candidate(ticker="A", bucket="aplus"),
                _candidate(
                    ticker="B", bucket="watch", overrides={"proximity_20ma": "fail"}
                ),
                _candidate(
                    ticker="C", bucket="watch", overrides={"adr": "fail", "tightness": "fail"}
                ),
            ],
        )
        # Run 2 — qualifying: 1 watch (defensible).
        rid2 = insert_evaluation_run(
            conn,
            EvaluationRun(
                id=None,
                run_ts="2026-04-21T15:00",
                data_asof_date="2026-04-21",
                action_session_date="2026-04-22",
                finviz_csv_path="data/finviz-inbox/finviz21Apr2026.csv",
                tickers_evaluated=1,
                aplus_count=0,
                watch_count=1,
                skip_count=0,
                excluded_count=0,
                error_count=0,
            ),
        )
        insert_candidates(
            conn,
            rid2,
            [
                _candidate(
                    ticker="D", bucket="watch", overrides={"proximity_20ma": "fail"}
                ),
            ],
        )
        # Run 3 — SKIPPED (CSV missing).
        insert_evaluation_run(
            conn,
            EvaluationRun(
                id=None,
                run_ts="2026-04-19T15:00",
                data_asof_date="2026-04-19",
                action_session_date="2026-04-20",
                finviz_csv_path="data/finviz-inbox/finviz_does_not_exist.csv",
                tickers_evaluated=0,
                aplus_count=0,
                watch_count=0,
                skip_count=0,
                excluded_count=0,
                error_count=0,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return db_path, inbox


def test_run_emits_all_required_outputs(populated_db, tmp_path):
    db_path, inbox = populated_db
    out = tmp_path / "out"
    result = run_finviz_pool_aggregation(
        db_path=db_path,
        finviz_inbox_dir=inbox,
        output_dir=out,
        repo_root=Path("."),
    )

    expected_files = {
        "per_criterion_blockers.csv",
        "bucket_distribution.csv",
        "per_run_summary.csv",
        "near_aplus_defensible_sample.csv",
        "near_aplus_incompatible_sample.csv",
        "run_manifest.json",
    }
    actual_files = {p.name for p in out.iterdir()}
    assert expected_files == actual_files

    # Bucket distribution CSV schema.
    with (out / "bucket_distribution.csv").open() as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["bucket", "count", "fraction_of_evaluations"]
    bucket_data = {row[0]: row[1] for row in rows[1:] if row[0] != "watch_aplus_ratio_overall"}
    assert bucket_data["aplus"] == "1"
    assert bucket_data["watch"] == "3"

    # Manifest fields.
    manifest = json.loads((out / "run_manifest.json").read_text())
    assert manifest["qualifying_run_count"] == 2
    assert manifest["skipped_run_count"] == 1
    assert manifest["total_evaluations"] == 4
    assert manifest["near_aplus_defensible_count"] == 2  # B + D
    assert manifest["near_aplus_incompatible_count"] == 1  # C
    assert manifest["doctrine_defensible_miss_set"] == sorted(
        ["TT8_rs_rank", "risk_feasibility", "proximity_20ma"]
    )
    # action_session_date_range = (2026-04-21, 2026-04-22)
    assert manifest["action_session_date_range"] == {
        "start": "2026-04-21",
        "end": "2026-04-22",
    }
    # Skipped row recorded with reason.
    assert manifest["skipped_runs"][0]["reason"] == "csv_missing"
    assert manifest["skipped_runs"][0]["finviz_csv_basename"] == "finviz_does_not_exist.csv"
    # Path resolution rule documented verbatim.
    assert "literal basename match" in manifest["path_resolution_rule"]

    # Result struct also returned to caller.
    assert result.total_evaluations == 4
    assert result.near_aplus_defensible_count == 2


def test_run_per_criterion_blockers_csv_schema(populated_db, tmp_path):
    db_path, inbox = populated_db
    out = tmp_path / "out"
    run_finviz_pool_aggregation(
        db_path=db_path,
        finviz_inbox_dir=inbox,
        output_dir=out,
        repo_root=Path("."),
    )
    with (out / "per_criterion_blockers.csv").open() as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["criterion", "count", "fraction_of_evaluations"]
    # First non-header row is <aplus> sentinel by schema design.
    assert rows[1][0] == "<aplus>"


def test_run_sample_csv_columns_and_pipe_separator(populated_db, tmp_path):
    db_path, inbox = populated_db
    out = tmp_path / "out"
    run_finviz_pool_aggregation(
        db_path=db_path,
        finviz_inbox_dir=inbox,
        output_dir=out,
        repo_root=Path("."),
    )
    with (out / "near_aplus_incompatible_sample.csv").open() as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == [
        "ticker",
        "evaluation_run_id",
        "action_session_date",
        "bucket",
        "failed_criteria",
    ]
    # C failed adr + tightness — pipe-joined.
    c_row = next(r for r in rows[1:] if r[0] == "C")
    assert set(c_row[4].split("|")) == {"adr", "tightness"}
