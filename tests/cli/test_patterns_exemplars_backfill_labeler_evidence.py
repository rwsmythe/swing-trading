"""Phase 13 T2.SB6c T-A.6c.3 — `swing patterns-exemplars-backfill-labeler-evidence`
one-shot backfill subcommand tests (5 discriminating tests).

Per plan §G.3 Step 1c + §1.5.2 amendment Path C.

Synthesis rule (per plan §G.3 + Codex R1 MAJOR #2):
  rule_criteria: synthesized from `pattern_exemplars.geometric_score_json`
                 COLUMN (NOT a key inside labeler_evidence_json).
  narrative:     copied from labeler_evidence_json payload's
                 `geometric_evidence_narrative` key.

Idempotency contract (per plan §G.3): second run is a no-op on already-
augmented payloads.

Fail-soft per row (per plan §G.3): exception WARN-logs + skips that row.

Per Codex R2 MAJOR #5 closure: if `rule_criteria` missing AND
`geometric_score_json` is NULL/empty, the row is SKIPPED (do NOT write
an empty rule_criteria array).

Invariant #5 LOCK (migration 0020 lines 149-160): backfill SKIPs rows
where `labeler_evidence_json IS NULL` (those rows have label_source in
NULL-required class).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from swing.data.db import connect, ensure_schema


def _make_cfg(tmp_path: Path):
    from tests.cli.test_cli_eval import _minimal_config
    from swing.config import load as load_cfg
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    return load_cfg(cfg_path), cfg_path


def _seed_exemplar(
    conn,
    *,
    ticker: str,
    label_source: str,
    final_decision: str,
    labeler_evidence_json: str | None,
    geometric_score_json: str | None,
    ai_labeler_version: str | None = "claude-sonnet-4-5",
    parent_exemplar_id: int | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO pattern_exemplars
            (ticker, timeframe, start_date, end_date,
             proposed_pattern_class, final_decision, label_source,
             structural_evidence_json, created_at, created_by,
             final_pattern_class, ai_labeler_version,
             gold_validated_at, codex_reviewed, codex_agreement,
             geometric_score_json, labeler_evidence_json,
             quality_grade, notes, parent_exemplar_id)
        VALUES (?, 'daily', '2024-01-01', '2024-02-01', 'vcp', ?, ?,
                '{}', '2024-02-01T09:00:00', 'operator',
                NULL, ?,
                NULL, 0, NULL,
                ?, ?,
                NULL, NULL, ?)
        """,
        (
            ticker, final_decision, label_source, ai_labeler_version,
            geometric_score_json, labeler_evidence_json, parent_exemplar_id,
        ),
    )
    return int(cur.lastrowid)


# ---------------------------------------------------------------------------
# Test 1: synthesis happy-path — rule_criteria + narrative emitted.
# ---------------------------------------------------------------------------

def test_backfill_synthesizes_rule_criteria_and_narrative(tmp_path):
    cfg, _ = _make_cfg(tmp_path)
    ensure_schema(cfg.paths.db_path).close()

    payload = json.dumps({
        "confidence": "high",
        "evaluation": "confirm",
        "geometric_evidence_narrative": "stage_2 pass + 3 contractions tight",
    })
    geom = json.dumps({
        "rules": {
            "stage_2": {
                "pass": True, "value": "yes",
                "threshold": "all 8 TT pass", "tolerance": None,
            },
            "contractions": {
                "pass": True, "value": "3 contractions: 22pct/14pct/8pct",
                "threshold": ">= 2", "tolerance": None,
            },
            "volume_dryup": {
                "pass": False, "value": "0.85", "threshold": "<= 0.70",
                "tolerance": "0.05",
            },
        },
    })
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_exemplar(
                conn, ticker="AAA", label_source="curated_gold",
                final_decision="confirmed",
                labeler_evidence_json=payload,
                geometric_score_json=geom,
            )
    finally:
        conn.close()

    from swing.cli import patterns_exemplars_backfill_labeler_evidence_run
    conn = connect(cfg.paths.db_path)
    try:
        augmented, skipped = patterns_exemplars_backfill_labeler_evidence_run(
            conn,
        )
    finally:
        conn.close()
    assert augmented == 1
    assert skipped == 0

    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT labeler_evidence_json FROM pattern_exemplars LIMIT 1",
        ).fetchone()
    finally:
        conn.close()
    parsed = json.loads(row[0])
    assert "narrative" in parsed
    assert parsed["narrative"] == "stage_2 pass + 3 contractions tight"
    assert "rule_criteria" in parsed
    assert isinstance(parsed["rule_criteria"], list)
    assert len(parsed["rule_criteria"]) == 3
    # Original keys preserved.
    assert parsed.get("confidence") == "high"
    assert parsed.get("evaluation") == "confirm"
    assert (
        parsed.get("geometric_evidence_narrative")
        == "stage_2 pass + 3 contractions tight"
    )
    # rule_criteria shape: per-rule {name, status, evidence_value,
    # threshold, tolerance}.
    names = {c["name"] for c in parsed["rule_criteria"]}
    assert names == {"stage_2", "contractions", "volume_dryup"}
    statuses = {c["name"]: c["status"] for c in parsed["rule_criteria"]}
    assert statuses == {
        "stage_2": "pass",
        "contractions": "pass",
        "volume_dryup": "fail",
    }


