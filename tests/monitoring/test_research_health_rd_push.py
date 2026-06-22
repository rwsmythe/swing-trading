"""18-H.7 Tasks 2/3 -- the edge-triggered research-health RED push helper.

Drives the PRODUCTION push helper (push_research_health_red_to_rd) +
_read_prior_overall over a TMP comms_root, never the live comms/ tree. The edge
is current.overall == "red" AND prior_overall != "red" (covers green/yellow->red
AND the absent/corrupt(None)->red first-ever-RED case). The push is best-effort:
any failure is swallowed + logged, never raised.
"""
from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

from swing.monitoring.research_health import (
    ResearchHealthCheck,
    ResearchHealthStatus,
    _read_prior_overall,
    push_research_health_red_to_rd,
)

# load role_mail the not-a-package way (to inspect the inbox frontmatter)
_RM = Path(__file__).resolve().parents[2] / "scripts" / "role_mail.py"
_spec = importlib.util.spec_from_file_location("role_mail", _RM)
role_mail = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(role_mail)


def _red_status(detail="ZZZ@2026-06-20"):
    return ResearchHealthStatus(overall="red", checks=[ResearchHealthCheck(
        key="temporal_log_finiteness", status="red",
        summary="3 post-baseline non-finite OHLC observation(s)", detail=detail)])


def _yellow_status():
    return ResearchHealthStatus(overall="yellow", checks=[ResearchHealthCheck(
        key="drumbeat_liveness", status="yellow", summary="5 day(s) old",
        detail="age->yellow")])


def _green_status():
    return ResearchHealthStatus(overall="green", checks=[ResearchHealthCheck(
        key="temporal_log_finiteness", status="green", summary="0 non-finite",
        detail=None)])


def _rd_inbox(comms_root):
    d = Path(comms_root) / "rd" / "inbox"
    return sorted(d.glob("*.md")) if d.is_dir() else []


# --- trigger discrimination ------------------------------------------------

def test_red_with_prior_not_red_posts_one_status_to_rd(tmp_path):
    comms = tmp_path / "comms"
    posted = push_research_health_red_to_rd(
        _red_status(), run_id=104, prior_overall="green", comms_root=comms)
    assert posted is True
    files = _rd_inbox(comms)
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert "from: pipeline" in text
    assert "to: rd" in text
    assert "type: status" in text


def test_red_with_prior_red_does_not_post(tmp_path):
    comms = tmp_path / "comms"
    posted = push_research_health_red_to_rd(
        _red_status(), run_id=1, prior_overall="red", comms_root=comms)
    assert posted is False
    assert _rd_inbox(comms) == []


def test_yellow_does_not_post(tmp_path):
    comms = tmp_path / "comms"
    posted = push_research_health_red_to_rd(
        _yellow_status(), run_id=1, prior_overall="green", comms_root=comms)
    assert posted is False
    assert _rd_inbox(comms) == []


def test_green_does_not_post(tmp_path):
    comms = tmp_path / "comms"
    posted = push_research_health_red_to_rd(
        _green_status(), run_id=1, prior_overall="yellow", comms_root=comms)
    assert posted is False
    assert _rd_inbox(comms) == []


def test_first_ever_red_absent_prior_posts(tmp_path):
    comms = tmp_path / "comms"
    posted = push_research_health_red_to_rd(
        _red_status(), run_id=7, prior_overall=None, comms_root=comms)
    assert posted is True
    assert len(_rd_inbox(comms)) == 1


# --- content ---------------------------------------------------------------

def test_posted_message_carries_keys_summary_detail_runid_pointer(tmp_path):
    comms = tmp_path / "comms"
    push_research_health_red_to_rd(
        _red_status(detail="ZZZ@2026-06-20 non-finite Close"),
        run_id=104, prior_overall="green", comms_root=comms)
    text = _rd_inbox(comms)[0].read_text(encoding="utf-8")
    assert "temporal_log_finiteness" in text          # the red check key
    assert "3 post-baseline non-finite" in text        # the summary substring
    assert "ZZZ@2026-06-20 non-finite Close" in text   # the LOAD-BEARING detail
    assert "104" in text                               # the run id
    assert "exports/research/health/latest.json" in text
    assert "/health/research" in text                  # the GUI pointer


def test_detail_none_renders_placeholder_not_crash(tmp_path):
    comms = tmp_path / "comms"
    status = ResearchHealthStatus(overall="red", checks=[ResearchHealthCheck(
        key="structural_integrity", status="red",
        summary="1 orphan observation(s)", detail=None)])
    posted = push_research_health_red_to_rd(
        status, run_id=5, prior_overall="green", comms_root=comms)
    assert posted is True
    text = _rd_inbox(comms)[0].read_text(encoding="utf-8")
    assert "(none)" in text


