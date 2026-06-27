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


# NOTE: the OLD test_orchestrator_cannot_receive is REPLACED by the G6 Arc A
# orchestrator-addressing tests below (orchestrator IS a valid --to now -- bare
# = newest-live, :<sid> = explicit). The new tests assert the new contract.


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


# --- G6 Arc A: orchestrator per-generation addressing ----------------------

_FIXED = datetime(2026, 6, 25, 12, 0, 0, tzinfo=UTC)


def _per_gen_inbox(comms_root, sid):
    d = Path(comms_root) / "orchestrator" / sid / "inbox"
    return sorted(d.glob("*.md")) if d.is_dir() else []


def _per_gen_read(comms_root, sid):
    d = Path(comms_root) / "orchestrator" / sid / "read"
    return sorted(d.glob("*.md")) if d.is_dir() else []


def _seed_live_orch(comms_root, sid, monkeypatch, *, last_seen=None):
    """Seed a live orchestrator registry entry + freeze role_mail._now."""
    reg = role_mail._registry()
    seen = last_seen or _FIXED
    reg.write_entry(Path(comms_root), sid, "orchestrator", "", _FIXED)
    # stamp last_seen explicitly so staleness is deterministic
    import json
    path = reg.entry_path(Path(comms_root), sid)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["last_seen"] = seen.isoformat()
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(role_mail, "_now", lambda: _FIXED)


# 4a -- bare --to orchestrator, live gen -> per-gen delivery
def test_bare_orchestrator_live_gen_delivers_to_per_gen(comms, monkeypatch):
    _seed_live_orch(comms, "g1", monkeypatch)
    paths = role_mail.post_message(comms, "charc", ["orchestrator"], "fyi",
                                   "hi gen", "body")
    assert len(paths) == 1
    assert len(_per_gen_inbox(comms, "g1")) == 1
    text = _per_gen_inbox(comms, "g1")[0].read_text(encoding="utf-8")
    assert "to: orchestrator:g1" in text
    # the singular orchestrator inbox must NOT exist (guard #2)
    assert not (Path(comms) / "orchestrator" / "inbox").exists()


# 4b -- bare --to orchestrator, NO live gen -> CLEAR ERROR (no silent drop)
def test_bare_orchestrator_no_live_gen_clear_error(comms, monkeypatch):
    monkeypatch.setattr(role_mail, "_now", lambda: _FIXED)
    with pytest.raises(role_mail.NoLiveOrchestratorError) as ei:
        role_mail.post_message(comms, "charc", ["orchestrator"], "fyi", "s", "x")
    msg = str(ei.value).lower()
    assert "orchestrator" in msg and "session_id" in msg
    assert list(Path(comms).rglob("*.md")) == []


def test_bare_orchestrator_no_live_gen_cli_rc1_no_file(comms, monkeypatch):
    monkeypatch.setattr(role_mail, "_now", lambda: _FIXED)
    rc = _post(comms, **{"from": "charc", "to": "orchestrator", "type": "fyi",
                         "subject": "s", "body": "x"})
    assert rc == 1  # NOT a silent rc-0 drop
    assert list(Path(comms).rglob("*.md")) == []


