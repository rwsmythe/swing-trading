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
    runner_env, monkeypatch,
) -> None:
    """Without --silver-response-file: CLI emits dispatch payload JSON."""
    # Post-T-A.1.5b R1 M#1+M#2: emit mode requires non-empty bars; mock
    # yfinance so the unit test does not require network.
    from swing.patterns import labeling_bars
    import pandas as pd
    monkeypatch.setattr(
        labeling_bars.yf, "download",
        lambda *a, **k: pd.DataFrame(
            {"Open": [10.0], "High": [11.0], "Low": [9.5],
             "Close": [10.5], "Volume": [100000]},
            index=pd.DatetimeIndex(["2024-01-02"]),
        ),
    )
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
    # T-A.1.5b Defect 2: dispatch payload carries non-placeholder
    # spec-section-5.2-through-5.6 rule_criteria + structural_evidence_schema.
    rc = payload["rule_criteria"]
    assert rc["pattern_class"] == "flat_base"
    assert rc["spec_section"] == "section 5.3"
    assert isinstance(rc["criteria"], list) and len(rc["criteria"]) >= 2
    assert "placeholder" not in json.dumps(rc).lower()
    schema = payload["structural_evidence_schema"]
    assert schema["pattern_class"] == "flat_base"
    assert schema["spec_section"] == "section 5.3"
    assert "placeholder" not in json.dumps(schema).lower()


_NON_ASCII_PATTERN = re.compile(r"[^\x00-\x7F]")


def test_label_exemplars_output_is_ascii_only(
    runner_env, monkeypatch, tmp_path: Path,
) -> None:
    """Per §A.8 + CLAUDE.md Windows cp1252 stdout gotcha: ALL CLI output
    paths emit ASCII-only characters.

    Covers both --emit-payload mode + --silver-response-file persist mode.
    """
    # Post-T-A.1.5b R1 M#1+M#2: emit mode requires non-empty bars; mock
    # yfinance so the test stays hermetic.
    from swing.patterns import labeling_bars
    import pandas as pd
    monkeypatch.setattr(
        labeling_bars.yf, "download",
        lambda *a, **k: pd.DataFrame(
            {"Open": [10.0], "High": [11.0], "Low": [9.5],
             "Close": [10.5], "Volume": [100000]},
            index=pd.DatetimeIndex(["2024-01-02"]),
        ),
    )
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


# T-A.1.5b Defect 3 (Option B) — auto-fetch bars at CLI emit path.

def test_label_exemplars_payload_autofetches_bars_via_yfinance(
    runner_env, monkeypatch,
) -> None:
    """Defect 3 Option B happy-path: emit-payload mode invokes the
    yfinance windowed download helper + populates bars in the dispatch
    payload (NOT the V1 empty placeholder list).
    """
    from swing.patterns import labeling_bars

    captured = {"n": 0}

    def fake_download(ticker, **kwargs):
        captured["n"] += 1
        captured["ticker"] = ticker
        import pandas as pd
        df = pd.DataFrame({
            "Open": [10.0, 10.5],
            "High": [11.0, 11.5],
            "Low": [9.5, 10.0],
            "Close": [10.5, 11.2],
            "Volume": [100000, 120000],
        }, index=pd.DatetimeIndex(["2024-01-02", "2024-01-03"]))
        return df

    monkeypatch.setattr(labeling_bars.yf, "download", fake_download)

    runner, cfg_path, _ = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "label-exemplars",
        "--ticker", "ABC",
        "--start", "2024-01-02",
        "--end", "2024-01-03",
        "--pattern-class", "vcp",
    ])
    assert r.exit_code == 0, r.output
    assert captured["n"] == 1
    assert captured["ticker"] == "ABC"

    payload = json.loads(r.output)
    bars = payload["window_payload"]["bars"]
    assert len(bars) == 2
    assert bars[0]["date"] == "2024-01-02"
    assert bars[0]["close"] == 10.5
    assert bars[1]["close"] == 11.2


# Codex R1 M#1 closure: persist mode (--silver-response-file) MUST NOT
# trigger yfinance auto-fetch. The persist path stores ONLY the label;
# the bars list is not needed.
def test_persist_mode_does_not_autofetch_bars(
    runner_env, monkeypatch, tmp_path: Path,
) -> None:
    from swing.patterns import labeling_bars

    yf_called = {"n": 0}

    def fake_download(*args, **kwargs):
        yf_called["n"] += 1
        return None

    monkeypatch.setattr(labeling_bars.yf, "download", fake_download)

    silver = {
        "evaluation": "confirmed",
        "confidence": "medium",
        "structural_evidence_json": {"pivot_price": 25.0},
        "geometric_evidence_narrative": "Test narrative.",
    }
    silver_path = tmp_path / "silver_persist.json"
    silver_path.write_text(json.dumps(silver), encoding="utf-8")

    runner, cfg_path, _ = runner_env
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
    assert yf_called["n"] == 0, (
        "yfinance.download MUST NOT be called in persist mode "
        "(Codex R1 M#1)"
    )


# Codex R1 M#2 closure: empty yfinance response raises ClickException
# with operator hint to use --window-bars-file. Silently emitting
# bars=[] hands an unusable dispatch payload to the subagent.
def test_emit_payload_empty_yfinance_raises_with_file_override_hint(
    runner_env, monkeypatch,
) -> None:
    from swing.patterns import labeling_bars
    import pandas as pd

    monkeypatch.setattr(
        labeling_bars.yf, "download",
        lambda *a, **k: pd.DataFrame(),
    )

    runner, cfg_path, _ = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "label-exemplars",
        "--ticker", "DELISTED",
        "--start", "2024-01-01",
        "--end", "2024-02-01",
        "--pattern-class", "vcp",
    ])
    assert r.exit_code != 0
    combined = (r.output or "") + str(r.exception or "")
    assert "no bars" in combined.lower()
    assert "--window-bars-file" in combined


