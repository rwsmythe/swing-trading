"""Tests for scripts/role_mail.py -- the inter-role file mailbox CLI.

All tests pass --comms-root <tmp_path> so the real comms/ tree is never
touched. role_mail.py reads no home-dir paths, so no USERPROFILE/HOME
monkeypatch is needed here (kept in mind per the CLAUDE.md gotcha).
"""

from __future__ import annotations

import argparse
import importlib.util
from datetime import UTC, datetime, timedelta
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


# NOTE: orchestrator IS a valid --to, and since 21-D it is a SINGULAR inbox like
# every other role -- a bare `--to orchestrator` is the ONLY address form, and a
# `:<session_id>` suffix is REJECTED. The 21-D section below asserts that
# contract. (This replaced the original test_orchestrator_cannot_receive, and
# then the G6 Arc-A newest-live / explicit-:<sid> pair.)


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


# --- round-1 review hardening ----------------------------------------------

def test_console_ascii_with_unicode_subject_and_body(comms, capsys):
    # non-cp1252 chars in subject/body must NOT crash the console paths.
    _post(comms, **{"from": "charc", "to": "rd", "type": "fyi",
                    "subject": "cafe check OK ja 'pan'",
                    "body": "emoji rocket and CJK below"})
    # write a message file with genuinely non-cp1252 content directly so the
    # console readers must sanitize (post args themselves stay ASCII here).
    msg = _inbox(comms, "rd")[0]
    msg.write_text(msg.read_text(encoding="utf-8") + "\nUnicode: \U0001F680 日本",
                   encoding="utf-8")
    capsys.readouterr()
    role_mail.main(["list", "--role", "rd", "--comms-root", str(comms)])
    role_mail.main(["peek", "--role", "rd", "--comms-root", str(comms)])
    role_mail.main(["read", "--role", "rd", "--all", "--comms-root", str(comms)])
    out = capsys.readouterr().out
    out.encode("cp1252")  # must not raise


def test_unicode_subject_console_ascii(comms, capsys):
    # a subject with real non-cp1252 chars, sanitized on the console.
    rc = role_mail.main(["post", "--comms-root", str(comms), "--from", "charc",
                         "--to", "rd", "--type", "fyi",
                         "--subject", "rocket \U0001F680 nihon 日本",
                         "--body", "x"])
    assert rc == 0
    capsys.readouterr()
    role_mail.main(["list", "--role", "rd", "--comms-root", str(comms)])
    out = capsys.readouterr().out
    out.encode("cp1252")  # must not raise


def test_newline_in_subject_rejected(comms):
    rc = role_mail.main(["post", "--comms-root", str(comms), "--from", "charc",
                         "--to", "rd", "--type", "fyi",
                         "--subject", "ok\ntype: decision_request",
                         "--body", "x"])
    assert rc == 1
    assert list(Path(comms).rglob("*.md")) == []


def test_read_archive_not_overwritten_on_name_collision(comms, monkeypatch):
    fixed = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(role_mail, "_now", lambda: fixed)
    # post A, read it (-> read/), then post B with identical stamp+subject.
    _post(comms, **{"from": "charc", "to": "rd", "type": "fyi",
                    "subject": "same", "body": "AAA"})
    role_mail.main(["read", "--role", "rd", "--all", "--comms-root", str(comms)])
    _post(comms, **{"from": "charc", "to": "rd", "type": "fyi",
                    "subject": "same", "body": "BBB"})
    role_mail.main(["read", "--role", "rd", "--all", "--comms-root", str(comms)])
    archived = _read_dir(comms, "rd")
    assert len(archived) == 2  # neither archived message was overwritten
    bodies = "".join(p.read_text(encoding="utf-8") for p in archived)
    assert "AAA" in bodies and "BBB" in bodies


def test_multi_recipient_post_is_atomic_on_failure(comms, monkeypatch):
    calls = {"n": 0}
    orig = role_mail._write_temp

    def boom(final, content):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("simulated disk full")
        return orig(final, content)

    monkeypatch.setattr(role_mail, "_write_temp", boom)
    rc = _post(comms, **{"from": "orchestrator", "to": "charc,rd",
                         "type": "status", "subject": "atomic", "body": "x"})
    assert rc == 1
    # partial delivery must not happen: no final .md anywhere.
    assert list(Path(comms).rglob("*.md")) == []