# ---------------------------------------------------------------------------
# Test 2: idempotency — second run is no-op on already-augmented payloads.
# ---------------------------------------------------------------------------

def test_backfill_idempotent_second_run_no_op(tmp_path):
    cfg, _ = _make_cfg(tmp_path)
    ensure_schema(cfg.paths.db_path).close()

    payload = json.dumps({
        "confidence": "medium",
        "evaluation": "confirm",
        "geometric_evidence_narrative": "narrative-1",
    })
    geom = json.dumps({
        "rules": {
            "stage_2": {"pass": True, "value": "yes", "threshold": "8/8"},
        },
    })
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_exemplar(
                conn, ticker="BBB", label_source="curated_gold",
                final_decision="confirmed",
                labeler_evidence_json=payload,
                geometric_score_json=geom,
            )
    finally:
        conn.close()

    from swing.cli import patterns_exemplars_backfill_labeler_evidence_run

    conn = connect(cfg.paths.db_path)
    try:
        a1, s1 = patterns_exemplars_backfill_labeler_evidence_run(conn)
    finally:
        conn.close()
    assert a1 == 1
    assert s1 == 0

    conn = connect(cfg.paths.db_path)
    try:
        row1 = conn.execute(
            "SELECT labeler_evidence_json FROM pattern_exemplars LIMIT 1",
        ).fetchone()
    finally:
        conn.close()

    # Second run.
    conn = connect(cfg.paths.db_path)
    try:
        a2, s2 = patterns_exemplars_backfill_labeler_evidence_run(conn)
    finally:
        conn.close()
    assert a2 == 0
    assert s2 == 1  # idempotently skipped

    conn = connect(cfg.paths.db_path)
    try:
        row2 = conn.execute(
            "SELECT labeler_evidence_json FROM pattern_exemplars LIMIT 1",
        ).fetchone()
    finally:
        conn.close()
    # First-run output preserved exactly.
    assert json.loads(row1[0]) == json.loads(row2[0])


# ---------------------------------------------------------------------------
# Test 3: Invariant #5 — rows with labeler_evidence_json IS NULL are skipped
# (those rows have label_source in NULL-required class).
# ---------------------------------------------------------------------------

def test_backfill_skips_rows_with_null_labeler_evidence(tmp_path):
    cfg, _ = _make_cfg(tmp_path)
    ensure_schema(cfg.paths.db_path).close()

    # closed_loop_review must have labeler_evidence_json IS NULL per Invariant #5
    # (and may have geometric_score_json populated per Invariant #4).
    geom = json.dumps({
        "rules": {"stage_2": {"pass": True, "value": "yes",
                              "threshold": "8/8"}},
    })
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_exemplar(
                conn, ticker="CCC", label_source="closed_loop_review",
                final_decision="confirmed",
                labeler_evidence_json=None,
                geometric_score_json=geom,
                ai_labeler_version=None,
            )
    finally:
        conn.close()

    from swing.cli import patterns_exemplars_backfill_labeler_evidence_run
    conn = connect(cfg.paths.db_path)
    try:
        a, s = patterns_exemplars_backfill_labeler_evidence_run(conn)
    finally:
        conn.close()
    # Row is filtered upstream (labeler_evidence_json IS NULL). Per plan
    # contract the filter does not increment skipped (the row is invisible
    # to the synthesis loop).
    assert a == 0
    # The labeler_evidence_json column remains NULL post-run.
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT labeler_evidence_json FROM pattern_exemplars LIMIT 1",
        ).fetchone()
    finally:
        conn.close()
    assert row[0] is None


