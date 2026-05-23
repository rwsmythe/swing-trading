"""Phase 13 T-T4.SB.4 Sub-task 4E (OQ-2.2 LOCK) — `swing patterns
label-corpus-all` CLI smoke tests.

Per plan section B.4 Sub-task 4E.3-4E.5: discriminating tests for the
operator-paired bulk relabel emit-mode subcommand.

OQ-2.2 LOCK: ship the corpus-all path as operator-paired V1; the CLI
EMITS one JSONL dispatch payload per claude_silver row to stdout and
exits 0. The persist path goes back through the existing
`label-exemplars --silver-response-file` per-row.

Monkeypatches USERPROFILE + HOME per CLAUDE.md gotcha to avoid pollution
of the operator's real ``~/swing-data/user-config.toml``.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from swing.data.models import PatternExemplar
from swing.data.repos import pattern_exemplars as exemplars_repo
from tests.cli.test_cli_eval import _minimal_config


@pytest.fixture
def runner_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    cfg_path = _minimal_config(project, home)
    runner = CliRunner()
    r = runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    assert r.exit_code == 0, r.output
    db_path = home / "swing-data" / "swing.db"
    return runner, cfg_path, db_path


def _make_silver(
    *, ticker: str, pattern_class: str = "vcp",
    label_source: str = "claude_silver",
    final_decision: str | None = None,
) -> PatternExemplar:
    # Default final_decision honors the source-vs-decision invariant
    # matrix at swing/data/models.py:1779-1806 (synthetic/perturbation
    # MUST be 'generated'; review sources MUST be in the review-decision
    # set; curated_gold MUST be 'confirmed').
    if final_decision is None:
        if label_source in ("synthetic", "perturbation"):
            final_decision = "generated"
        elif label_source == "curated_gold":
            final_decision = "confirmed"
        else:
            final_decision = "confirmed"
    # Invariant #4 + #5 (swing/data/models.py:1822-1859):
    #   claude_silver / codex_silver -> labeler_ev NOT NULL + gs NULL.
    #   curated_gold -> labeler_ev NOT NULL + gs NOT NULL.
    #   synthetic / perturbation -> labeler_ev NULL + gs NOT NULL.
    labeler_ev: str | None = json.dumps({"narrative": "x"})
    gs_json: str | None = None
    if label_source in ("synthetic", "perturbation"):
        labeler_ev = None
        gs_json = json.dumps({"geometric_score": 0.5})
    elif label_source == "curated_gold":
        gs_json = json.dumps({"geometric_score": 0.5})
    return PatternExemplar(
        id=None,
        ticker=ticker,
        timeframe="daily",
        start_date="2024-01-01",
        end_date="2024-02-01",
        proposed_pattern_class=pattern_class,
        final_decision=final_decision,
        label_source=label_source,
        structural_evidence_json="{}",
        created_at="2024-02-02T00:00:00",
        created_by="claude_dispatch",
        labeler_evidence_json=labeler_ev,
        geometric_score_json=gs_json,
    )


def _plant_exemplars(
    db_path: Path, rows: list[PatternExemplar],
) -> list[int]:
    conn = sqlite3.connect(db_path)
    try:
        ids: list[int] = []
        with conn:
            for r in rows:
                ids.append(exemplars_repo.insert_exemplar(conn, r))
        return ids
    finally:
        conn.close()


def test_label_corpus_all_emits_jsonl_per_claude_silver_row(
    runner_env,
) -> None:
    """Happy path: 3 claude_silver rows -> 3 JSONL payloads + exit 0."""
    runner, cfg_path, db_path = runner_env
    _plant_exemplars(db_path, [
        _make_silver(ticker="AAA", pattern_class="vcp"),
        _make_silver(ticker="BBB", pattern_class="flat_base"),
        _make_silver(ticker="CCC", pattern_class="cup_with_handle"),
    ])

    result = runner.invoke(main, [
        "--config", str(cfg_path), "patterns", "label-corpus-all",
    ])
    assert result.exit_code == 0, result.output
    stdout_lines = [
        line for line in result.output.splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert len(stdout_lines) == 3, (
        f"expected 3 JSONL lines, got {len(stdout_lines)}: {result.output}"
    )
    payloads = [json.loads(line) for line in stdout_lines]
    tickers = sorted(p["ticker"] for p in payloads)
    assert tickers == ["AAA", "BBB", "CCC"]
    # Per-row payload shape mirrors label-exemplars emit-mode contract.
    for p in payloads:
        assert "exemplar_id" in p
        assert "pattern_class" in p
        assert "rule_criteria" in p
        assert "structural_evidence_schema" in p
        assert "window_payload" in p
        # Bars NOT auto-fetched (V1 simplification per spec section 5.9
        # + emit-mode contract); operator supplies via --window-bars-file.
        assert p["window_payload"]["bars"] == []


def test_label_corpus_all_excludes_gold_and_other_tiers(
    runner_env,
) -> None:
    """Gold + other tiers MUST be excluded — gold rows are
    operator-validated and re-labeling would clobber the audit trail."""
    runner, cfg_path, db_path = runner_env
    _plant_exemplars(db_path, [
        _make_silver(
            ticker="SILVER", label_source="claude_silver",
        ),
        _make_silver(
            ticker="GOLD", label_source="curated_gold",
        ),
        _make_silver(
            ticker="SYNTH", label_source="synthetic",
        ),
    ])

    result = runner.invoke(main, [
        "--config", str(cfg_path), "patterns", "label-corpus-all",
    ])
    assert result.exit_code == 0, result.output
    stdout_lines = [
        line for line in result.output.splitlines()
        if line.strip() and not line.startswith("#")
    ]
    payloads = [json.loads(line) for line in stdout_lines]
    tickers = sorted(p["ticker"] for p in payloads)
    assert tickers == ["SILVER"], (
        f"expected only SILVER, got {tickers}: {result.output}"
    )


def test_label_corpus_all_includes_codex_silver_rows(runner_env) -> None:
    """codex_silver (disagreement-chain rows) ALSO included in the
    silver-tier review scope."""
    runner, cfg_path, db_path = runner_env
    # Plant parent claude_silver first, then codex_silver child pointing
    # at it (invariant #3: codex_silver requires parent_exemplar_id).
    parent_ids = _plant_exemplars(
        db_path, [_make_silver(ticker="C1", label_source="claude_silver")],
    )
    # codex_silver requires parent_exemplar_id at CONSTRUCTION time
    # (invariant validated in __post_init__) — construct via direct
    # PatternExemplar() with parent_exemplar_id set inline.
    child = PatternExemplar(
        id=None,
        ticker="C2",
        timeframe="daily",
        start_date="2024-01-01",
        end_date="2024-02-01",
        proposed_pattern_class="vcp",
        final_decision="confirmed",
        label_source="codex_silver",
        structural_evidence_json="{}",
        created_at="2024-02-02T00:00:00",
        created_by="codex_dispatch",
        labeler_evidence_json=json.dumps({"narrative": "x"}),
        geometric_score_json=None,
        parent_exemplar_id=parent_ids[0],
    )
    _plant_exemplars(db_path, [child])

    result = runner.invoke(main, [
        "--config", str(cfg_path), "patterns", "label-corpus-all",
    ])
    assert result.exit_code == 0, result.output
    stdout_lines = [
        line for line in result.output.splitlines()
        if line.strip() and not line.startswith("#")
    ]
    tickers = sorted(json.loads(line)["ticker"] for line in stdout_lines)
    assert tickers == ["C1", "C2"]


def test_label_corpus_all_empty_corpus_emits_notice_and_exits_zero(
    runner_env,
) -> None:
    """Empty corpus -> friendly operator-facing notice + exit 0
    (CTRL-C safe; no DB writes)."""
    runner, cfg_path, db_path = runner_env
    result = runner.invoke(main, [
        "--config", str(cfg_path), "patterns", "label-corpus-all",
    ])
    assert result.exit_code == 0, result.output
    assert "no silver-tier exemplars" in result.output


def test_label_corpus_all_limit_caps_emission_count(runner_env) -> None:
    """--limit N caps the emission count for operator-paired
    iteration convenience."""
    runner, cfg_path, db_path = runner_env
    _plant_exemplars(db_path, [
        _make_silver(ticker=f"T{i}", pattern_class="vcp")
        for i in range(5)
    ])
    result = runner.invoke(main, [
        "--config", str(cfg_path), "patterns", "label-corpus-all",
        "--limit", "2",
    ])
    assert result.exit_code == 0, result.output
    stdout_lines = [
        line for line in result.output.splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert len(stdout_lines) == 2


def test_label_corpus_all_output_is_ascii_only(runner_env) -> None:
    """ASCII-only contract per CLAUDE.md Windows cp1252 gotcha."""
    runner, cfg_path, db_path = runner_env
    _plant_exemplars(db_path, [
        _make_silver(ticker="ASC", pattern_class="vcp"),
    ])
    result = runner.invoke(main, [
        "--config", str(cfg_path), "patterns", "label-corpus-all",
    ])
    assert result.exit_code == 0, result.output
    # ASCII-only: ALL bytes < 128.
    output_bytes = result.output.encode("utf-8")
    assert all(b < 128 for b in output_bytes), (
        "non-ASCII detected in stdout (Windows cp1252 gotcha)"
    )