def test_multi_recipient_replace_failure_rolls_back(comms, monkeypatch):
    calls = {"n": 0}
    orig = role_mail.os.replace

    def boom(src, dst):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("simulated replace failure")
        return orig(src, dst)

    monkeypatch.setattr(role_mail.os, "replace", boom)
    rc = _post(comms, **{"from": "orchestrator", "to": "charc,rd",
                         "type": "status", "subject": "rollback", "body": "x"})
    assert rc == 1
    # the first recipient's final must be rolled back, no temps left behind.
    assert list(Path(comms).rglob("*.md")) == []
    assert list(Path(comms).rglob("*.tmp")) == []


def test_error_output_ascii_with_unicode_input(comms, capsys):
    # a non-cp1252 --from value must not crash the error path itself.
    rc = role_mail.main(["post", "--comms-root", str(comms),
                         "--from", "\U0001F680nihon", "--to", "rd",
                         "--type", "fyi", "--subject", "s", "--body", "x"])
    assert rc == 1
    err = capsys.readouterr().err
    err.encode("cp1252")  # must not raise


def test_argparse_error_output_is_ascii(capsys):
    # argparse's OWN error path (unrecognized non-cp1252 arg) must stay
    # cp1252-safe -- it runs before main()'s handler, so the parser subclass
    # sanitizes it.
    with pytest.raises(SystemExit):
        role_mail.main(["post", "--from", "charc", "--to", "rd", "--type",
                        "fyi", "--subject", "s", "--body", "x",
                        "--bogus\U0001F680flag"])
    captured = capsys.readouterr()
    (captured.out + captured.err).encode("cp1252")  # must not raise


# --- pure functions: post_message / ack_message (T1, the single-write-path) --
# These are the seam the mail UI writes through. The CLI is now a thin adapter
# over them; the governance/atomicity guarantees must hold at THIS layer, not
# only through argparse.

def test_post_message_returns_committed_paths_and_writes_file(comms):
    paths = role_mail.post_message(
        comms, "charc", ["rd"], "status", "Arc 1 shipped", "All green.")
    assert isinstance(paths, list)
    assert len(paths) == 1
    assert paths[0].is_file()
    assert paths[0] == _inbox(comms, "rd")[0]
    text = paths[0].read_text(encoding="utf-8")
    assert "from: charc" in text
    assert "to: rd" in text
    assert "type: status" in text
    assert "subject: Arc 1 shipped" in text
    assert "All green." in text


def test_post_message_multi_recipient(comms):
    paths = role_mail.post_message(
        comms, "orchestrator", ["charc", "rd"], "return_report",
        "Stage 1 done", "report body")
    assert len(paths) == 2
    assert len(_inbox(comms, "charc")) == 1
    assert len(_inbox(comms, "rd")) == 1


def test_post_message_l1_lock_direct_non_operator_rejected(comms):
    # The L1 governance lock must hold at the pure-function layer (the UI never
    # offers decision_request, but the seam itself stays load-bearing).
    with pytest.raises(role_mail.MailError):
        role_mail.post_message(
            comms, "charc", ["rd"], "decision_request", "approve?", "x")
    assert list(Path(comms).rglob("*.md")) == []


def test_post_message_l1_lock_direct_mixed_recipients_rejected(comms):
    with pytest.raises(role_mail.MailError):
        role_mail.post_message(
            comms, "charc", ["operator", "charc"], "decision_request",
            "approve?", "x")
    assert list(Path(comms).rglob("*.md")) == []


def test_post_message_l1_lock_direct_operator_allowed(comms):
    paths = role_mail.post_message(
        comms, "charc", ["operator"], "decision_request", "approve?", "x")
    assert len(paths) == 1
    assert len(_inbox(comms, "operator")) == 1