def test_non_ascii_detail_is_sanitized(tmp_path):
    # Codex R1 MINOR: a non-ASCII detail (a ticker / future value is not
    # ASCII-constrained at the schema) must not reach the mail body verbatim --
    # _compose_red_push backslash-escapes it (the cp1252 discipline). Assert the
    # raw non-ASCII glyph is absent and the message is pure ASCII.
    comms = tmp_path / "comms"
    status = ResearchHealthStatus(overall="red", checks=[ResearchHealthCheck(
        key="temporal_log_finiteness", status="red",
        summary="non-finite", detail="café — → oops")])
    posted = push_research_health_red_to_rd(
        status, run_id=1, prior_overall="green", comms_root=comms)
    assert posted is True
    raw = _rd_inbox(comms)[0].read_bytes()
    assert b"\xc3\xa9" not in raw  # the UTF-8 'e-acute' must not appear
    body_text = raw.decode("utf-8")
    # the message content (sans the always-present headers) is ASCII
    assert body_text.encode("ascii", "strict")  # would raise if non-ASCII


def test_subject_names_red_and_check_keys(tmp_path):
    comms = tmp_path / "comms"
    push_research_health_red_to_rd(
        _red_status(), run_id=1, prior_overall="green", comms_root=comms)
    text = _rd_inbox(comms)[0].read_text(encoding="utf-8")
    # the subject frontmatter line names RED + the fired key
    subject_line = next(
        ln for ln in text.splitlines() if ln.startswith("subject:"))
    assert "RED" in subject_line
    assert "temporal_log_finiteness" in subject_line


# --- _read_prior_overall ---------------------------------------------------

def test_read_prior_overall_absent_returns_none(tmp_path, monkeypatch):
    artifact = tmp_path / "health" / "latest.json"  # does not exist
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: artifact)
    assert _read_prior_overall() is None


def test_read_prior_overall_unparseable_returns_none(tmp_path, monkeypatch):
    artifact = tmp_path / "health" / "latest.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("{ not json", encoding="utf-8")
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: artifact)
    assert _read_prior_overall() is None


def test_read_prior_overall_reads_overall(tmp_path, monkeypatch):
    artifact = tmp_path / "health" / "latest.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{"monitor": "research_measurement", "overall": "red", "checks": []}',
        encoding="utf-8")
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: artifact)
    assert _read_prior_overall() == "red"


def test_read_prior_overall_non_str_overall_returns_none(tmp_path, monkeypatch):
    artifact = tmp_path / "health" / "latest.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text('{"overall": 123}', encoding="utf-8")
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: artifact)
    assert _read_prior_overall() is None


def test_read_prior_overall_non_dict_top_level_returns_none(tmp_path, monkeypatch):
    artifact = tmp_path / "health" / "latest.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("[1, 2]", encoding="utf-8")
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: artifact)
    assert _read_prior_overall() is None


def test_read_prior_overall_explicit_out_path(tmp_path):
    artifact = tmp_path / "latest.json"
    artifact.write_text('{"overall": "yellow"}', encoding="utf-8")
    assert _read_prior_overall(artifact) == "yellow"


def test_read_prior_overall_deeply_nested_returns_none(tmp_path):
    # Codex R1 MAJOR: a deeply-nested JSON makes json.loads raise RecursionError
    # (a RuntimeError, NOT OSError/ValueError) -> must degrade to None, never
    # escape (it runs before the writer in _step_research_health). Pre-fix the
    # (OSError, ValueError)-only except let RecursionError propagate -> this would
    # raise rather than return None.
    artifact = tmp_path / "latest.json"
    artifact.write_text("[" * 5000 + "]" * 5000, encoding="utf-8")
    assert _read_prior_overall(artifact) is None


# --- test-safe -------------------------------------------------------------

def test_push_targets_tmp_comms_root_not_live(tmp_path):
    comms = tmp_path / "comms"
    posted = push_research_health_red_to_rd(
        _red_status(), run_id=1, prior_overall="green", comms_root=comms)
    assert posted is True
    # the message landed under tmp_path (never the live repo comms/)
    landed = list(comms.rglob("*.md"))
    assert len(landed) == 1
    assert str(tmp_path) in str(landed[0])


# --- best-effort (Task 3 helper-level) -------------------------------------

def test_push_swallows_post_failure_and_logs(tmp_path, caplog):
    # A regular FILE where the comms-root directory is expected forces
    # post_message's mkdir to raise inside the helper's try -> swallowed.
    bad = tmp_path / "comms"
    bad.write_text("x", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        posted = push_research_health_red_to_rd(
            _red_status(), run_id=1, prior_overall="green", comms_root=bad)
    assert posted is False
    assert any("push" in r.getMessage().lower() for r in caplog.records)
