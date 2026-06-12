"""Tests for scripts/role_mail.py -- the inter-role file mailbox CLI.

All tests pass --comms-root <tmp_path> so the real comms/ tree is never
touched. role_mail.py reads no home-dir paths, so no USERPROFILE/HOME
monkeypatch is needed here (kept in mind per the CLAUDE.md gotcha).
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "role_mail.py"
_spec = importlib.util.spec_from_file_location("role_mail", _MODULE_PATH)
role_mail = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(role_mail)


@pytest.fixture
def comms(tmp_path):
    return tmp_path / "comms"


def _post(comms_root, **kw):
    argv = ["post", "--comms-root", str(comms_root)]
    for flag in ("from", "to", "type", "subject", "body", "body_file", "thread"):
        val = kw.get(flag)
        if val is not None:
            argv += [f"--{flag.replace('_', '-')}", val]
    return role_mail.main(argv)


def _inbox(comms_root, role):
    d = Path(comms_root) / role / "inbox"
    return sorted(d.glob("*.md")) if d.is_dir() else []


def _read_dir(comms_root, role):
    d = Path(comms_root) / role / "read"
    return sorted(d.glob("*.md")) if d.is_dir() else []


# --- round-trip post/list/read/peek ---------------------------------------

def test_post_creates_inbox_file_with_frontmatter(comms):
    rc = _post(comms, **{"from": "charc", "to": "rd", "type": "status",
                         "subject": "Arc 1 shipped", "body": "All green."})
    assert rc == 0
    files = _inbox(comms, "rd")
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "from: charc" in text
    assert "to: rd" in text
    assert "type: status" in text
    assert "subject: Arc 1 shipped" in text
    assert "posted:" in text
    assert "All green." in text


def test_filename_shape(comms):
    _post(comms, **{"from": "charc", "to": "rd", "type": "fyi",
                    "subject": "Hello World!! 123", "body": "x"})
    name = _inbox(comms, "rd")[0].name
    # <stamp>-<from>-<slug>.md ; slug is [a-z0-9-]
    assert name.endswith(".md")
    parts = name[:-3].split("-")
    assert "charc" in parts
    assert "hello" in name and "world" in name


def test_list_shows_inbox(comms, capsys):
    _post(comms, **{"from": "rd", "to": "charc", "type": "query",
                    "subject": "Need timing data", "body": "?"})
    capsys.readouterr()
    rc = role_mail.main(["list", "--role", "charc", "--comms-root", str(comms)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Need timing data" in out
    assert "rd" in out
    assert "query" in out


def test_read_prints_and_moves_inbox_to_read(comms, capsys):
    _post(comms, **{"from": "charc", "to": "rd", "type": "fyi",
                    "subject": "Move me", "body": "payload-body-text"})
    assert len(_inbox(comms, "rd")) == 1
    capsys.readouterr()
    rc = role_mail.main(["read", "--role", "rd", "--all",
                         "--comms-root", str(comms)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "payload-body-text" in out
    assert len(_inbox(comms, "rd")) == 0
    assert len(_read_dir(comms, "rd")) == 1


def test_read_by_id(comms, capsys):
    _post(comms, **{"from": "charc", "to": "rd", "type": "fyi",
                    "subject": "one", "body": "b1"})
    _post(comms, **{"from": "charc", "to": "rd", "type": "fyi",
                    "subject": "two", "body": "b2"})
    target = _inbox(comms, "rd")[0].name
    capsys.readouterr()
    rc = role_mail.main(["read", "--role", "rd", "--id", target,
                         "--comms-root", str(comms)])
    assert rc == 0
    capsys.readouterr()
    assert len(_inbox(comms, "rd")) == 1  # only one moved
    assert len(_read_dir(comms, "rd")) == 1


def test_peek_does_not_ack(comms, capsys):
    _post(comms, **{"from": "charc", "to": "rd", "type": "fyi",
                    "subject": "glance", "body": "stay-put"})
    capsys.readouterr()
    rc = role_mail.main(["peek", "--role", "rd", "--comms-root", str(comms)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "stay-put" in out
    assert len(_inbox(comms, "rd")) == 1  # NOT moved
    assert len(_read_dir(comms, "rd")) == 0


# --- multi-recipient -------------------------------------------------------

def test_multi_recipient_post(comms):
    rc = _post(comms, **{"from": "orchestrator", "to": "charc,rd",
                         "type": "return_report", "subject": "Stage 1 done",
                         "body": "report body"})
    assert rc == 0
    assert len(_inbox(comms, "charc")) == 1
    assert len(_inbox(comms, "rd")) == 1


# --- L1 information-vs-authority enforcement -------------------------------

def test_decision_request_to_non_operator_rejected(comms):
    rc = _post(comms, **{"from": "charc", "to": "rd", "type": "decision_request",
                         "subject": "approve?", "body": "x"})
    assert rc == 1
    # no file written anywhere under comms root
    assert list(Path(comms).rglob("*.md")) == []


def test_decision_request_to_operator_allowed(comms):
    rc = _post(comms, **{"from": "charc", "to": "operator",
                         "type": "decision_request", "subject": "approve?",
                         "body": "x"})
    assert rc == 0
    assert len(_inbox(comms, "operator")) == 1


def test_decision_request_mixed_recipients_rejected(comms):
    rc = _post(comms, **{"from": "charc", "to": "operator,charc",
                         "type": "decision_request", "subject": "approve?",
                         "body": "x"})
    assert rc == 1
    assert list(Path(comms).rglob("*.md")) == []


# --- validation ------------------------------------------------------------

def test_invalid_from_role_rejected(comms):
    rc = _post(comms, **{"from": "bogus", "to": "rd", "type": "fyi",
                         "subject": "s", "body": "x"})
    assert rc == 1
    assert list(Path(comms).rglob("*.md")) == []


def test_invalid_to_role_rejected(comms):
    rc = _post(comms, **{"from": "charc", "to": "bogus", "type": "fyi",
                         "subject": "s", "body": "x"})
    assert rc == 1
    assert list(Path(comms).rglob("*.md")) == []


def test_orchestrator_cannot_receive(comms):
    # orchestrator is a valid --from but NOT a valid --to (no inbox in V1)
    rc = _post(comms, **{"from": "charc", "to": "orchestrator", "type": "fyi",
                         "subject": "s", "body": "x"})
    assert rc == 1


def test_invalid_type_rejected(comms):
    rc = _post(comms, **{"from": "charc", "to": "rd", "type": "bogus",
                         "subject": "s", "body": "x"})
    assert rc == 1
    assert list(Path(comms).rglob("*.md")) == []


# --- filename collision ----------------------------------------------------

def test_filename_collision_suffix(comms, monkeypatch):
    fixed = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(role_mail, "_now", lambda: fixed)
    for _ in range(3):
        _post(comms, **{"from": "charc", "to": "rd", "type": "fyi",
                        "subject": "same subject", "body": "x"})
    names = sorted(p.name for p in _inbox(comms, "rd"))
    assert len(names) == 3
    # exactly one base, one -2, one -3
    assert any(n.endswith("-2.md") for n in names)
    assert any(n.endswith("-3.md") for n in names)


# --- ASCII-only console output ---------------------------------------------

def test_post_output_is_ascii(comms, capsys):
    _post(comms, **{"from": "charc", "to": "rd", "type": "fyi",
                    "subject": "ascii check", "body": "x"})
    out = capsys.readouterr().out
    out.encode("cp1252")  # must not raise


def test_list_and_read_output_is_ascii(comms, capsys):
    _post(comms, **{"from": "rd", "to": "charc", "type": "status",
                    "subject": "ascii too", "body": "body"})
    capsys.readouterr()
    role_mail.main(["list", "--role", "charc", "--comms-root", str(comms)])
    role_mail.main(["read", "--role", "charc", "--all",
                    "--comms-root", str(comms)])
    out = capsys.readouterr().out
    out.encode("cp1252")  # must not raise


def test_rejection_message_is_ascii(comms, capsys):
    _post(comms, **{"from": "charc", "to": "rd", "type": "decision_request",
                    "subject": "approve?", "body": "x"})
    err = capsys.readouterr().err
    err.encode("cp1252")  # must not raise


# --- body sources ----------------------------------------------------------

def test_body_from_file(comms, tmp_path):
    bf = tmp_path / "body.txt"
    bf.write_text("file-sourced-body", encoding="utf-8")
    rc = _post(comms, **{"from": "charc", "to": "rd", "type": "fyi",
                         "subject": "from file", "body_file": str(bf)})
    assert rc == 0
    assert "file-sourced-body" in _inbox(comms, "rd")[0].read_text(encoding="utf-8")


def test_thread_field_recorded(comms):
    _post(comms, **{"from": "charc", "to": "rd", "type": "status",
                    "subject": "threaded", "body": "x", "thread": "arc-1"})
    text = _inbox(comms, "rd")[0].read_text(encoding="utf-8")
    assert "thread: arc-1" in text
