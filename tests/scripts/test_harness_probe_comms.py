"""Tests for the comms-mailbox section of scripts/harness_probe.py.

Exercises the pure _scan_comms() helper over a tmp_path comms tree (never the
real comms/). No home-dir paths are touched.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "harness_probe.py"
_spec = importlib.util.spec_from_file_location("harness_probe", _MODULE_PATH)
harness_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(harness_probe)

NOW = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)


def _make_msg(comms: Path, role: str, when: datetime, sender: str = "charc",
              slug: str = "msg") -> Path:
    inbox = comms / role / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    stamp = when.strftime("%Y%m%dT%H%M%SZ")
    path = inbox / f"{stamp}-{sender}-{slug}.md"
    path.write_text(f"---\nfrom: {sender}\nto: {role}\n---\nbody\n",
                    encoding="utf-8")
    return path


@pytest.fixture
def comms(tmp_path):
    return tmp_path / "comms"


def test_missing_dir_is_info_only(comms):
    rows = harness_probe._scan_comms(comms, NOW)
    assert len(rows) == 1
    assert rows[0][0] == "INFO"
    assert "missing" in rows[0][1].lower()


def test_fresh_messages_info_no_attention(comms):
    _make_msg(comms, "charc", NOW - timedelta(days=1))
    _make_msg(comms, "rd", NOW - timedelta(days=2))
    rows = harness_probe._scan_comms(comms, NOW)
    assert all(level == "INFO" for level, _ in rows)
    joined = " ".join(line for _, line in rows)
    assert "charc" in joined and "rd" in joined


def test_stale_unread_triggers_attention(comms):
    _make_msg(comms, "charc", NOW - timedelta(days=9))
    rows = harness_probe._scan_comms(comms, NOW)
    attn = [line for level, line in rows if level == "ATTENTION"]
    assert any("charc" in line for line in attn)
    assert any("9" in line or "old" in line.lower() for line in attn)


def test_boundary_7_days_not_stale(comms):
    # exactly 7 days old must NOT fire (strictly older-than-7 is the rule)
    _make_msg(comms, "charc", NOW - timedelta(days=7))
    rows = harness_probe._scan_comms(comms, NOW)
    assert all(level == "INFO" for level, _ in rows)


def test_fractional_over_7_days_is_stale(comms):
    # 7 days + 12 hours is strictly older than 7 days -> ATTENTION (the int
    # .days floor would miss this; the fix compares timedeltas).
    _make_msg(comms, "charc", NOW - timedelta(days=7, hours=12))
    rows = harness_probe._scan_comms(comms, NOW)
    assert any(level == "ATTENTION" for level, _ in rows)


def test_ceil_day_display_rounds_up_just_over_7d(comms):
    # 7 days + 1 second must display as "8d", never "7d (>7d)".
    _make_msg(comms, "charc", NOW - timedelta(days=7, seconds=1))
    rows = harness_probe._scan_comms(comms, NOW)
    attn = [line for level, line in rows if level == "ATTENTION"]
    assert any("8d" in line for line in attn)


def test_operator_line_when_nonzero(comms):
    _make_msg(comms, "operator", NOW - timedelta(hours=1), slug="approve")
    rows = harness_probe._scan_comms(comms, NOW)
    joined = " ".join(line for _, line in rows)
    assert "operator" in joined
    # a dedicated awaiting-operator line is present
    assert any("operator" in line and "await" in line.lower()
               for _, line in rows)


def test_no_awaiting_operator_line_when_zero(comms):
    _make_msg(comms, "charc", NOW - timedelta(hours=1))
    rows = harness_probe._scan_comms(comms, NOW)
    assert not any("await" in line.lower() for _, line in rows)


def test_output_is_ascii(comms):
    _make_msg(comms, "charc", NOW - timedelta(days=9))
    _make_msg(comms, "operator", NOW - timedelta(hours=1))
    rows = harness_probe._scan_comms(comms, NOW)
    for _, line in rows:
        line.encode("cp1252")  # must not raise