def test_post_message_crlf_subject_rejected(comms):
    with pytest.raises(role_mail.MailError):
        role_mail.post_message(
            comms, "charc", ["rd"], "fyi", "ok\ntype: decision_request", "x")
    assert list(Path(comms).rglob("*.md")) == []


def test_post_message_crlf_thread_rejected(comms):
    with pytest.raises(role_mail.MailError):
        role_mail.post_message(
            comms, "charc", ["rd"], "fyi", "ok", "x", thread="a\nb")
    assert list(Path(comms).rglob("*.md")) == []


def test_post_message_invalid_sender_rejected(comms):
    with pytest.raises(role_mail.MailError):
        role_mail.post_message(comms, "bogus", ["rd"], "fyi", "s", "x")
    assert list(Path(comms).rglob("*.md")) == []


def test_post_message_invalid_recipient_rejected(comms):
    with pytest.raises(role_mail.MailError):
        role_mail.post_message(comms, "charc", ["bogus"], "fyi", "s", "x")
    assert list(Path(comms).rglob("*.md")) == []


def test_post_message_empty_recipients_rejected(comms):
    with pytest.raises(role_mail.MailError):
        role_mail.post_message(comms, "charc", [], "fyi", "s", "x")
    assert list(Path(comms).rglob("*.md")) == []


def test_post_message_invalid_type_rejected(comms):
    with pytest.raises(role_mail.MailError):
        role_mail.post_message(comms, "charc", ["rd"], "bogus", "s", "x")
    assert list(Path(comms).rglob("*.md")) == []


def test_post_message_dedupes_recipients(comms):
    paths = role_mail.post_message(
        comms, "charc", ["rd", "rd"], "fyi", "dupe", "x")
    assert len(paths) == 1
    assert len(_inbox(comms, "rd")) == 1


def test_ack_message_moves_inbox_to_read_and_returns_dest(comms):
    role_mail.post_message(comms, "charc", ["operator"], "fyi", "ack me", "body")
    fname = _inbox(comms, "operator")[0].name
    dest = role_mail.ack_message(comms, "operator", fname)
    assert dest.is_file()
    assert dest.parent.name == "read"
    assert len(_inbox(comms, "operator")) == 0
    assert len(_read_dir(comms, "operator")) == 1


def test_ack_message_missing_file_raises(comms):
    # The "already acked / drained via CLI in parallel" case: the UI catches
    # this and renders a friendly flash rather than 500ing.
    role_mail._ensure_tree(comms)
    with pytest.raises(role_mail.MailError):
        role_mail.ack_message(comms, "operator", "nonexistent-file.md")


def test_ack_message_invalid_role_raises(comms):
    with pytest.raises(role_mail.MailError):
        role_mail.ack_message(comms, "bogus", "x.md")


def test_ack_message_rejects_path_traversal(comms):
    # Defense-in-depth (L3): a filename must be a bare basename; a traversal
    # attempt must never reach outside the role's own inbox.
    role_mail.post_message(comms, "charc", ["charc"], "fyi", "victim", "x")
    victim = _inbox(comms, "charc")[0].name
    role_mail._ensure_tree(comms)
    for bad in (f"../charc/inbox/{victim}", "..\\charc\\inbox\\x.md",
                "sub/dir.md"):
        with pytest.raises(role_mail.MailError):
            role_mail.ack_message(comms, "operator", bad)
    # the charc inbox file is untouched
    assert len(_inbox(comms, "charc")) == 1


def test_ack_message_archive_not_overwritten_on_collision(comms, monkeypatch):
    fixed = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(role_mail, "_now", lambda: fixed)
    role_mail.post_message(comms, "charc", ["operator"], "fyi", "same", "AAA")
    f1 = _inbox(comms, "operator")[0].name
    role_mail.ack_message(comms, "operator", f1)
    role_mail.post_message(comms, "charc", ["operator"], "fyi", "same", "BBB")
    f2 = _inbox(comms, "operator")[0].name
    role_mail.ack_message(comms, "operator", f2)
    archived = _read_dir(comms, "operator")
    assert len(archived) == 2
    bodies = "".join(p.read_text(encoding="utf-8") for p in archived)
    assert "AAA" in bodies and "BBB" in bodies