# 4c -- explicit :<sid> reaches a NEVER-registered + a PRUNED gen, full round-trip
def test_explicit_sid_never_registered_full_round_trip(comms, capsys):
    # EMPTY registry, no pre-existing comms/orchestrator/ dir.
    assert not (Path(comms) / "orchestrator").exists()
    paths = role_mail.post_message(comms, "charc", ["orchestrator:g2"], "fyi",
                                   "explicit", "body-g2")
    assert len(paths) == 1
    assert len(_per_gen_inbox(comms, "g2")) == 1  # send-path mkdir bootstrap
    # read drains it -> moves to read/ (ack-path mkdir bootstraps read/)
    capsys.readouterr()
    rc = role_mail.main(["read", "--role", "orchestrator", "--session", "g2",
                         "--all", "--comms-root", str(comms)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "body-g2" in out
    assert len(_per_gen_inbox(comms, "g2")) == 0
    assert len(_per_gen_read(comms, "g2")) == 1


def test_explicit_sid_pruned_gen_still_delivers(comms, monkeypatch):
    # register g3, then prune it -> registry-independent :<sid> still delivers
    reg = role_mail._registry()
    reg.write_entry(Path(comms), "g3", "orchestrator", "", _FIXED)
    reg.prune_stale(Path(comms), _FIXED + timedelta(seconds=reg.STALE_SECONDS + 1))
    assert reg.read_entry(Path(comms), "g3") is None  # pruned
    paths = role_mail.post_message(comms, "charc", ["orchestrator:g3"], "fyi",
                                   "still here", "x")
    assert len(paths) == 1
    assert len(_per_gen_inbox(comms, "g3")) == 1


# 4d -- session_id path-safety in :<sid>
def test_explicit_sid_path_safety(comms):
    for bad in ("orchestrator:../evil", "orchestrator:/abs", "orchestrator:",
                "orchestrator:a/b"):
        with pytest.raises(role_mail.MailError):
            role_mail.post_message(comms, "charc", [bad], "fyi", "s", "x")
    # a suffix on a singular role is rejected
    with pytest.raises(role_mail.MailError):
        role_mail.post_message(comms, "charc", ["charc:foo"], "fyi", "s", "x")
    # no .md escaped the per-gen tree
    assert list(Path(comms).rglob("*.md")) == []


# 4e -- type x recipient matrix
def test_decision_request_to_explicit_orchestrator_refused_L1(comms, capsys):
    rc = _post(comms, **{"from": "charc", "to": "orchestrator:g1",
                         "type": "decision_request", "subject": "x", "body": "y"})
    assert rc == 1
    err = capsys.readouterr().err
    assert "L1" in err
    assert "invalid recipient" not in err
    assert list(Path(comms).rglob("*.md")) == []


def test_decision_request_to_bare_orchestrator_refused_L1(comms, monkeypatch):
    # L1 fires on the PARSED role BEFORE newest-live resolution -- even with a
    # live gen, decision_request to orchestrator is refused at L1.
    _seed_live_orch(comms, "g1", monkeypatch)
    with pytest.raises(role_mail.MailError) as ei:
        role_mail.post_message(comms, "charc", ["orchestrator"],
                               "decision_request", "x", "y")
    assert "L1" in str(ei.value)
    assert list(Path(comms).rglob("*.md")) == []


def test_fyi_status_query_return_report_to_orchestrator_delivered(comms, monkeypatch):
    _seed_live_orch(comms, "g1", monkeypatch)
    for mtype in ("fyi", "status", "query", "return_report"):
        role_mail.post_message(comms, "charc", ["orchestrator:g1"], mtype,
                               "s", "x")
    assert len(_per_gen_inbox(comms, "g1")) == 4


def test_pipeline_decision_request_to_orchestrator_rejected(comms, capsys):
    rc = _post(comms, **{"from": "pipeline", "to": "orchestrator:g1",
                         "type": "decision_request", "subject": "x", "body": "y"})
    assert rc == 1
    err = capsys.readouterr().err
    assert "automated emitter" in err
    assert list(Path(comms).rglob("*.md")) == []


# 4f -- read/list/peek/ack with --session
def test_orchestrator_read_list_peek_session_round_trip(comms, capsys):
    role_mail.post_message(comms, "charc", ["orchestrator:g1"], "fyi", "m", "B")
    # peek does NOT ack
    capsys.readouterr()
    rc = role_mail.main(["peek", "--role", "orchestrator", "--session", "g1",
                         "--comms-root", str(comms)])
    assert rc == 0
    assert "B" in capsys.readouterr().out
    assert len(_per_gen_inbox(comms, "g1")) == 1
    # list counts it
    rc = role_mail.main(["list", "--role", "orchestrator", "--session", "g1",
                         "--comms-root", str(comms)])
    assert rc == 0
    # read drains it (proves cmd_read threaded --session into ack_message)
    capsys.readouterr()
    rc = role_mail.main(["read", "--role", "orchestrator", "--session", "g1",
                         "--all", "--comms-root", str(comms)])
    assert rc == 0
    assert len(_per_gen_inbox(comms, "g1")) == 0
    assert len(_per_gen_read(comms, "g1")) == 1


# T1b -- read no-session with NO live gen -> the CLEAR read-side error (the FLIP
# of the old Arc-A test_orchestrator_read_without_session_errors, which codified
# the now-reversed "requires --session" contract). The OLD message is gone.
def test_orchestrator_read_no_session_no_live_gen_clear_error(comms, monkeypatch,
                                                              capsys):
    monkeypatch.setattr(role_mail, "_now", lambda: _FIXED)  # empty registry
    rc = role_mail.main(["read", "--role", "orchestrator", "--all",
                         "--comms-root", str(comms)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "no live orchestrator" in err.lower()
    assert "requires --session" not in err
    assert list(Path(comms).rglob("*.md")) == []


# 4g -- single-sourced reader: behavioral delegation + structural backstop
def test_role_mail_delegates_resolution_to_registry(comms, monkeypatch):
    sentinel_inbox = Path(comms) / "STUBBED" / "inbox"

    class _Stub:
        STALE_SECONDS = 2700

        @staticmethod
        def is_valid_session_id(sid):
            return True

        @staticmethod
        def newest_live(root, now, stale_seconds=2700):
            return {"session_id": "STUB"}

        @staticmethod
        def per_generation_inbox(root, sid):
            return sentinel_inbox

    monkeypatch.setattr(role_mail, "_registry", lambda: _Stub())
    monkeypatch.setattr(role_mail, "_now", lambda: _FIXED)
    role_mail.post_message(comms, "charc", ["orchestrator"], "fyi", "s", "x")
    # delivered through the STUB's per_generation_inbox -> proves delegation
    assert sorted(sentinel_inbox.glob("*.md"))


def test_role_mail_has_no_private_resolver_copy():
    src = role_mail.__file__ if hasattr(role_mail, "__file__") else None
    text = (Path(role_mail.__file__).read_text(encoding="utf-8") if src
            else _MODULE_PATH.read_text(encoding="utf-8"))
    assert "def newest_live" not in text
    assert "STALE_SECONDS =" not in text
    reg_text = (Path(role_mail._registry().__file__).read_text(encoding="utf-8"))
    assert "def newest_live" in reg_text
    assert "STALE_SECONDS =" in reg_text


# 4h -- backward-compat: _ensure_tree does NOT create comms/orchestrator/inbox
def test_ensure_tree_excludes_orchestrator_singular(comms):
    role_mail._ensure_tree(comms)
    assert (Path(comms) / "charc" / "inbox").is_dir()
    assert (Path(comms) / "rd" / "inbox").is_dir()
    assert (Path(comms) / "operator" / "inbox").is_dir()
    assert not (Path(comms) / "orchestrator" / "inbox").exists()


def test_ack_message_three_arg_still_works(comms):
    role_mail.post_message(comms, "charc", ["operator"], "fyi", "ack me", "body")
    fname = _inbox(comms, "operator")[0].name
    dest = role_mail.ack_message(comms, "operator", fname)  # 3-arg, no session
    assert dest.is_file()
    assert len(_inbox(comms, "operator")) == 0


# --- G6 B.1: orchestrator newest-live self-read (read/list/peek no-session) -

def _set_started_ts(comms_root, sid, started):
    """Rewrite a seeded gen's started_ts so multi-gen newest is deterministic."""
    import json
    reg = role_mail._registry()
    path = reg.entry_path(Path(comms_root), sid)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["started_ts"] = started.isoformat()
    path.write_text(json.dumps(data), encoding="utf-8")


# T1a -- read no-session resolves newest-live AND acks THAT gen (read+ack
# consistency: the .md moves from the resolved gen's inbox/ -> read/).
def test_orchestrator_read_no_session_resolves_newest_live_and_acks_that_gen(
        comms, monkeypatch, capsys):
    _seed_live_orch(comms, "g1", monkeypatch)
    role_mail.post_message(comms, "charc", ["orchestrator:g1"], "fyi", "m", "BODY")
    capsys.readouterr()
    rc = role_mail.main(["read", "--role", "orchestrator", "--all",
                         "--comms-root", str(comms)])
    assert rc == 0
    assert "BODY" in capsys.readouterr().out
    assert len(_per_gen_inbox(comms, "g1")) == 0
    assert len(_per_gen_read(comms, "g1")) == 1


# T1c (GUARD) -- explicit --session targets a SPECIFIC, non-newest gen;
# newest-live must NOT override an explicit --session. Passes pre- and post-fix.
def test_orchestrator_read_explicit_session_targets_specific_non_newest_gen(
        comms, monkeypatch, capsys):
    _seed_live_orch(comms, "g1", monkeypatch)
    _seed_live_orch(comms, "g2", monkeypatch)
    _set_started_ts(comms, "g1", _FIXED - timedelta(hours=1))  # older
    _set_started_ts(comms, "g2", _FIXED)                        # newest-live
    role_mail.post_message(comms, "charc", ["orchestrator:g1"], "fyi", "m", "g1msg")
    role_mail.post_message(comms, "charc", ["orchestrator:g2"], "fyi", "m", "g2msg")
    capsys.readouterr()
    rc = role_mail.main(["read", "--role", "orchestrator", "--session", "g1",
                         "--all", "--comms-root", str(comms)])
    assert rc == 0
    assert len(_per_gen_inbox(comms, "g1")) == 0
    assert len(_per_gen_read(comms, "g1")) == 1
    assert len(_per_gen_inbox(comms, "g2")) == 1   # newer gen UNTOUCHED


# T1d -- list no-session resolves newest-live, NO ack (observational).
def test_orchestrator_list_no_session_resolves_newest_live_no_ack(
        comms, monkeypatch, capsys):
    _seed_live_orch(comms, "g1", monkeypatch)
    role_mail.post_message(comms, "charc", ["orchestrator:g1"], "fyi", "m", "x")
    capsys.readouterr()
    rc = role_mail.main(["list", "--role", "orchestrator",
                         "--comms-root", str(comms)])
    assert rc == 0
    assert "1 unread" in capsys.readouterr().out
    assert len(_per_gen_inbox(comms, "g1")) == 1   # not acked


# T1e -- peek no-session resolves newest-live, NO ack (peek never acks).
def test_orchestrator_peek_no_session_resolves_newest_live_no_ack(
        comms, monkeypatch, capsys):
    _seed_live_orch(comms, "g1", monkeypatch)
    role_mail.post_message(comms, "charc", ["orchestrator:g1"], "fyi", "m", "PEEKBODY")
    capsys.readouterr()
    rc = role_mail.main(["peek", "--role", "orchestrator",
                         "--comms-root", str(comms)])
    assert rc == 0
    assert "PEEKBODY" in capsys.readouterr().out
    assert len(_per_gen_inbox(comms, "g1")) == 1   # peek never acks


# T1f -- read no-session, MULTIPLE live gens -> drains the NEWEST only
# (the documented edge + read+ack consistency on the resolved gen).
def test_orchestrator_read_no_session_multi_gen_drains_newest_only(
        comms, monkeypatch, capsys):
    _seed_live_orch(comms, "g1", monkeypatch)
    _seed_live_orch(comms, "g2", monkeypatch)
    _set_started_ts(comms, "g1", _FIXED - timedelta(hours=1))  # older
    _set_started_ts(comms, "g2", _FIXED)                        # newest-live
    role_mail.post_message(comms, "charc", ["orchestrator:g1"], "fyi", "m", "g1msg")
    role_mail.post_message(comms, "charc", ["orchestrator:g2"], "fyi", "m", "g2msg")
    capsys.readouterr()
    rc = role_mail.main(["read", "--role", "orchestrator", "--all",
                         "--comms-root", str(comms)])
    assert rc == 0
    assert len(_per_gen_read(comms, "g2")) == 1    # newest drained + acked
    assert len(_per_gen_inbox(comms, "g2")) == 0
    assert len(_per_gen_inbox(comms, "g1")) == 1   # older UNTOUCHED


# T1g -- the --session help text is newest-live-aware, NOT "required".
def test_session_help_is_newest_live_aware_not_required():
    parser = role_mail.build_parser()
    sub = [a for a in parser._actions
           if isinstance(a, argparse._SubParsersAction)][0]
    read_parser = sub.choices["read"]
    session_action = [a for a in read_parser._actions
                      if "--session" in getattr(a, "option_strings", [])][0]
    help_text = session_action.help
    assert "required" not in help_text
    assert "newest-live" in help_text


# T2a -- the READ path delegates newest-live resolution to the registry (it
# does NOT hand-roll resolution off the filesystem). Read+ack route through the
# stub's per-generation dirs.
def test_role_mail_read_delegates_resolution_to_registry(comms, monkeypatch):
    sentinel_inbox = Path(comms) / "STUBBED" / "inbox"
    sentinel_read = Path(comms) / "STUBBED" / "read"
    sentinel_inbox.mkdir(parents=True, exist_ok=True)
    (sentinel_inbox / "20260625T120000Z-charc-m.md").write_text(
        "---\nfrom: charc\nto: orchestrator:STUB\ntype: fyi\n---\n\nbody\n",
        encoding="utf-8")

    class _Stub:
        STALE_SECONDS = 2700

        @staticmethod
        def is_valid_session_id(sid):
            return True

        @staticmethod
        def newest_live(root, now, stale_seconds=2700):
            return {"session_id": "STUB"}

        @staticmethod
        def per_generation_inbox(root, sid):
            return sentinel_inbox

        @staticmethod
        def per_generation_read(root, sid):
            return sentinel_read

    monkeypatch.setattr(role_mail, "_registry", lambda: _Stub())
    monkeypatch.setattr(role_mail, "_now", lambda: _FIXED)
    rc = role_mail.main(["read", "--role", "orchestrator", "--all",
                         "--comms-root", str(comms)])
    assert rc == 0
    # read + ack routed through the STUB's per-generation dirs -> delegation
    assert sorted(sentinel_inbox.glob("*.md")) == []
    assert len(sorted(sentinel_read.glob("*.md"))) == 1


# T2c -- cmd_read/list/peek resolve EXACTLY ONCE through the single
# _effective_read_session seam (the read+ack consistency guarantee depends on
# it). A spy returns the raw sid unchanged so behavior is preserved.
def test_read_commands_route_through_effective_read_session(comms, monkeypatch):
    calls = []

    def _spy(root, role, sid, now=None):
        calls.append((root, role, sid))
        return sid

    monkeypatch.setattr(role_mail, "_effective_read_session", _spy)
    for cmd in ("read", "list", "peek"):
        calls.clear()
        argv = [cmd, "--role", "charc", "--comms-root", str(comms)]
        if cmd == "read":
            argv.append("--all")
        rc = role_mail.main(argv)
        assert rc == 0
        assert len(calls) == 1
        assert calls[0] == (Path(comms), "charc", None)