# ---------------------------------------------------------------------------
# Test 4: graceful no-op when geometric_score_json is NULL/empty AND
# rule_criteria missing. Per Codex R2 MAJOR #5: skip the row (do NOT write
# empty rule_criteria array).
# ---------------------------------------------------------------------------

def test_backfill_skips_when_geometric_score_json_missing_and_no_rule_criteria(
    tmp_path, caplog,
):
    cfg, _ = _make_cfg(tmp_path)
    ensure_schema(cfg.paths.db_path).close()

    # claude_silver may have geometric_score_json NULL per Invariant #4;
    # labeler_evidence_json must be NOT NULL per Invariant #5.
    payload = json.dumps({
        "confidence": "high",
        "evaluation": "confirm",
        "geometric_evidence_narrative": "narrative-only",
    })
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_exemplar(
                conn, ticker="DDD", label_source="claude_silver",
                final_decision="confirmed",
                labeler_evidence_json=payload,
                geometric_score_json=None,
            )
    finally:
        conn.close()

    from swing.cli import patterns_exemplars_backfill_labeler_evidence_run
    conn = connect(cfg.paths.db_path)
    try:
        with caplog.at_level("WARNING"):
            a, s = patterns_exemplars_backfill_labeler_evidence_run(conn)
    finally:
        conn.close()
    assert a == 0
    assert s == 1
    # Persisted row unchanged (no rule_criteria written).
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT labeler_evidence_json FROM pattern_exemplars LIMIT 1",
        ).fetchone()
    finally:
        conn.close()
    parsed = json.loads(row[0])
    assert "rule_criteria" not in parsed


# ---------------------------------------------------------------------------
# Test 5: round-trip via public repo reader.
# ---------------------------------------------------------------------------

def test_backfill_round_trips_via_public_reader(tmp_path):
    cfg, _ = _make_cfg(tmp_path)
    ensure_schema(cfg.paths.db_path).close()

    payload = json.dumps({
        "confidence": "high",
        "evaluation": "confirm",
        "geometric_evidence_narrative": "round-trip narrative",
    })
    geom = json.dumps({
        "rules": {
            "stage_2": {"pass": True, "value": "yes",
                        "threshold": "all 8 TT"},
        },
    })
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            ex_id = _seed_exemplar(
                conn, ticker="EEE", label_source="curated_gold",
                final_decision="confirmed",
                labeler_evidence_json=payload,
                geometric_score_json=geom,
            )
    finally:
        conn.close()

    from swing.cli import patterns_exemplars_backfill_labeler_evidence_run
    from swing.data.repos.pattern_exemplars import get_exemplar_by_id

    conn = connect(cfg.paths.db_path)
    try:
        patterns_exemplars_backfill_labeler_evidence_run(conn)
    finally:
        conn.close()

    conn = connect(cfg.paths.db_path)
    try:
        ex = get_exemplar_by_id(conn, ex_id)
    finally:
        conn.close()
    assert ex is not None
    parsed = json.loads(ex.labeler_evidence_json)
    assert "rule_criteria" in parsed
    assert "narrative" in parsed
    assert parsed["narrative"] == "round-trip narrative"


# ---------------------------------------------------------------------------
# Test 6 (BONUS): NEW repo helper update_exemplar_labeler_evidence_json
# round-trips + raises on missing id.
# ---------------------------------------------------------------------------

def test_update_exemplar_labeler_evidence_json_raises_on_missing_id(tmp_path):
    cfg, _ = _make_cfg(tmp_path)
    ensure_schema(cfg.paths.db_path).close()

    from swing.data.repos.pattern_exemplars import (
        update_exemplar_labeler_evidence_json,
    )
    conn = connect(cfg.paths.db_path)
    try:
        with pytest.raises(ValueError, match="not found"):
            with conn:
                update_exemplar_labeler_evidence_json(
                    conn, exemplar_id=9999, new_json='{"x": 1}',
                )
    finally:
        conn.close()