# --- 18-H.7: the 'pipeline' automated-emitter sender -----------------------

def test_pipeline_is_a_valid_sender(comms):
    # 18-H.7 Task 1: the nightly pipeline posts a `status` to rd. Pipeline is an
    # automated-emitter sender (distinct from the human/agent roles).
    rc = _post(comms, **{"from": "pipeline", "to": "rd", "type": "status",
                         "subject": "research-health RED", "body": "overall=red"})
    assert rc == 0
    files = _inbox(comms, "rd")
    assert len(files) == 1
    assert "from: pipeline" in files[0].read_text(encoding="utf-8")


def test_pipeline_decision_request_to_rd_still_rejects(comms, capsys):
    # A decision_request from pipeline to rd STILL rejects. After the
    # codex-auto-review fix the automated-emitter type allowlist (status-only)
    # rejects it BEFORE the L1 gate -- an even stronger guarantee than L1 alone
    # (pipeline can never post a decision_request, to ANY recipient). The point
    # the original Task-1 test made -- it is NOT the pre-fix sender gate -- still
    # holds (the error is not "invalid --from").
    rc = _post(comms, **{"from": "pipeline", "to": "rd",
                         "type": "decision_request", "subject": "x", "body": "y"})
    assert rc == 1
    err = capsys.readouterr().err
    assert "automated emitter" in err
    assert "invalid --from" not in err
    assert list(Path(comms).rglob("*.md")) == []


def test_l1_lock_unchanged_for_human_sender(comms, capsys):
    # The L1 sender-agnostic lock is UNCHANGED: a human/agent sender's
    # decision_request to a non-operator recipient still hits the L1 gate (the
    # allowlist is scoped to automated emitters and does not touch human senders).
    rc = _post(comms, **{"from": "orchestrator", "to": "rd",
                         "type": "decision_request", "subject": "x", "body": "y"})
    assert rc == 1
    err = capsys.readouterr().err
    assert "L1" in err
    assert list(Path(comms).rglob("*.md")) == []


def test_pipeline_to_invalid_recipient_rejects(comms, capsys):
    # Widening VALID_FROM did NOT widen VALID_TO: a `--to` outside the allowed
    # set still rejects at the recipient gate (post-fix the sender passes, so the
    # recipient-gate text distinguishes the behavior).
    rc = _post(comms, **{"from": "pipeline", "to": "santa", "type": "status",
                         "subject": "x", "body": "y"})
    assert rc == 1
    err = capsys.readouterr().err
    assert "invalid recipient" in err
    assert list(Path(comms).rglob("*.md")) == []


def test_pipeline_decision_request_to_operator_rejected(comms, capsys):
    # codex-auto-review MAJOR: an automated emitter is transport-automation, NOT
    # authority. The L1 gate alone would ALLOW pipeline->operator decision_request
    # (operator is the allowed recipient). The automated-emitter type allowlist
    # rejects it: pipeline may post `status` only. Pre-fix (no allowlist) this
    # would SUCCEED (rc 0); post-fix it rejects (rc 1) before delivery.
    rc = _post(comms, **{"from": "pipeline", "to": "operator",
                         "type": "decision_request", "subject": "x", "body": "y"})
    assert rc == 1
    err = capsys.readouterr().err
    assert "automated emitter" in err
    assert list(Path(comms).rglob("*.md")) == []


def test_pipeline_non_status_type_to_rd_rejected(comms, capsys):
    # The allowlist also blocks pipeline posting fyi/query/return_report -- only
    # `status` is permitted for the automated emitter.
    rc = _post(comms, **{"from": "pipeline", "to": "rd", "type": "fyi",
                         "subject": "x", "body": "y"})
    assert rc == 1
    err = capsys.readouterr().err
    assert "automated emitter" in err
    assert list(Path(comms).rglob("*.md")) == []


