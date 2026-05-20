"""Phase 13 T2.SB1 T-A.1.8 — ``swing patterns review-silver-with-codex`` CLI.

Per closer brief T-1.8.1 acceptance criteria:
  - New CLI subcommand exercising ``should_fire_codex`` +
    ``fire_codex_review_for_silver_row`` end-to-end.
  - L9 LOCK preserved: phase HARD-CODED to ``t2_sb1`` (random-15% only).
  - Caller-tx contract preserved at repo-level inserts.
  - ASCII-only on CLI output.

Operator-paired V1 workflow (mirrors ``label-exemplars`` shape per OQ-6):
  Step A (emit/sample):
    swing patterns review-silver-with-codex --exemplar-id 5 --seed 42
      => emits dispatch payload if random-15% sample fires;
         emits skip-note + exit 0 if sample does NOT fire.
  Step B (operator dispatches Codex via paired session; saves response JSON).
  Step C (persist):
    swing patterns review-silver-with-codex --exemplar-id 5 \
        --codex-response-file codex.json
      => bypasses policy gate (operator's response collection IS the
         dispatch decision); parses + invokes
         ``fire_codex_review_for_silver_row`` with a forced-fire rng so the
         existing service-layer policy gate is exercised end-to-end.

Per CLAUDE.md gotcha (USERPROFILE + HOME monkeypatch): test fixture
isolates writes from operator's real ``~/swing-data/user-config.toml``.
"""
from __future__ import annotations

import json
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


def _plant_claude_silver_row(
    runner: CliRunner, cfg_path: Path, tmp_path: Path,
    ticker: str = "ABC", pattern_class: str = "vcp",
    evaluation: str = "confirmed",
) -> int:
    """Plant a claude_silver row via the label-exemplars persist path.

    Returns the inserted exemplar id by reading max(id) from the DB.
    """
    silver_response = {
        "evaluation": evaluation,
        "confidence": "high",
        "structural_evidence_json": json.dumps({"pivot_price": 25.0}),
        "geometric_evidence_narrative": "Stage 2 uptrend; pivot at 25.00.",
    }
    silver_path = tmp_path / f"silver_{ticker}.json"
    silver_path.write_text(json.dumps(silver_response), encoding="utf-8")
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "label-exemplars",
        "--ticker", ticker,
        "--start", "2024-01-01",
        "--end", "2024-02-01",
        "--pattern-class", pattern_class,
        "--silver-response-file", str(silver_path),
    ])
    assert r.exit_code == 0, r.output
    return _read_max_id(runner, cfg_path)


def _read_max_id(runner: CliRunner, cfg_path: Path) -> int:
    # Read the db path from the same config used by the CLI under test.
    import tomllib
    with open(cfg_path, "rb") as f:
        cfg = tomllib.load(f)
    db_path = Path(cfg["paths"]["db_path"]).expanduser()
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT MAX(id) FROM pattern_exemplars"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None and row[0] is not None
    return int(row[0])


# ============================================================================
# Emit-mode tests (no --codex-response-file).
# ============================================================================


def test_emit_mode_when_seed_selects_row_emits_payload(
    runner_env, tmp_path: Path,
) -> None:
    """Seed that falls below 15% threshold => CLI emits dispatch payload.

    Seed 0 + Python's Mersenne Twister + the first ``rng.random()`` call
    yields ~0.84 — that's ABOVE the 15% threshold, so we need a seed
    whose first random() draw IS below 0.15. Pre-computed: seed 42 first
    draw = 0.6394... (above). Sample candidates to find one < 0.15.
    """
    runner, cfg_path, _ = runner_env
    exemplar_id = _plant_claude_silver_row(runner, cfg_path, tmp_path)

    # Find a seed whose first random() is < 0.15.
    import random as _random
    fire_seed = None
    for s in range(10_000):
        if _random.Random(s).random() < 0.15:
            fire_seed = s
            break
    assert fire_seed is not None

    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "review-silver-with-codex",
        "--exemplar-id", str(exemplar_id),
        "--seed", str(fire_seed),
    ])
    assert r.exit_code == 0, r.output
    # Output is a JSON object with keys parent_exemplar_id +
    # parent_label_source + spec_section + rule_criteria + ...
    payload = json.loads(r.output)
    assert payload["parent_exemplar_id"] == exemplar_id
    assert payload["parent_label_source"] == "claude_silver"
    assert payload["proposed_pattern_class"] == "vcp"
    assert "rule_criteria" in payload
    assert "structural_evidence_schema" in payload


def test_emit_mode_when_seed_skips_row_emits_skip_note(
    runner_env, tmp_path: Path,
) -> None:
    """Seed that falls above 15% threshold => skip-note printed, exit 0."""
    runner, cfg_path, _ = runner_env
    exemplar_id = _plant_claude_silver_row(runner, cfg_path, tmp_path)

    # Find a seed whose first random() is >= 0.15.
    import random as _random
    skip_seed = None
    for s in range(10_000):
        if _random.Random(s).random() >= 0.15:
            skip_seed = s
            break
    assert skip_seed is not None

    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "review-silver-with-codex",
        "--exemplar-id", str(exemplar_id),
        "--seed", str(skip_seed),
    ])
    assert r.exit_code == 0, r.output
    assert "[skip]" in r.output
    assert f"exemplar {exemplar_id}" in r.output
    # No payload JSON emitted.
    assert "rule_criteria" not in r.output