# Codex R1 M#3 closure: malformed JSON string at structural_evidence_json
# must be rejected with a clear error (not silently persisted).
def test_persist_rejects_malformed_json_string_evidence(
    runner_env, tmp_path: Path,
) -> None:
    silver = {
        "evaluation": "confirmed",
        "confidence": "medium",
        "structural_evidence_json": "not valid json at all {[",
        "geometric_evidence_narrative": "Narrative.",
    }
    silver_path = tmp_path / "malformed_evidence.json"
    silver_path.write_text(json.dumps(silver), encoding="utf-8")

    runner, cfg_path, _ = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "label-exemplars",
        "--ticker", "ABC",
        "--start", "2024-01-01",
        "--end", "2024-02-01",
        "--pattern-class", "vcp",
        "--silver-response-file", str(silver_path),
    ])
    assert r.exit_code != 0
    combined = (r.output or "") + str(r.exception or "")
    assert "not valid JSON" in combined or "shape invalid" in combined


# Codex R1 M#3 closure: non-dict JSON value (e.g. a JSON array string) at
# structural_evidence_json must be rejected.
def test_persist_rejects_json_array_string_evidence(
    runner_env, tmp_path: Path,
) -> None:
    silver = {
        "evaluation": "confirmed",
        "confidence": "medium",
        "structural_evidence_json": "[1, 2, 3]",
        "geometric_evidence_narrative": "Narrative.",
    }
    silver_path = tmp_path / "array_evidence.json"
    silver_path.write_text(json.dumps(silver), encoding="utf-8")

    runner, cfg_path, _ = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "label-exemplars",
        "--ticker", "ABC",
        "--start", "2024-01-01",
        "--end", "2024-02-01",
        "--pattern-class", "vcp",
        "--silver-response-file", str(silver_path),
    ])
    assert r.exit_code != 0
    combined = (r.output or "") + str(r.exception or "")
    assert "decode to a JSON object" in combined or (
        "shape invalid" in combined
    )


# Codex R1 M#6 closure: --window-bars-file content must be a list of dicts
# with the canonical OHLCV keys. Bad shapes must raise ClickException.
def test_window_bars_file_rejects_non_list_top_level(
    runner_env, tmp_path: Path,
) -> None:
    bars_path = tmp_path / "bad_bars.json"
    bars_path.write_text(
        json.dumps({"not": "a list"}), encoding="utf-8",
    )
    runner, cfg_path, _ = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "label-exemplars",
        "--ticker", "ABC",
        "--start", "2024-01-01",
        "--end", "2024-02-01",
        "--pattern-class", "vcp",
        "--window-bars-file", str(bars_path),
    ])
    assert r.exit_code != 0
    combined = (r.output or "") + str(r.exception or "")
    assert "JSON array" in combined or "top-level" in combined


def test_window_bars_file_rejects_bar_missing_required_keys(
    runner_env, tmp_path: Path,
) -> None:
    bars_path = tmp_path / "incomplete_bar.json"
    bars_path.write_text(
        json.dumps([
            {"date": "2024-01-02", "open": 10.0, "high": 11.0}
            # missing low/close/volume
        ]),
        encoding="utf-8",
    )
    runner, cfg_path, _ = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "label-exemplars",
        "--ticker", "ABC",
        "--start", "2024-01-01",
        "--end", "2024-02-01",
        "--pattern-class", "vcp",
        "--window-bars-file", str(bars_path),
    ])
    assert r.exit_code != 0
    combined = (r.output or "") + str(r.exception or "")
    assert "missing required" in combined or "OHLCV" in combined


def test_label_exemplars_payload_window_bars_file_overrides_autofetch(
    runner_env, monkeypatch, tmp_path: Path,
) -> None:
    """When --window-bars-file is supplied, the helper auto-fetch path
    MUST NOT be invoked; operator-supplied bars take precedence (fixture-
    pinned reproducibility per T-A.1.5b brief section 1.3 Option B).
    """
    from swing.patterns import labeling_bars

    fetch_called = {"n": 0}

    def fake_download(*args, **kwargs):
        fetch_called["n"] += 1
        return None

    monkeypatch.setattr(labeling_bars.yf, "download", fake_download)

    pinned_bars = [
        {"date": "2020-07-01", "open": 23.65, "high": 24.225,
         "low": 23.585, "close": 23.72, "volume": 21733800},
    ]
    bars_path = tmp_path / "pinned_bars.json"
    bars_path.write_text(json.dumps(pinned_bars), encoding="utf-8")

    runner, cfg_path, _ = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path),
        "patterns", "label-exemplars",
        "--ticker", "SNAP",
        "--start", "2020-07-01",
        "--end", "2020-07-01",
        "--pattern-class", "vcp",
        "--window-bars-file", str(bars_path),
    ])
    assert r.exit_code == 0, r.output
    assert fetch_called["n"] == 0, (
        "yfinance.download MUST NOT be called when --window-bars-file is set"
    )

    payload = json.loads(r.output)
    assert payload["window_payload"]["bars"] == pinned_bars