def test_human_role_keeps_full_type_set(comms):
    # The allowlist is scoped to automated emitters ONLY: a human/agent role
    # (charc) keeps the full VALID_TYPES (e.g. it can still post fyi).
    rc = _post(comms, **{"from": "charc", "to": "rd", "type": "fyi",
                         "subject": "s", "body": "x"})
    assert rc == 0
    assert len(_inbox(comms, "rd")) == 1


# --- 21-D: orchestrator SINGULAR inbox + :<sid> REJECTION -------------------
# The per-generation model is RETIRED. Every role -- charc/rd/operator AND
# orchestrator -- has ONE fixed inbox. A stale `:<session_id>` address (or a
# stale `--session`) must FAIL LOUDLY with an actionable message, never be
# silently ignored and never silently misroute (D2: reject, do not ignore).

_FIXED = datetime(2026, 6, 25, 12, 0, 0, tzinfo=UTC)


def _per_gen_inbox(comms_root, sid):
    d = Path(comms_root) / "orchestrator" / sid / "inbox"
    return sorted(d.glob("*.md")) if d.is_dir() else []


# D1 -- a bare `--to orchestrator` routes to the SINGULAR inbox.
def test_bare_orchestrator_delivers_to_singular_inbox(comms):
    paths = role_mail.post_message(comms, "charc", ["orchestrator"], "fyi",
                                   "hi orch", "body")
    assert len(paths) == 1
    files = _inbox(comms, "orchestrator")
    assert len(files) == 1
    assert files[0] == paths[0]
    text = files[0].read_text(encoding="utf-8")
    assert "to: orchestrator" in text
    assert "to: orchestrator:" not in text  # no generation label survives
    # NO per-generation directory is created anywhere under orchestrator/
    base = Path(comms) / "orchestrator"
    assert sorted(p.name for p in base.iterdir() if p.is_dir()) == [
        "inbox", "read"]


def test_bare_orchestrator_cli_round_trip_singular(comms, capsys):
    rc = _post(comms, **{"from": "charc", "to": "orchestrator", "type": "status",
                         "subject": "s", "body": "BODYTEXT"})
    assert rc == 0
    assert len(_inbox(comms, "orchestrator")) == 1
    capsys.readouterr()
    rc = role_mail.main(["read", "--role", "orchestrator", "--all",
                         "--comms-root", str(comms)])
    assert rc == 0
    assert "BODYTEXT" in capsys.readouterr().out
    assert len(_inbox(comms, "orchestrator")) == 0
    assert len(_read_dir(comms, "orchestrator")) == 1


# D2 -- a `:<sid>`-suffixed address RAISES with an ACTIONABLE message.
def test_sid_suffixed_recipient_raises_actionable_message(comms):
    with pytest.raises(role_mail.MailError) as ei:
        role_mail.post_message(comms, "charc", ["orchestrator:g1"], "fyi",
                               "s", "x")
    msg = str(ei.value)
    # the actionable content, not merely "it failed"
    assert "per-generation addressing was removed" in msg
    assert "orchestrator:g1" in msg
    assert "Every role is a singular inbox" in msg
    assert "bare name" in msg
    # nothing written anywhere, and no per-gen tree bootstrapped
    assert list(Path(comms).rglob("*.md")) == []
    assert _per_gen_inbox(comms, "g1") == []


def test_sid_suffixed_recipient_cli_rc1_and_actionable_stderr(comms, capsys):
    rc = _post(comms, **{"from": "charc", "to": "orchestrator:g1",
                         "type": "fyi", "subject": "s", "body": "x"})
    assert rc == 1  # NOT a silent rc-0 delivery
    err = capsys.readouterr().err
    assert "per-generation addressing was removed" in err
    assert "Every role is a singular inbox" in err
    assert list(Path(comms).rglob("*.md")) == []


def test_sid_suffix_on_a_singular_role_also_rejected(comms):
    for bad in ("charc:foo", "rd:bar", "operator:baz", "orchestrator:",
                "orchestrator:../evil", "orchestrator:a/b"):
        with pytest.raises(role_mail.MailError) as ei:
            role_mail.post_message(comms, "charc", [bad], "fyi", "s", "x")
        assert "per-generation addressing was removed" in str(ei.value)
    assert list(Path(comms).rglob("*.md")) == []