def test_emit_mode_rejects_unknown_exemplar(runner_env) -> None:
    """exemplar_id that doesn't exist => ClickException."""
    runner, cfg_path, _ = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "review-silver-with-codex",
        "--exemplar-id", "999999",
        "--seed", "1",
    ])
    assert r.exit_code != 0
    out = (r.output or "") + str(r.exception or "")
    assert "999999" in out or "not found" in out.lower()


def test_emit_mode_rejects_non_claude_silver_exemplar(
    runner_env, tmp_path: Path,
) -> None:
    """Codex 2nd-review fires ONLY on claude_silver rows. Curated-gold rows
    rejected with a clean ClickException routing-hint.
    """
    runner, cfg_path, db_path = runner_env
    exemplar_id = _plant_claude_silver_row(runner, cfg_path, tmp_path)
    # Promote to gold so label_source != 'claude_silver'.
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE pattern_exemplars SET label_source = 'curated_gold' "
            "WHERE id = ?",
            (exemplar_id,),
        )
        conn.commit()
    finally:
        conn.close()

    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "review-silver-with-codex",
        "--exemplar-id", str(exemplar_id),
        "--seed", "0",  # any seed; the check fires before the policy gate
    ])
    assert r.exit_code != 0
    out = (r.output or "") + str(r.exception or "")
    assert "claude_silver" in out


# ============================================================================
# Persist-mode tests (--codex-response-file present).
# ============================================================================


def test_persist_mode_disagreement_inserts_codex_silver_row(
    runner_env, tmp_path: Path,
) -> None:
    """Persist path with disagreement response => second row inserted with
    label_source='codex_silver' + parent_exemplar_id linkage.
    """
    runner, cfg_path, db_path = runner_env
    parent_id = _plant_claude_silver_row(runner, cfg_path, tmp_path)

    codex_response = {
        "agreed": False,
        "alternative_evaluation": "rejected",
        "alternative_confidence": "high",
        "alternative_structural_evidence_json": {
            "reason": "criterion 5 failed: pivot below resistance",
        },
    }
    codex_path = tmp_path / "codex.json"
    codex_path.write_text(json.dumps(codex_response), encoding="utf-8")

    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "review-silver-with-codex",
        "--exemplar-id", str(parent_id),
        "--codex-response-file", str(codex_path),
    ])
    assert r.exit_code == 0, r.output
    assert "codex_silver row persisted" in r.output
    assert f"parent_exemplar_id={parent_id}" in r.output

    conn = sqlite3.connect(db_path)
    try:
        # Parent row flipped.
        parent = conn.execute(
            "SELECT codex_reviewed, codex_agreement, label_source "
            "FROM pattern_exemplars WHERE id = ?",
            (parent_id,),
        ).fetchone()
        assert parent == (1, 0, "claude_silver")
        # Codex disagreement row inserted.
        rows = conn.execute(
            "SELECT label_source, parent_exemplar_id, final_decision "
            "FROM pattern_exemplars WHERE parent_exemplar_id = ?",
            (parent_id,),
        ).fetchall()
        assert rows == [("codex_silver", parent_id, "rejected")]
    finally:
        conn.close()


def test_persist_mode_agreement_flips_parent_no_new_row(
    runner_env, tmp_path: Path,
) -> None:
    """Persist path with agreement => parent flagged codex_agreement=1;
    NO new row inserted.
    """
    runner, cfg_path, db_path = runner_env
    parent_id = _plant_claude_silver_row(runner, cfg_path, tmp_path)

    codex_response = {"agreed": True}
    codex_path = tmp_path / "codex.json"
    codex_path.write_text(json.dumps(codex_response), encoding="utf-8")

    pre_count = _count_rows(db_path)
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "review-silver-with-codex",
        "--exemplar-id", str(parent_id),
        "--codex-response-file", str(codex_path),
    ])
    assert r.exit_code == 0, r.output
    assert "codex agreement" in r.output.lower()
    post_count = _count_rows(db_path)
    assert post_count == pre_count

    conn = sqlite3.connect(db_path)
    try:
        parent = conn.execute(
            "SELECT codex_reviewed, codex_agreement FROM pattern_exemplars "
            "WHERE id = ?",
            (parent_id,),
        ).fetchone()
        assert parent == (1, 1)
    finally:
        conn.close()


def _count_rows(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM pattern_exemplars"
        ).fetchone()
    finally:
        conn.close()
    return int(row[0])


