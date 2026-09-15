"""scripts/weekly_glance.py -- the RD watch-standard section-2 glance.

Two defects fixed 2026-09-15 (RD-owned instrument, no swing/ touch):

1. T3 cried wolf on every glance since June: the script had no way to know
   the golden gate (watch standard section 2.2) was DONE, so a nonzero
   trigger rate -- the standing state of a working engine -- flagged forever.
   The gate date is now a recorded constant; T3 fires only while it is None.
2. The `trigger` column took the FIRST "trigger rate" line in summary.md,
   which is whichever hypothesis section the emitter prints first (the A+
   baseline: 7/12), not the broad-watch cohort the weekly tier watches
   (737/1185). The column now reads the Broad-watch section explicitly.

Fixtures mirror the real emitter's section layout (A+ section BEFORE
Broad-watch), so a first-match regex is discriminated from a section read.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = REPO_ROOT / "scripts" / "weekly_glance.py"


def _load():
    spec = importlib.util.spec_from_file_location("_weekly_glance", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_SUMMARY = """# Shadow-expectancy engine - summary

## Denominator funnel (detection-level)
total_detections=6655 collapsed_duplicate=5324 unique_signals=1331

## Unattributed signals (pre-/non-attribution; spec 7.1)
  total_unattributed=0

## A+ baseline
HEADLINE realistic closed-only mean R=-0.590 (n=7)
win rate (closed-only) 1/7
trigger rate {aplus}; per-signal expectancy [realistic]=-0.344

## Broad-watch baseline
HEADLINE realistic closed-only mean R=-0.384 (n=687)
win rate (closed-only) 149/687
trigger rate {bw}; per-signal expectancy [realistic]=-0.193

## Near-A+ defensible: extension test
trigger rate 12/17; per-signal expectancy [realistic]=-0.317
"""


def _plant(exports: Path, stamp: str, *, aplus: str, bw: str | None) -> None:
    d = exports / f"shadow-expectancy-{stamp}"
    d.mkdir(parents=True)
    text = _SUMMARY.format(aplus=aplus, bw=bw or "0/0")
    if bw is None:
        # Drop the whole Broad-watch section: the column must answer "?",
        # never fall through to another section's number.
        head, _, tail = text.partition("## Broad-watch baseline")
        text = head + "## Near-A+" + tail.partition("## Near-A+")[2]
    (d / "summary.md").write_text(text, encoding="utf-8")


@pytest.fixture
def glance(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "EXPORTS", tmp_path)
    return mod


def _row_for(out: str, stamp: str) -> str:
    return next(line for line in out.splitlines() if stamp in line)


def test_trigger_column_reads_broad_watch_section_not_first_match(
        glance, tmp_path, capsys):
    _plant(tmp_path, "20260915T034421Z", aplus="7/12", bw="737/1185")
    glance.scan_artifacts(7)
    row = _row_for(capsys.readouterr().out, "20260915T034421Z")
    assert row.rstrip().endswith("737/1185"), row
    assert "7/12" not in row


def test_trigger_column_is_unknown_without_broad_watch_section(
        glance, tmp_path, capsys):
    _plant(tmp_path, "20260915T034421Z", aplus="7/12", bw=None)
    glance.scan_artifacts(7)
    row = _row_for(capsys.readouterr().out, "20260915T034421Z")
    assert row.rstrip().endswith("?"), row


def test_t3_is_silent_once_the_golden_gate_is_recorded(
        glance, tmp_path, capsys):
    # The shipped constant records the 2026-06-10 gate (standard section 2.2).
    assert glance.T3_GOLDEN_GATE_PASSED_ON is not None
    _plant(tmp_path, "20260915T034421Z", aplus="7/12", bw="737/1185")
    flags = glance.scan_artifacts(7)
    assert not [f for f in flags if f.startswith("T3")], flags
    out = capsys.readouterr().out
    assert "golden gate" in out and str(glance.T3_GOLDEN_GATE_PASSED_ON) in out


def test_t3_fires_while_the_golden_gate_is_unrecorded(
        glance, tmp_path, monkeypatch):
    monkeypatch.setattr(glance, "T3_GOLDEN_GATE_PASSED_ON", None)
    _plant(tmp_path, "20260915T034421Z", aplus="0/12", bw="1/1185")
    flags = glance.scan_artifacts(7)
    t3 = [f for f in flags if f.startswith("T3")]
    assert len(t3) == 1 and "1/1185" in t3[0], flags


def test_t3_does_not_fire_on_a_zero_numerator_even_when_unrecorded(
        glance, tmp_path, monkeypatch):
    monkeypatch.setattr(glance, "T3_GOLDEN_GATE_PASSED_ON", None)
    _plant(tmp_path, "20260915T034421Z", aplus="7/12", bw="0/1185")
    flags = glance.scan_artifacts(7)
    assert not [f for f in flags if f.startswith("T3")], flags