# D2 (read side) -- the stale `--session` flag fails loudly too.
def test_session_flag_rejected_with_actionable_message(comms, capsys):
    role_mail.post_message(comms, "charc", ["orchestrator"], "fyi", "m", "B")
    for cmd, extra in (("read", ["--all"]), ("list", []), ("peek", [])):
        capsys.readouterr()
        rc = role_mail.main([cmd, "--role", "orchestrator", "--session", "g1",
                             "--comms-root", str(comms), *extra])
        assert rc == 1, cmd
        err = capsys.readouterr().err
        assert "per-generation addressing was removed" in err, cmd
        assert "--session" in err, cmd
    # the refusal never acked / moved the message
    assert len(_inbox(comms, "orchestrator")) == 1
    assert len(_read_dir(comms, "orchestrator")) == 0


def test_session_help_text_states_it_is_retired():
    parser = role_mail.build_parser()
    sub = [a for a in parser._actions
           if isinstance(a, argparse._SubParsersAction)][0]
    for name in ("read", "list", "peek"):
        action = [a for a in sub.choices[name]._actions
                  if "--session" in getattr(a, "option_strings", [])][0]
        assert "retired" in action.help
        assert "newest-live" not in action.help


# read / list / peek round-trip on the singular orchestrator inbox
def test_orchestrator_read_list_peek_round_trip(comms, capsys):
    role_mail.post_message(comms, "charc", ["orchestrator"], "fyi", "m", "B")
    capsys.readouterr()
    rc = role_mail.main(["peek", "--role", "orchestrator",
                         "--comms-root", str(comms)])
    assert rc == 0
    assert "B" in capsys.readouterr().out
    assert len(_inbox(comms, "orchestrator")) == 1  # peek never acks
    capsys.readouterr()
    rc = role_mail.main(["list", "--role", "orchestrator",
                         "--comms-root", str(comms)])
    assert rc == 0
    assert "1 unread" in capsys.readouterr().out
    assert len(_inbox(comms, "orchestrator")) == 1
    capsys.readouterr()
    rc = role_mail.main(["read", "--role", "orchestrator", "--all",
                         "--comms-root", str(comms)])
    assert rc == 0
    assert len(_inbox(comms, "orchestrator")) == 0
    assert len(_read_dir(comms, "orchestrator")) == 1


def test_orchestrator_empty_inbox_is_not_an_error(comms, capsys):
    capsys.readouterr()
    for argv in (["read", "--role", "orchestrator", "--all"],
                 ["list", "--role", "orchestrator"],
                 ["peek", "--role", "orchestrator"]):
        rc = role_mail.main([*argv, "--comms-root", str(comms)])
        assert rc == 0
    out = capsys.readouterr().out
    assert "empty" in out


# type x recipient matrix, unchanged semantics on the singular address
def test_decision_request_to_orchestrator_refused_L1(comms, capsys):
    rc = _post(comms, **{"from": "charc", "to": "orchestrator",
                         "type": "decision_request", "subject": "x", "body": "y"})
    assert rc == 1
    err = capsys.readouterr().err
    assert "L1" in err
    assert list(Path(comms).rglob("*.md")) == []


def test_fyi_status_query_return_report_to_orchestrator_delivered(comms):
    for mtype in ("fyi", "status", "query", "return_report"):
        role_mail.post_message(comms, "charc", ["orchestrator"], mtype, "s", "x")
    assert len(_inbox(comms, "orchestrator")) == 4


def test_pipeline_decision_request_to_orchestrator_rejected(comms, capsys):
    rc = _post(comms, **{"from": "pipeline", "to": "orchestrator",
                         "type": "decision_request", "subject": "x", "body": "y"})
    assert rc == 1
    assert "automated emitter" in capsys.readouterr().err
    assert list(Path(comms).rglob("*.md")) == []