def test_persist_mode_rejects_malformed_codex_response_file(
    runner_env, tmp_path: Path,
) -> None:
    """Malformed JSON in --codex-response-file => clean ClickException."""
    runner, cfg_path, _ = runner_env
    parent_id = _plant_claude_silver_row(runner, cfg_path, tmp_path)

    codex_path = tmp_path / "codex.json"
    codex_path.write_text("not valid json {[", encoding="utf-8")

    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "review-silver-with-codex",
        "--exemplar-id", str(parent_id),
        "--codex-response-file", str(codex_path),
    ])
    assert r.exit_code != 0
    out = (r.output or "") + str(r.exception or "")
    assert "not valid JSON" in out


def test_persist_mode_rejects_shape_invalid_codex_response_file(
    runner_env, tmp_path: Path,
) -> None:
    """Top-level scalar / array => clean ClickException."""
    runner, cfg_path, _ = runner_env
    parent_id = _plant_claude_silver_row(runner, cfg_path, tmp_path)

    codex_path = tmp_path / "codex.json"
    codex_path.write_text("[1, 2, 3]", encoding="utf-8")

    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "review-silver-with-codex",
        "--exemplar-id", str(parent_id),
        "--codex-response-file", str(codex_path),
    ])
    assert r.exit_code != 0
    out = (r.output or "") + str(r.exception or "")
    assert "shape invalid" in out.lower() or "must be" in out.lower()


def test_persist_mode_rejects_non_bool_agreed_field(
    runner_env, tmp_path: Path,
) -> None:
    """Codex R1 Major #1 closure: `agreed` MUST be a JSON boolean.
    Quoted-string `"false"` would otherwise be coerced to True via
    `bool("false")` -> a disagreement silently recorded as agreement +
    no codex_silver row inserted. The CLI rejects with a routing-hint
    error pointing at the common quoting mistake.
    """
    runner, cfg_path, _ = runner_env
    parent_id = _plant_claude_silver_row(runner, cfg_path, tmp_path)

    for bogus_agreed in ("false", "true", 0, 1, None):
        codex_path = tmp_path / "codex.json"
        codex_path.write_text(
            json.dumps({"agreed": bogus_agreed,
                        "alternative_evaluation": "rejected"}),
            encoding="utf-8",
        )
        r = runner.invoke(main, [
            "--config", str(cfg_path),
            "patterns", "review-silver-with-codex",
            "--exemplar-id", str(parent_id),
            "--codex-response-file", str(codex_path),
        ])
        assert r.exit_code != 0, (
            f"agreed={bogus_agreed!r} ({type(bogus_agreed).__name__}) "
            f"must be rejected; got exit 0 output={r.output!r}"
        )
        out = (r.output or "") + str(r.exception or "")
        assert "agreed" in out.lower() and (
            "boolean" in out.lower() or "bool" in out.lower()
        ), (
            f"agreed={bogus_agreed!r}: rejection message must cite "
            f"'agreed' + 'boolean'/'bool'; got {out!r}"
        )


def test_persist_mode_rejects_disagreement_without_alternatives(
    runner_env, tmp_path: Path,
) -> None:
    """agreed=False but missing alternative_evaluation =>
    ClickException (service-layer ValueError wrapped per T-A.1.5b R4 M#1).
    """
    runner, cfg_path, _ = runner_env
    parent_id = _plant_claude_silver_row(runner, cfg_path, tmp_path)

    # Missing alternative_evaluation + alternative_structural_evidence_json.
    codex_response = {"agreed": False}
    codex_path = tmp_path / "codex.json"
    codex_path.write_text(json.dumps(codex_response), encoding="utf-8")

    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "review-silver-with-codex",
        "--exemplar-id", str(parent_id),
        "--codex-response-file", str(codex_path),
    ])
    assert r.exit_code != 0
    out = (r.output or "") + str(r.exception or "")
    assert "alternative" in out.lower()


# ============================================================================
# ASCII-only output discipline (CLAUDE.md Windows cp1252 stdout gotcha).
# ============================================================================


def test_cli_output_is_ascii_only(runner_env, tmp_path: Path) -> None:
    """Every output path (emit + skip + persist + error) MUST be ASCII-only
    so PowerShell stdout (cp1252) does not crash on non-ASCII glyphs.
    """
    runner, cfg_path, _ = runner_env
    parent_id = _plant_claude_silver_row(runner, cfg_path, tmp_path)

    # Emit (fire) path.
    fire_seed = next(
        s for s in range(10_000)
        if __import__("random").Random(s).random() < 0.15
    )
    r_emit = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "review-silver-with-codex",
        "--exemplar-id", str(parent_id),
        "--seed", str(fire_seed),
    ])
    assert r_emit.exit_code == 0
    r_emit.output.encode("ascii")  # raises if non-ASCII present

    # Persist path.
    codex_path = tmp_path / "codex.json"
    codex_path.write_text(json.dumps({"agreed": True}), encoding="utf-8")
    r_persist = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "review-silver-with-codex",
        "--exemplar-id", str(parent_id),
        "--codex-response-file", str(codex_path),
    ])
    assert r_persist.exit_code == 0
    r_persist.output.encode("ascii")
