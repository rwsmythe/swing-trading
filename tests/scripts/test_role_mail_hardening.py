"""role_mail hardening: post-verified + the containment guard (T3).

Ported from the harness template's tests/harness/test_role_mail_hardening.py
(master 4335ff6; harness-template merge 2026-11-03, T3) into this instance's
pytest style and role set. Each property is proved in BOTH directions (a check
that passes both ways is worthless):

  (a) ``post-verified`` posts AND confirms the landing in one call -- a mailbox-
      root mismatch caught BEFORE the write, a landing that does not match what
      was asked for, and the ack-in-the-gap acceptance.
  (b) D1 -- the per-message discriminator: post-verified confirms THE specific
      message it wrote (posted stamp + msg-id nonce), so a header-twin sharing
      from/to/type/subject cannot answer for it.
  (c) D4 -- ``_within`` resolves symlinks/junctions before containment, and
      post / ack / list / read / peek REFUSE a target that escapes the mailbox
      root (nothing written, moved, or printed).

Junction tests SKIP (never silently pass) when a junction/symlink cannot be
created on the box. No test touches the real comms/ tree: every main() call
passes --comms-root or patches _REPO_ROOT to a tmp dir.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_spec = importlib.util.spec_from_file_location(
    "role_mail_hardening_under_test", _SCRIPTS / "role_mail.py")
rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rm)


def _tree(root: Path) -> set[str]:
    """Every path under root, relative + normalized (the wrote-nothing witness)."""
    if not root.exists():
        return set()
    return {p.relative_to(root).as_posix() for p in root.rglob("*")}


def _make_dir_link(link: Path, target: Path) -> bool:
    """Create link -> target as a dir junction/symlink; True on success.

    A Windows directory junction (mklink /J) needs no privilege, unlike a
    symlink; POSIX uses os.symlink. Returns False if neither can be made.
    """
    try:
        if sys.platform == "win32":
            proc = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True, text=True)
            return proc.returncode == 0 and link.exists()
        os.symlink(str(target), str(link), target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        return False


def _link_or_skip(link: Path, target: Path) -> None:
    if not _make_dir_link(link, target):
        pytest.skip("cannot create a junction/symlink on this box")


def _run(capsys, argv: list[str]) -> tuple[int, str, str]:
    rc = rm.main(argv)
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


@pytest.fixture
def root(tmp_path):
    d = tmp_path / "comms"
    d.mkdir()
    return d


@pytest.fixture
def outside(tmp_path):
    d = tmp_path / "outside"
    d.mkdir()
    return d


def _pv(root: Path, *extra: str, to: str = "operator", subject: str = "s",
        mtype: str = "status", sender: str = "charc") -> list[str]:
    return ["--comms-root", str(root), "post-verified", *extra,
            "--from", sender, "--to", to, "--type", mtype,
            "--subject", subject, "--body", "b"]


# --- (a) post-verified --------------------------------------------------------

def test_success_reports_the_absolute_landing_path(root, capsys):
    rc, out, _ = _run(capsys, _pv(root, subject="verified-hi"))
    assert rc == 0
    landed = list((root / "operator" / "inbox").glob("*.md"))
    assert len(landed) == 1
    assert f"verified -> {landed[0].absolute()}" in out


def test_prints_the_same_posted_and_ping_lines_as_post(root, capsys):
    # post-verified is a drop-in for post: the same posted -> / ping -> lines
    # (this instance's ping line reads comms/.sessions.json), then verified ->.
    (root / ".sessions.json").write_text(
        '{"orchestrator": {"session_name": "swing-orchestrator-x"}}',
        encoding="utf-8")
    rc, out, _ = _run(capsys, _pv(root, to="orchestrator"))
    assert rc == 0
    lines = out.splitlines()
    name = next((root / "orchestrator" / "inbox").glob("*.md")).name
    assert lines[0] == f"posted -> orchestrator/inbox/{name}"
    assert lines[1] == 'ping -> SendMessage to="swing-orchestrator-x"'
    assert lines[2].startswith("verified -> ")
    # and post itself prints exactly the first two
    rc, out2, _ = _run(capsys, ["--comms-root", str(root), "post", "--from",
                                "charc", "--to", "operator", "--type", "status",
                                "--subject", "p", "--body", "b"])
    assert rc == 0
    assert [ln.split(" ", 2)[0:2] for ln in out2.splitlines()] == [
        ["posted", "->"], ["ping", "->"]]


def test_success_on_the_singular_orchestrator(root, capsys):
    rc, _, _ = _run(capsys, _pv(root, to="orchestrator"))
    assert rc == 0
    assert len(list((root / "orchestrator" / "inbox").glob("*.md"))) == 1


def test_multi_recipient_all_verified(root, capsys):
    rc, out, _ = _run(capsys, _pv(root, to="operator,rd"))
    assert rc == 0
    assert out.count("verified ->") == 2


def test_acked_in_the_gap_still_verifies_landed(root, capsys, monkeypatch):
    # A receiver that acks the message (inbox -> read) between the post and the
    # verify has NOT lost it -- the read/ sibling is a legitimate landing.
    real_post = rm.post_message

    def post_then_ack(root_, sender, recipients, mtype, subject, body,
                      thread=None, posted_ids=None):
        finals = real_post(root_, sender, recipients, mtype, subject, body,
                           thread, posted_ids=posted_ids)
        for f in finals:  # receiver acks in the gap
            rm.ack_message(root_, "operator", f.name)
        return finals

    monkeypatch.setattr(rm, "post_message", post_then_ack)
    rc, _, err = _run(capsys, _pv(root, subject="acked-gap"))
    assert rc == 0, err
    assert len(list((root / "operator" / "read").glob("*.md"))) == 1
    assert list((root / "operator" / "inbox").glob("*.md")) == []


def test_expected_root_mismatch_fails_before_writing_anything(root, tmp_path,
                                                              capsys):
    other = tmp_path / "other"
    other.mkdir()
    rc, _, err = _run(capsys, _pv(root, "--expect-root", str(other)))
    assert rc == 1
    assert str(root.absolute()) in err
    assert str(other.absolute()) in err
    assert _tree(root) == set(), "nothing may be written"
    assert _tree(other) == set()


def test_expected_root_match_is_accepted(root, capsys):
    rc, _, _ = _run(capsys, _pv(root, "--expect-root", str(root)))
    assert rc == 0


def test_landing_that_vanished_is_reported_as_did_not_land(root, capsys,
                                                           monkeypatch):
    ghost = root / "operator" / "inbox" / "never-written.md"
    monkeypatch.setattr(rm, "post_message", lambda *a, **k: [ghost])
    rc, _, err = _run(capsys, _pv(root))
    assert rc == 1
    assert "did not land" in err
    assert "never-written.md" in err


def test_landing_in_the_wrong_inbox_is_reported_with_the_actual_path(
        root, capsys, monkeypatch):
    def wrong_place(root_, sender, recipients, mtype, subject, body,
                    thread=None, posted_ids=None):
        stray = Path(root_) / "charc" / "inbox" / "misrouted.md"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_text(
            "---\nfrom: charc\nto: operator\ntype: status\n"
            "subject: s\nposted: x\n---\n\nb\n", encoding="utf-8")
        return [stray]

    monkeypatch.setattr(rm, "post_message", wrong_place)
    rc, out, err = _run(capsys, _pv(root))
    assert rc == 1
    assert "misrouted.md" in err
    assert "WRONG inbox" in err
    assert "verified ->" not in out


def test_a_dropped_recipient_is_caught(root, capsys, monkeypatch):
    # Two addressed, one delivered: verification must not call that success.
    real_post = rm.post_message

    def only_one(root_, sender, recipients, mtype, subject, body,
                 thread=None, posted_ids=None):
        return real_post(root_, sender, ["operator"], mtype, subject, body,
                         thread)

    monkeypatch.setattr(rm, "post_message", only_one)
    rc, _, err = _run(capsys, _pv(root, to="operator,orchestrator"))
    assert rc == 1
    assert "nothing landed for requested recipient 'orchestrator'" in err


def test_the_governance_lock_still_applies(root, capsys):
    rc, _, err = _run(capsys, _pv(root, to="charc", mtype="decision_request"))
    assert rc == 1
    assert "L1" in err
    assert _tree(root) == set()


def test_the_pipeline_type_allowlist_still_applies(root, capsys):
    rc, _, err = _run(capsys, _pv(root, sender="pipeline", mtype="fyi"))
    assert rc == 1
    assert "automated emitter" in err
    assert _tree(root) == set()


def test_the_retired_session_suffix_is_still_refused(root, capsys):
    rc, _, err = _run(capsys, _pv(root, to="orchestrator:abc123"))
    assert rc == 1
    assert "per-generation addressing was removed" in err
    assert _tree(root) == set()


def test_post_and_post_verified_share_one_argument_set():
    # _add_post_arguments single-sources both: swapping the subcommand word
    # can never change how a message is addressed. post-verified adds ONLY
    # --expect-root.
    parser = rm.build_parser()
    sub = next(a for a in parser._actions if a.dest == "cmd")
    post = {a.dest for a in sub.choices["post"]._actions}
    verified = {a.dest for a in sub.choices["post-verified"]._actions}
    assert verified - post == {"expect_root"}
    assert post - verified == set()


# --- (b) D1 the per-message discriminator --------------------------------------

def _compose_file(dst: Path, msg_id: str, posted: str = "2024-06-01T12:00:00Z"):
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(
        f"---\nfrom: operator\nto: charc\ntype: fyi\nsubject: s\n"
        f"posted: {posted}\nmsg-id: {msg_id}\n---\n\nbody\n", encoding="utf-8")


def test_compose_embeds_a_msg_id(root):
    finals = rm.post_message(root, "operator", ["charc"], "fyi", "s", "body")
    fm = rm._read_frontmatter(finals[0])
    assert fm.get("msg-id"), "a posted message must carry a msg-id"


def test_msg_ids_are_distinct_per_delivery(root):
    finals = rm.post_message(root, "operator", ["charc", "rd"], "fyi", "s", "b")
    ids = {rm._read_frontmatter(f)["msg-id"] for f in finals}
    assert len(ids) == 2


def test_post_message_reports_write_side_discriminators(root):
    posted_ids: list = []
    finals = rm.post_message(root, "operator", ["charc"], "fyi", "s", "b",
                             posted_ids=posted_ids)
    assert len(posted_ids) == 1
    final, label, posted, msg_id = posted_ids[0]
    fm = rm._read_frontmatter(finals[0])
    assert (final, label, posted, msg_id) == (
        finals[0], "charc", fm["posted"], fm["msg-id"])


def test_verify_rejects_a_header_twin_at_the_read_sibling(root):
    # The final never landed in inbox; a header-twin (same from/to/type/
    # subject) with a DIFFERENT msg-id sits at the read/ sibling. The
    # accept-if-either-path would find it -- D1 rejects it (wrong nonce).
    final = root / "charc" / "inbox" / "20240601T120000Z-operator-s.md"
    twin = root / "charc" / "read" / final.name
    _compose_file(twin, msg_id="TWINNONCE")
    problem = rm._verify_landing(
        root, final, "operator", "fyi", "s",
        want_posted="2024-06-01T12:00:00Z", want_msg_id="OURNONCE")
    assert problem is not None and "msg-id" in problem
    # The OTHER direction: the SAME nonce (a genuine ack-in-gap) verifies.
    _compose_file(twin, msg_id="OURNONCE")
    assert rm._verify_landing(
        root, final, "operator", "fyi", "s",
        want_posted="2024-06-01T12:00:00Z", want_msg_id="OURNONCE") is None


def test_verify_rejects_a_posted_stamp_twin(root):
    final = root / "charc" / "inbox" / "m.md"
    _compose_file(final, msg_id="N", posted="2024-06-01T12:00:00Z")
    problem = rm._verify_landing(root, final, "operator", "fyi", "s",
                                 want_posted="2024-06-01T12:00:01Z",
                                 want_msg_id="N")
    assert problem is not None and "posted" in problem


def test_landing_matches_request_ties_to_this_posts_nonces():
    landed_twin = [("charc", "TWINNONCE")]
    assert not rm._landing_matches_request("charc", landed_twin, {"OURNONCE"})
    assert rm._landing_matches_request("charc", [("charc", "OURNONCE")],
                                       {"OURNONCE"})
    # Degrade: with no known posted-id set (a mocked post), fall back to
    # label-only -- never a regression from the pre-D1 behavior.
    assert rm._landing_matches_request("charc", landed_twin, set())


# --- (c) D4 the containment guard ------------------------------------------------

def test_in_tree_child_is_contained(root):
    child = root / "charc" / "inbox"
    child.mkdir(parents=True)
    assert rm._within(root, child)
    assert rm._within(root, root / "not" / "yet" / "created")


def test_a_lexical_escape_is_not_contained(root, outside):
    assert not rm._within(root, root / ".." / "outside")


def test_a_reparse_escape_is_not_contained(root, outside):
    link = root / "escape"
    _link_or_skip(link, outside)
    (outside / "inbox").mkdir()
    # The LEXICAL path reads as inside root, but it resolves OUTSIDE.
    assert not rm._within(root, link / "inbox"), (
        "_within must resolve the reparse point and reject it")


def test_escaping_target_is_refused_and_writes_nothing(root, monkeypatch):
    before = _tree(root)
    monkeypatch.setattr(rm, "_within", lambda parent, child: False)
    with pytest.raises(rm.MailError, match="OUTSIDE the mailbox root"):
        rm.post_message(root, "operator", ["charc"], "fyi", "s", "body")
    assert _tree(root) == before, "a refused delivery must write NOTHING"


def test_contained_target_delivers(root):
    finals = rm.post_message(root, "operator", ["charc"], "fyi", "s", "body")
    assert len(finals) == 1 and finals[0].is_file()


def test_post_through_a_junctioned_recipient_role_is_refused(root, outside):
    _link_or_skip(root / "charc", outside)
    with pytest.raises(rm.MailError, match="OUTSIDE the mailbox root"):
        rm.post_message(root, "operator", ["charc"], "fyi", "s", "body")
    assert _tree(outside) == set(), "the escape target must be untouched"


def test_multi_recipient_post_with_one_junctioned_role_writes_nothing(root,
                                                                      outside):
    _link_or_skip(root / "charc", outside)
    before = _tree(root)
    with pytest.raises(rm.MailError, match="OUTSIDE the mailbox root"):
        rm.post_message(root, "operator", ["rd", "charc"], "fyi", "s", "body")
    assert _tree(outside) == set()
    # the contained recipient (rd) got nothing either: the guard is pre-staging
    assert _tree(root) == before


def test_guarded_mkdir_refuses_an_escape_and_creates_inside(root, outside):
    with pytest.raises(rm.MailError, match="refusing to create"):
        rm._guarded_mkdir(root, root / ".." / "outside" / "x")
    assert not (outside / "x").exists()
    rm._guarded_mkdir(root, root / "a" / "b")
    assert (root / "a" / "b").is_dir()


def test_guarded_enum_dir_missing_is_fine_escape_is_refused(root, outside):
    missing = root / "charc" / "inbox"
    assert rm._guarded_enum_dir(root, missing) == missing
    with pytest.raises(rm.MailError, match="refusing to enumerate"):
        rm._guarded_enum_dir(root, root / ".." / "outside")


def _seed_external_msg(d: Path, body: str = "b", subject: str = "s") -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / "m.md").write_text(
        f"---\nfrom: operator\nto: charc\ntype: fyi\nsubject: {subject}\n"
        f"posted: x\nmsg-id: y\n---\n\n{body}\n", encoding="utf-8")


def test_ack_through_a_junctioned_role_is_blocked(root, outside):
    _link_or_skip(root / "charc", outside)
    _seed_external_msg(outside / "inbox")
    with pytest.raises(rm.MailError, match="OUTSIDE the mailbox root"):
        rm.ack_message(root, "charc", "m.md")
    assert not (outside / "read").exists(), "no escaped read/ dir created"
    assert (outside / "inbox" / "m.md").is_file(), "nothing moved"


def test_ack_from_a_junctioned_inbox_is_blocked(root, outside):
    # The SOURCE side: comms/charc/inbox ITSELF is a junction (charc/ and a
    # charc/read stay in-tree, so the DEST guard alone would pass).
    ext_inbox = outside / "ext_inbox"
    _seed_external_msg(ext_inbox)
    (root / "charc").mkdir()
    _link_or_skip(root / "charc" / "inbox", ext_inbox)
    with pytest.raises(rm.MailError, match="OUTSIDE the mailbox root"):
        rm.ack_message(root, "charc", "m.md")
    assert (ext_inbox / "m.md").is_file(), "the external source was not moved"
    assert not (root / "charc" / "read").exists()


def test_ack_into_a_junctioned_read_dir_is_blocked(root, outside):
    # The DEST side alone: inbox in-tree, read/ a junction out.
    finals = rm.post_message(root, "operator", ["charc"], "fyi", "s", "body")
    import shutil
    shutil.rmtree(root / "charc" / "read")
    _link_or_skip(root / "charc" / "read", outside)
    with pytest.raises(rm.MailError, match="OUTSIDE the mailbox root"):
        rm.ack_message(root, "charc", finals[0].name)
    assert finals[0].is_file(), "nothing moved"
    assert _tree(outside) == set()


def test_ack_in_a_normal_tree_still_works(root):
    finals = rm.post_message(root, "operator", ["charc"], "fyi", "s", "body")
    dest = rm.ack_message(root, "charc", finals[0].name)
    assert dest.is_file()
    assert dest.parent == root / "charc" / "read"


def _junction_inbox_with_secret(root: Path, outside: Path) -> Path:
    ext = outside / "ext"
    _seed_external_msg(ext, body="EXTERNAL-SECRET-BODY", subject="SECRET-SUBJ")
    (root / "charc").mkdir()
    _link_or_skip(root / "charc" / "inbox", ext)
    return ext


def test_read_all_cli_refuses_before_printing_external_content(root, outside,
                                                               capsys):
    ext = _junction_inbox_with_secret(root, outside)
    rc, out, err = _run(capsys, ["--comms-root", str(root), "read",
                                 "--role", "charc", "--all"])
    assert rc == 1
    assert "EXTERNAL-SECRET-BODY" not in out
    assert "SECRET-SUBJ" not in out
    assert "OUTSIDE the mailbox root" in err
    assert (ext / "m.md").is_file()
    assert not (root / "charc" / "read").exists()


@pytest.mark.parametrize("cmd", ["peek", "list"])
def test_peek_and_list_cli_also_refuse(root, outside, capsys, cmd):
    _junction_inbox_with_secret(root, outside)
    rc, out, err = _run(capsys, ["--comms-root", str(root), cmd,
                                 "--role", "charc"])
    assert rc == 1
    assert "EXTERNAL-SECRET-BODY" not in out
    assert "SECRET-SUBJ" not in out
    assert "OUTSIDE the mailbox root" in err


def test_list_refuses_a_junctioned_read_dir(root, outside, capsys):
    # list also counts read/: an escaping read/ is refused before enumeration
    (root / "charc" / "inbox").mkdir(parents=True)
    _link_or_skip(root / "charc" / "read", outside)
    rc, _, err = _run(capsys, ["--comms-root", str(root), "list",
                               "--role", "charc"])
    assert rc == 1
    assert "OUTSIDE the mailbox root" in err


def test_missing_inbox_reads_empty_normal(root, capsys):
    rc, out, _ = _run(capsys, ["--comms-root", str(root), "read",
                               "--role", "charc", "--all"])
    assert rc == 0
    assert "empty" in out


def test_normal_inbox_reads_fine(root, capsys):
    rm.post_message(root, "operator", ["charc"], "fyi", "hello", "NORMAL-BODY")
    rc, out, _ = _run(capsys, ["--comms-root", str(root), "read",
                               "--role", "charc", "--all"])
    assert rc == 0
    assert "NORMAL-BODY" in out


def test_post_never_creates_an_unaddressed_junctioned_role(root, outside):
    # A post must NEVER create an UNADDRESSED role's tree, so a junctioned
    # unaddressed role cannot be escaped through on a post that never names it
    # (the old _ensure_tree mkdir'd EVERY role's inbox/read on every post).
    _link_or_skip(root / "charc", outside)
    finals = rm.post_message(root, "operator", ["orchestrator"], "fyi", "s",
                             "body")
    assert len(finals) == 1
    assert len(list((root / "orchestrator" / "inbox").glob("*.md"))) == 1
    assert _tree(outside) == set(), (
        "an unaddressed junctioned role must not be created")


def test_post_creates_only_the_addressed_recipient_trees(root):
    rm.post_message(root, "operator", ["rd"], "fyi", "s", "body")
    assert sorted(p.name for p in root.iterdir()) == ["rd"]
    assert (root / "rd" / "inbox").is_dir() and (root / "rd" / "read").is_dir()


# --- the linked-checkout notice (advisory, never a failure) ----------------------

def _pointer(primary: Path, linked: Path) -> None:
    (primary / ".git" / "worktrees" / "wt").mkdir(parents=True)
    (linked / ".git").write_text(
        f"gitdir: {(primary / '.git' / 'worktrees' / 'wt').as_posix()}\n",
        encoding="utf-8")


@pytest.fixture
def linked_pair(tmp_path):
    primary = tmp_path / "primary"
    linked = tmp_path / "linked"
    primary.mkdir()
    linked.mkdir()
    _pointer(primary, linked)
    return primary, linked


def test_primary_checkout_behind_a_linked_copy_is_resolved(linked_pair):
    primary, linked = linked_pair
    assert rm._linked_checkout_primary(linked).resolve() == primary.resolve()


def test_a_normal_checkout_yields_no_notice(tmp_path):
    (tmp_path / ".git").mkdir()
    assert rm._linked_checkout_primary(tmp_path) is None
    assert rm._linked_checkout_primary(tmp_path / "no-git-here") is None


def test_notice_is_printed_only_when_the_root_was_defaulted(linked_pair,
                                                            capsys,
                                                            monkeypatch):
    primary, linked = linked_pair
    monkeypatch.setattr(rm, "_REPO_ROOT", linked)
    rc = rm.main(["post-verified", "--from", "charc", "--to", "operator",
                  "--type", "status", "--subject", "s", "--body", "b"])
    err = capsys.readouterr().err
    assert rc == 0, "the notice must never fail the post"
    assert "notice:" in err
    assert str((primary / "comms").absolute()) in err
    assert len(list((linked / "comms" / "operator" / "inbox").glob("*.md"))) == 1


def test_notice_accompanies_a_root_mismatch(linked_pair, capsys, monkeypatch):
    primary, linked = linked_pair
    monkeypatch.setattr(rm, "_REPO_ROOT", linked)
    rc = rm.main(["post-verified", "--expect-root", str(primary / "comms"),
                  "--from", "charc", "--to", "operator", "--type", "status",
                  "--subject", "s", "--body", "b"])
    text = capsys.readouterr().err
    assert rc == 1
    assert "notice:" in text
    assert "mailbox root mismatch" in text
    assert text.index("notice:") < text.index("error:")
    assert _tree(linked / "comms") == set()
    assert _tree(primary / "comms") == set()


def test_a_matching_expected_root_suppresses_the_notice(linked_pair, capsys,
                                                        monkeypatch):
    _primary, linked = linked_pair
    monkeypatch.setattr(rm, "_REPO_ROOT", linked)
    rc = rm.main(["post-verified", "--expect-root", str(linked / "comms"),
                  "--from", "charc", "--to", "operator", "--type", "status",
                  "--subject", "s", "--body", "b"])
    assert rc == 0
    assert "notice:" not in capsys.readouterr().err


def test_notice_is_skipped_when_the_root_is_explicit(linked_pair, root, capsys,
                                                     monkeypatch):
    primary, linked = linked_pair
    monkeypatch.setattr(rm, "_REPO_ROOT", linked)
    rc = rm.main(_pv(root))
    err = capsys.readouterr().err
    assert rc == 0
    assert "notice:" not in err
    assert str(primary.absolute()) not in err


def test_post_verified_output_is_ascii(root, capsys):
    rc, out, err = _run(capsys, _pv(root, subject="rocket \U0001F680"))
    assert rc == 0
    (out + err).encode("ascii")


# --- Reviewer A round 1 fixes ----------------------------------------------------

def _freeze_now(monkeypatch):
    from datetime import UTC, datetime
    fixed = datetime(2026, 11, 3, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(rm, "_now", lambda: fixed)


def _verified_path(out: str) -> Path:
    line = next(ln for ln in out.splitlines() if ln.startswith("verified -> "))
    return Path(line[len("verified -> "):])


def test_r1_f1_acked_twin_with_a_suffixed_archive_name_still_verifies(
        root, capsys, monkeypatch):
    # Same sender + subject twice in one second, each acked: the second reuses
    # the inbox basename (the first was moved out) and its ack archives it as
    # <stem>-2.md. The verify must find THAT file by its nonce, not reject the
    # earlier message sitting at the unsuffixed read/ name.
    _freeze_now(monkeypatch)
    first = rm.post_message(root, "charc", ["operator"], "status", "same", "b")
    rm.ack_message(root, "operator", first[0].name)
    real_post = rm.post_message

    def post_then_ack(root_, sender, recipients, mtype, subject, body,
                      thread=None, posted_ids=None):
        finals = real_post(root_, sender, recipients, mtype, subject, body,
                           thread, posted_ids=posted_ids)
        for f in finals:
            rm.ack_message(root_, "operator", f.name)
        return finals

    monkeypatch.setattr(rm, "post_message", post_then_ack)
    rc, out, err = _run(capsys, _pv(root, subject="same"))
    assert rc == 0, err
    landed = _verified_path(out)
    assert landed.name.endswith("-2.md") and landed.parent.name == "read"
    assert landed.is_file()


def test_r1_f7_verified_line_names_the_actual_landing_after_an_ack(
        root, capsys, monkeypatch):
    real_post = rm.post_message

    def post_then_ack(root_, sender, recipients, mtype, subject, body,
                      thread=None, posted_ids=None):
        finals = real_post(root_, sender, recipients, mtype, subject, body,
                           thread, posted_ids=posted_ids)
        for f in finals:
            rm.ack_message(root_, "operator", f.name)
        return finals

    monkeypatch.setattr(rm, "post_message", post_then_ack)
    rc, out, _ = _run(capsys, _pv(root))
    assert rc == 0
    landed = _verified_path(out)
    assert landed.parent.name == "read" and landed.is_file()
    # the posted -> line is unchanged (it names the addressed inbox)
    assert out.splitlines()[0].startswith("posted -> operator/inbox/")


def test_r1_f3_an_ack_between_exists_and_read_is_not_a_failure(
        root, capsys, monkeypatch):
    real_read = rm._read_frontmatter
    acked: list[str] = []

    def read_after_ack(path):
        path = Path(path)
        if path.parent.name == "inbox" and not acked:
            acked.append(path.name)
            rm.ack_message(root, path.parent.parent.name, path.name)
        return real_read(path)

    monkeypatch.setattr(rm, "_read_frontmatter", read_after_ack)
    rc, out, err = _run(capsys, _pv(root))
    assert acked, "the race was not exercised"
    assert rc == 0, err
    assert _verified_path(out).parent.name == "read"


def test_r1_f4_a_subject_with_surrounding_spaces_verifies(root, capsys):
    rc, _, err = _run(capsys, _pv(root, subject=" padded subject "))
    assert rc == 0, err


def test_r1_f5_same_dir_resolves_a_linked_parent_for_missing_children(
        tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    _link_or_skip(tmp_path / "alias", real)
    assert rm._same_dir(tmp_path / "alias" / "new-comms", real / "new-comms")
    assert not rm._same_dir(tmp_path / "alias" / "new-comms", real / "other")


def test_r1_f6_a_relative_gitdir_pointer_resolves_against_the_checkout(
        tmp_path, monkeypatch):
    primary = tmp_path / "main"
    linked = primary / ".worktrees" / "wt"
    (primary / ".git" / "worktrees" / "wt").mkdir(parents=True)
    linked.mkdir(parents=True)
    (linked / ".git").write_text("gitdir: ../../.git/worktrees/wt\n",
                                 encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    got = rm._linked_checkout_primary(linked)
    assert got is not None and got.resolve() == primary.resolve()


def test_r1_f2_enumeration_refuses_an_escaping_message_file(root, monkeypatch,
                                                            capsys):
    # Deterministic: a message FILE (not its dir) that resolves outside.
    rm.post_message(root, "operator", ["charc"], "fyi", "s", "SECRET-BODY")
    real_within = rm._within

    def file_escapes(parent, child):
        if Path(child).suffix == ".md":
            return False
        return real_within(parent, child)

    monkeypatch.setattr(rm, "_within", file_escapes)
    for cmd in ("read", "peek", "list"):
        argv = ["--comms-root", str(root), cmd, "--role", "charc"]
        rc, out, err = _run(capsys, argv + (["--all"] if cmd == "read" else []))
        assert rc == 1, cmd
        assert "SECRET-BODY" not in out, cmd
        assert "OUTSIDE the mailbox root" in err, cmd
    assert len(list((root / "charc" / "inbox").glob("*.md"))) == 1  # not acked


def test_r1_f2_a_real_file_symlink_in_a_contained_inbox_is_refused(
        root, outside, capsys):
    ext = outside / "message.md"
    ext.write_text("---\nfrom: operator\nto: charc\ntype: fyi\nsubject: s\n"
                   "posted: x\n---\n\nEXTERNAL-FILE-BODY\n", encoding="utf-8")
    inbox = root / "charc" / "inbox"
    inbox.mkdir(parents=True)
    try:
        os.symlink(str(ext), str(inbox / "external.md"))
    except (OSError, NotImplementedError):
        pytest.skip("cannot create a file symlink on this box")
    rc, out, err = _run(capsys, ["--comms-root", str(root), "peek",
                                 "--role", "charc"])
    assert rc == 1
    assert "EXTERNAL-FILE-BODY" not in out
    assert "OUTSIDE the mailbox root" in err
    with pytest.raises(rm.MailError, match="OUTSIDE the mailbox root"):
        rm.ack_message(root, "charc", "external.md")
    assert (inbox / "external.md").is_symlink()


# --- Reviewer A round 2 fixes ----------------------------------------------------

def test_r2_f1_an_ack_during_the_first_read_with_an_archived_twin_verifies(
        root, capsys, monkeypatch):
    # An older same-second, same-subject twin already sits at read/<name>.md.
    # Our message lands at inbox/<name>.md and is acked (to read/<name>-2.md)
    # AFTER the first pass globbed its candidates but BEFORE it read the inbox
    # file. Pass 1 then sees only the old twin; it must not be returned as the
    # answer before pass 2 re-globs and finds -2.md by its nonce.
    _freeze_now(monkeypatch)
    first = rm.post_message(root, "charc", ["operator"], "status", "same", "b")
    rm.ack_message(root, "operator", first[0].name)
    real_read = rm._read_frontmatter
    acked: list[str] = []

    def read_after_ack(path):
        path = Path(path)
        if path.parent.name == "inbox" and not acked:
            acked.append(path.name)
            rm.ack_message(root, path.parent.parent.name, path.name)
        return real_read(path)

    monkeypatch.setattr(rm, "_read_frontmatter", read_after_ack)
    rc, out, err = _run(capsys, _pv(root, subject="same"))
    assert acked, "the race was not exercised"
    assert rc == 0, err
    landed = _verified_path(out)
    assert landed.name.endswith("-2.md") and landed.parent.name == "read"
    assert landed.is_file()


def test_r2_f2_read_frontmatter_treats_invalid_utf8_as_unreadable(tmp_path):
    bad = tmp_path / "bad.md"
    bad.write_bytes(b"---\nfrom: \xff\xfe\x80\n---\n\nbody\n")
    assert rm._read_frontmatter(bad) == {}


def test_r2_f2_a_corrupt_unrelated_archive_does_not_abort_verification(
        root, capsys, monkeypatch):
    # An unrelated read/<name>.md holding invalid UTF-8 sits where our acked
    # message's search reads first; the verify must skip it and find ours at
    # read/<name>-2.md, not die with a UnicodeDecodeError traceback.
    _freeze_now(monkeypatch)
    first = rm.post_message(root, "charc", ["operator"], "status", "same", "b")
    archived = rm.ack_message(root, "operator", first[0].name)
    archived.write_bytes(b"---\nfrom: \xff\xfe\x80\n---\n\ncorrupt\n")
    real_post = rm.post_message

    def post_then_ack(root_, sender, recipients, mtype, subject, body,
                      thread=None, posted_ids=None):
        finals = real_post(root_, sender, recipients, mtype, subject, body,
                           thread, posted_ids=posted_ids)
        for f in finals:
            rm.ack_message(root_, "operator", f.name)
        return finals

    monkeypatch.setattr(rm, "post_message", post_then_ack)
    rc, out, err = _run(capsys, _pv(root, subject="same"))
    assert rc == 0, err
    landed = _verified_path(out)
    assert landed.name.endswith("-2.md") and landed.parent.name == "read"


# --- Reviewer A round 3 fixes ----------------------------------------------------

def _post_then_ack_patch(monkeypatch):
    real_post = rm.post_message

    def post_then_ack(root_, sender, recipients, mtype, subject, body,
                      thread=None, posted_ids=None):
        finals = real_post(root_, sender, recipients, mtype, subject, body,
                           thread, posted_ids=posted_ids)
        for f in finals:
            rm.ack_message(root_, "operator", f.name)
        return finals

    monkeypatch.setattr(rm, "post_message", post_then_ack)


def test_r3_f2_an_escaping_archive_candidate_is_never_read(root, capsys,
                                                           monkeypatch):
    # Deterministic: the archived twin at read/<name>.md resolves OUTSIDE the
    # root. The verify must not read it while searching for our message (which
    # was acked to read/<name>-2.md), and must still verify ours.
    _freeze_now(monkeypatch)
    first = rm.post_message(root, "charc", ["operator"], "status", "same", "b")
    twin = rm.ack_message(root, "operator", first[0].name)
    real_within = rm._within

    def twin_escapes(parent, child):
        if Path(child).name == twin.name and Path(child).parent.name == "read":
            return False
        return real_within(parent, child)

    real_read = rm._read_frontmatter
    reads: list[str] = []

    def spy_read(path):
        reads.append(Path(path).name)
        return real_read(path)

    monkeypatch.setattr(rm, "_within", twin_escapes)
    monkeypatch.setattr(rm, "_read_frontmatter", spy_read)
    _post_then_ack_patch(monkeypatch)
    rc, out, err = _run(capsys, _pv(root, subject="same"))
    assert rc == 0, err
    assert _verified_path(out).name.endswith("-2.md")
    assert twin.name not in reads


def test_r3_f2_an_escaping_candidate_alone_is_reported_outside(root, capsys,
                                                               monkeypatch):
    # The only landing escapes the root: reported as OUTSIDE, never read.
    real_within = rm._within
    real_read = rm._read_frontmatter
    reads: list[str] = []

    def inbox_md_escapes(parent, child):
        c = Path(child)
        if c.suffix == ".md" and c.parent.name == "inbox":
            return False
        return real_within(parent, child)

    def spy_read(path):
        reads.append(Path(path).parent.name)
        return real_read(path)

    real_post = rm.post_message

    def post_then_patch(*a, **k):
        finals = real_post(*a, **k)
        monkeypatch.setattr(rm, "_within", inbox_md_escapes)
        monkeypatch.setattr(rm, "_read_frontmatter", spy_read)
        return finals

    monkeypatch.setattr(rm, "post_message", post_then_patch)
    rc, _out, err = _run(capsys, _pv(root))
    assert rc == 1
    assert "landed OUTSIDE the mailbox root" in err
    assert "inbox" not in reads


def test_r3_f2_a_real_external_symlink_twin_is_never_read(root, outside, capsys,
                                                          monkeypatch):
    _freeze_now(monkeypatch)
    first = rm.post_message(root, "charc", ["operator"], "status", "same", "b")
    twin = rm.ack_message(root, "operator", first[0].name)
    ext = outside / "external.md"
    ext.write_bytes(twin.read_bytes())
    twin.unlink()
    try:
        os.symlink(str(ext), str(twin))
    except (OSError, NotImplementedError):
        pytest.skip("cannot create a file symlink on this box")
    real_read = rm._read_frontmatter
    reads: list[Path] = []

    def spy_read(path):
        reads.append(Path(path))
        return real_read(path)

    monkeypatch.setattr(rm, "_read_frontmatter", spy_read)
    _post_then_ack_patch(monkeypatch)
    rc, out, err = _run(capsys, _pv(root, subject="same"))
    assert rc == 0, err
    assert _verified_path(out).name.endswith("-2.md")
    assert twin not in reads


def test_r3_f3_an_empty_comms_root_counts_as_defaulted(linked_pair, capsys,
                                                       monkeypatch):
    # --comms-root "" (an empty variable) selects the default root, so it must
    # also get the linked-checkout notice the default gets.
    primary, linked = linked_pair
    monkeypatch.setattr(rm, "_REPO_ROOT", linked)
    rc = rm.main(["--comms-root", "", "post-verified", "--from", "charc",
                  "--to", "operator", "--type", "status", "--subject", "s",
                  "--body", "b"])
    err = capsys.readouterr().err
    assert rc == 0
    assert "notice:" in err
    assert str((primary / "comms").absolute()) in err
    assert len(list((linked / "comms" / "operator" / "inbox").glob("*.md"))) == 1
