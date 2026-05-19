"""Phase 13 T2.SB1 T-A.1.5 — `swing patterns label-exemplars` CLI tests.

Per plan §G.1 T-A.1.5 Step 1: 3 discriminating tests covering
(a) dispatches subagent + persists silver row;
(b) rejects invalid pattern-class with click error;
(c) ASCII-only output verified.

Monkeypatches USERPROFILE + HOME per CLAUDE.md gotcha to avoid pollution of
the operator's real ``~/swing-data/user-config.toml``.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
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


def test_label_exemplars_with_silver_response_file_persists_silver_row(
    runner_env, tmp_path: Path,
) -> None:
    """Happy path: --silver-response-file persists a pattern_exemplars row."""
    runner, cfg_path, db_path = runner_env

    silver_response = {
        "evaluation": "confirmed",
        "confidence": "high",
        "structural_evidence_json": json.dumps(
            {"pivot_price": 25.0, "contractions": []}
        ),
        "geometric_evidence_narrative": (
            "Stage 2 uptrend; pivot at 25.00 above resistance."
        ),
    }
    silver_path = tmp_path / "silver.json"
    silver_path.write_text(json.dumps(silver_response), encoding="utf-8")

    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "label-exemplars",
        "--ticker", "ABC",
        "--start", "2024-01-01",
        "--end", "2024-02-01",
        "--pattern-class", "vcp",
        "--silver-response-file", str(silver_path),
    ])
    assert r.exit_code == 0, r.output
    assert "silver exemplar persisted" in r.output
    assert "ticker=ABC" in r.output
    assert "pattern_class=vcp" in r.output

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT ticker, proposed_pattern_class, label_source, final_decision, "
        "created_by FROM pattern_exemplars"
    ).fetchall()
    conn.close()
    assert rows == [("ABC", "vcp", "claude_silver", "confirmed", "claude_dispatch")]


def test_label_exemplars_rejects_invalid_pattern_class(runner_env) -> None:
    """Invalid pattern-class → click BadParameter (exit code != 0)."""
    runner, cfg_path, _ = runner_env

    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "label-exemplars",
        "--ticker", "ABC",
        "--start", "2024-01-01",
        "--end", "2024-02-01",
        "--pattern-class", "bogus_class_not_in_v1_set",
    ])
    assert r.exit_code != 0
    # ClickException + BadParameter both emit messages that include the option
    # name. Tolerate either flavor.
    output_combined = (r.output or "") + str(r.exception or "")
    assert (
        "pattern-class" in output_combined.lower()
        or "bogus_class_not_in_v1_set" in output_combined
    )


def test_label_exemplars_emits_payload_when_no_response_file(
    runner_env,
) -> None:
    """Without --silver-response-file: CLI emits dispatch payload JSON."""
    runner, cfg_path, _ = runner_env

    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "label-exemplars",
        "--ticker", "ABC",
        "--start", "2024-01-01",
        "--end", "2024-02-01",
        "--pattern-class", "flat_base",
        "--timeframe", "daily",
    ])
    assert r.exit_code == 0, r.output

    # Output is JSON payload. Parse + verify shape.
    payload = json.loads(r.output)
    assert payload["pattern_class"] == "flat_base"
    assert payload["window_payload"]["ticker"] == "ABC"
    assert payload["window_payload"]["timeframe"] == "daily"
    assert payload["window_payload"]["start_date"] == "2024-01-01"
    assert payload["window_payload"]["end_date"] == "2024-02-01"


_NON_ASCII_PATTERN = re.compile(r"[^\x00-\x7F]")


def test_label_exemplars_output_is_ascii_only(runner_env, tmp_path: Path) -> None:
    """Per §A.8 + CLAUDE.md Windows cp1252 stdout gotcha: ALL CLI output
    paths emit ASCII-only characters.

    Covers both --emit-payload mode + --silver-response-file persist mode.
    """
    runner, cfg_path, _ = runner_env

    # Mode 1: payload-emit.
    r1 = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "label-exemplars",
        "--ticker", "ABC",
        "--start", "2024-01-01",
        "--end", "2024-02-01",
        "--pattern-class", "cup_with_handle",
    ])
    assert r1.exit_code == 0
    assert _NON_ASCII_PATTERN.search(r1.output) is None, (
        f"Non-ASCII character leaked into CLI output: {r1.output!r}"
    )

    # Mode 2: --silver-response-file persist.
    silver_response = {
        "evaluation": "watch",
        "confidence": "medium",
        "structural_evidence_json": json.dumps({"placeholder": True}),
        "geometric_evidence_narrative": (
            "Watching pre-breakout setup; pivot 25.50."
        ),
    }
    silver_path = tmp_path / "silver2.json"
    silver_path.write_text(json.dumps(silver_response), encoding="utf-8")
    r2 = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "label-exemplars",
        "--ticker", "XYZ",
        "--start", "2024-02-01",
        "--end", "2024-03-15",
        "--pattern-class", "vcp",
        "--silver-response-file", str(silver_path),
    ])
    assert r2.exit_code == 0
    assert _NON_ASCII_PATTERN.search(r2.output) is None, (
        f"Non-ASCII character leaked into CLI output: {r2.output!r}"
    )


def test_label_exemplars_rejects_malformed_silver_response_file(
    runner_env, tmp_path: Path,
) -> None:
    """Invalid silver JSON shape (missing required keys) → ClickException."""
    runner, cfg_path, _ = runner_env

    malformed_path = tmp_path / "malformed.json"
    malformed_path.write_text(
        json.dumps({"evaluation": "confirmed"}),  # missing 3 required keys
        encoding="utf-8",
    )

    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "label-exemplars",
        "--ticker", "ABC",
        "--start", "2024-01-01",
        "--end", "2024-02-01",
        "--pattern-class", "vcp",
        "--silver-response-file", str(malformed_path),
    ])
    assert r.exit_code != 0
    output_combined = (r.output or "") + str(r.exception or "")
    assert "silver-response-file shape invalid" in output_combined


# T-A.1.5b Defect 1 — CLI dict-or-str coercion at structural_evidence_json.
#
# Provenance: fixture copied (verbatim) from the aborted T-A.1.7 paired-session
# at tmp/phase13-labeling/silver_1_SNAP_vcp.json. The subagent's documented
# output contract per .claude/agents/pattern-labeler.md emits
# `structural_evidence_json` as a JSON OBJECT (dict). Pre-T-A.1.5b CLI passed
# the dict directly into _SilverLabelResponse(structural_evidence_json=<dict>),
# the downstream repo INSERT then raised
# `sqlite3.ProgrammingError: type 'dict' is not supported` at the operator's
# first persist on 2026-05-19.
def test_label_exemplars_accepts_dict_shaped_structural_evidence_json(
    runner_env, tmp_path: Path,
) -> None:
    """Defect 1 discriminating test — REAL-shape (dict) silver response from
    tmp/phase13-labeling/silver_1_SNAP_vcp.json must persist + round-trip
    through json.loads() to the EXACT original dict.

    Pre-fix: structural_evidence_json comes through as a Python dict; the
    sqlite3 INSERT raises ProgrammingError 'type dict is not supported'.
    Post-fix: CLI coerces dict -> json.dumps(...) before constructing
    _SilverLabelResponse; persist succeeds; row's structural_evidence_json
    column is the serialized dict, which json.loads() restores intact.
    """
    runner, cfg_path, db_path = runner_env

    fixture_path = (
        Path(__file__).parent.parent / "fixtures" / "pattern_labeler"
        / "silver_response_vcp_dict_shape.json"
    )
    silver_response_raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    # Verify the fixture itself carries a DICT (not a string) at
    # structural_evidence_json — guards against the fixture drifting back to
    # the old json.dumps({...}) shape.
    assert isinstance(silver_response_raw["structural_evidence_json"], dict), (
        "fixture must carry a dict at structural_evidence_json to be a "
        "discriminating test of the T-A.1.5b Defect 1 fix"
    )
    expected_evidence_dict = silver_response_raw["structural_evidence_json"]

    silver_path = tmp_path / "silver_dict_shape.json"
    silver_path.write_text(json.dumps(silver_response_raw), encoding="utf-8")

    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "label-exemplars",
        "--ticker", "SNAP",
        "--start", "2020-07-01",
        "--end", "2020-09-30",
        "--pattern-class", "vcp",
        "--silver-response-file", str(silver_path),
    ])
    assert r.exit_code == 0, (
        f"persist failed (likely sqlite3.ProgrammingError pre-fix): "
        f"output={r.output!r} exception={r.exception!r}"
    )
    assert "silver exemplar persisted" in r.output

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT structural_evidence_json FROM pattern_exemplars "
        "WHERE ticker = 'SNAP' AND proposed_pattern_class = 'vcp'"
    ).fetchall()
    conn.close()
    assert len(rows) == 1, f"expected exactly one persisted row, got {rows}"
    persisted_evidence_str = rows[0][0]
    assert isinstance(persisted_evidence_str, str), (
        "persisted structural_evidence_json must be TEXT (serialized JSON), "
        "NOT a binary blob or NULL"
    )
    # Round-trip integrity: json.loads(persisted) == original dict.
    assert json.loads(persisted_evidence_str) == expected_evidence_dict
