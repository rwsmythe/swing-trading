from __future__ import annotations

import json

import pytest

from research.harness.shadow_expectancy import output


def test_assert_ascii_rejects_non_ascii():
    with pytest.raises(UnicodeEncodeError):
        output._assert_ascii("em—dash")


def test_write_results_and_ledger_csv(tmp_path):
    rows = [{"ticker": "AAA", "hypothesis": "A+ baseline", "bucket": "aplus",
             "realistic_r": "1.50", "favorable_r": "1.50", "exit_reason": "initial_stop",
             "open_at_horizon": "False", "entry_bar_ambiguous": "False",
             "detection_date": "2026-05-29", "run_id": "1"}]
    p = tmp_path / "results.csv"
    output.write_results_csv(rows, p)
    assert "A+ baseline" in p.read_text(encoding="utf-8")


def test_write_per_session_legs_csv(tmp_path):
    rows = [{"ticker": "AAA", "hypothesis": "A+ baseline", "action": "exit",
             "qty": "50.0", "price": "10.60", "price_favorable": "11.00",
             "session": "2026-06-04"}]
    p = tmp_path / "per_session.csv"
    output.write_per_session_csv(rows, p)
    text = p.read_text(encoding="utf-8")
    assert "price_favorable" in text   # m3: both arms reconstructable from the ledger
    assert "11.00" in text


def test_write_summary_and_manifest(tmp_path):
    output.write_summary_md(["# Shadow-expectancy", "headline: H1 ..."], tmp_path / "s.md")
    output.write_manifest_json({"harness_version": "0.1.0"}, tmp_path / "m.json")
    m = json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))
    assert m["l2_lock_preserved"] is True


def test_results_header_includes_entry_bar_weak_close():
    from research.harness.shadow_expectancy.output import RESULTS_HEADER
    assert "entry_bar_weak_close" in RESULTS_HEADER
    assert RESULTS_HEADER[-1] == "entry_bar_weak_close"   # appended (additive)