def test_multi_recipient_including_orchestrator_all_singular(comms):
    paths = role_mail.post_message(
        comms, "charc", ["rd", "orchestrator", "operator"], "status", "s", "x")
    assert len(paths) == 3
    assert len(_inbox(comms, "rd")) == 1
    assert len(_inbox(comms, "orchestrator")) == 1
    assert len(_inbox(comms, "operator")) == 1


def test_repeated_orchestrator_recipient_dedupes_to_one_delivery(comms):
    paths = role_mail.post_message(
        comms, "charc", ["orchestrator", "orchestrator"], "fyi", "s", "x")
    assert len(paths) == 1
    assert len(_inbox(comms, "orchestrator")) == 1


# D1 -- _ensure_tree now bootstraps the orchestrator singular tree like the rest
def test_ensure_tree_includes_orchestrator_singular(comms):
    role_mail._ensure_tree(comms)
    for role in ("charc", "rd", "operator", "orchestrator"):
        assert (Path(comms) / role / "inbox").is_dir()
        assert (Path(comms) / role / "read").is_dir()


def test_singular_inbox_roles_covers_every_valid_recipient():
    assert set(role_mail.SINGULAR_INBOX_ROLES) == set(role_mail.VALID_TO)


# D4 -- role_mail no longer depends on the session registry for addressing.
def test_role_mail_carries_no_registry_or_per_generation_addressing():
    text = _MODULE_PATH.read_text(encoding="utf-8")
    # the prose docstring may POINT at the registry (it is where session_id
    # survives as a recovery key); what must be gone is the CODE dependency.
    for dead in ("import comms_session_registry", "newest_live",
                 "per_generation_inbox", "per_generation_read",
                 "NoLiveOrchestratorError", "_effective_read_session",
                 "_registry("):
        assert dead not in text, dead


def test_ack_message_three_arg_still_works(comms):
    role_mail.post_message(comms, "charc", ["operator"], "fyi", "ack me", "body")
    fname = _inbox(comms, "operator")[0].name
    dest = role_mail.ack_message(comms, "operator", fname)  # 3-arg, no session
    assert dest.is_file()
    assert len(_inbox(comms, "operator")) == 0


# D2 on the LIBRARY entry point (Codex R1 CRITICAL): ack_message must REJECT a
# retired session_id, not accept-and-ignore it. An ignored selector lets a stale
# in-process caller believe it acked a specific generation while it actually
# acked the singular inbox -- the exact silent misroute D2 exists to prevent.
def test_ack_message_rejects_a_retired_session_id(comms):
    role_mail.post_message(comms, "charc", ["orchestrator"], "fyi", "s", "b")
    fname = _inbox(comms, "orchestrator")[0].name
    with pytest.raises(role_mail.MailError) as ei:
        role_mail.ack_message(comms, "orchestrator", fname, session_id="g1")
    msg = str(ei.value)
    assert "per-generation addressing was removed" in msg
    assert "g1" in msg
    # NOTHING was moved -- the message is still unread
    assert len(_inbox(comms, "orchestrator")) == 1
    assert len(_read_dir(comms, "orchestrator")) == 0


def test_no_helper_accepts_an_ignored_session_selector():
    """NO surviving address/read/ack helper may carry an ignored session param.

    An accept-and-ignore signature is a latent reject-not-ignore violation even
    when today's public callers all reject upstream (Codex R3 Minor 1): the
    next caller inherits silence instead of an error.
    """
    import inspect

    for fn in (role_mail._role_inbox_dir, role_mail._role_read_dir,
               role_mail._list_inbox, role_mail._list_read,
               role_mail._inbox_for_target, role_mail._recipient_label):
        params = list(inspect.signature(fn).parameters)
        assert not any(p in ("sid", "session_id") for p in params), fn.__name__


def test_ack_message_orchestrator_moves_inbox_to_read(comms):
    role_mail.post_message(comms, "charc", ["orchestrator"], "fyi", "s", "b")
    fname = _inbox(comms, "orchestrator")[0].name
    dest = role_mail.ack_message(comms, "orchestrator", fname)
    assert dest == Path(comms) / "orchestrator" / "read" / fname
    assert dest.is_file()
