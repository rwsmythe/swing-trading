"""Tests for scripts/comms_unread_hook.py -- the UserPromptSubmit unread hook.

The hook is stdlib-only. It prints the unread line for any comms role
(role_mail.VALID_TO) and, after it, the [ctx] context-depth gauge for any
session whose stdin payload names a transcript (harness-template merge
2026-11-03, T1). The bulk logic is pure functions exercised over a tmp_path
comms tree (never the real comms/); main()'s env + stdin + __file__ wiring is
exercised by monkeypatching the default root and by real subprocesses.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).resolve().parents[2] / "scripts"
_HOOK_PATH = _DIR / "comms_unread_hook.py"


def _load():
    spec = importlib.util.spec_from_file_location("comms_unread_hook", _HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["comms_unread_hook"] = mod
    spec.loader.exec_module(mod)
    return mod


hook = _load()


def _make_msg(comms: Path, role: str, mtype: str = "fyi", slug: str = "m") -> Path:
    inbox = comms / role / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    # a unique-ish stamp per call so names don't collide
    n = len(list(inbox.glob("*.md")))
    path = inbox / f"2026061{n}T120000Z-charc-{slug}.md"
    path.write_text(
        f"---\nfrom: charc\nto: {role}\ntype: {mtype}\nsubject: s\n---\n\nbody\n",
        encoding="utf-8")
    return path


@pytest.fixture
def comms(tmp_path):
    return tmp_path / "comms"


# --- pure notice logic -----------------------------------------------------

def test_notice_none_when_no_unread(comms):
    comms.mkdir(parents=True)
    assert hook.unread_notice("charc", comms) is None


def test_notice_none_when_missing_dir(tmp_path):
    assert hook.unread_notice("charc", tmp_path / "nope") is None


def test_notice_counts_unread(comms):
    _make_msg(comms, "charc")
    _make_msg(comms, "charc")
    line = hook.unread_notice("charc", comms)
    assert line is not None
    assert "2 unread for charc" in line
    # The recovery command must survive a foreign session cwd (the 2026-06-12
    # blocked-prompt incident): absolute quoted path, never a relative one.
    role_mail_abs = str(_DIR / "role_mail.py")
    assert f'python "{role_mail_abs}" read --role charc --all' in line
    assert "run: python scripts/" not in line


def test_notice_counts_decision_request(comms):
    _make_msg(comms, "charc", mtype="fyi")
    _make_msg(comms, "charc", mtype="decision_request")
    line = hook.unread_notice("charc", comms)
    assert "2 unread for charc" in line
    assert "1 decision_request" in line


def test_notice_no_dr_note_when_none(comms):
    _make_msg(comms, "charc", mtype="status")
    line = hook.unread_notice("charc", comms)
    assert "decision_request" not in line


def test_notice_is_ascii(comms):
    _make_msg(comms, "rd", mtype="decision_request")
    line = hook.unread_notice("rd", comms)
    line.encode("cp1252")  # must not raise


def test_notice_only_counts_own_role(comms):
    _make_msg(comms, "rd")
    _make_msg(comms, "rd")
    # charc has none even though rd has two
    assert hook.unread_notice("charc", comms) is None


# --- main() wiring ---------------------------------------------------------

def test_main_noop_without_swing_role(monkeypatch, capsys):
    monkeypatch.delenv("SWING_ROLE", raising=False)
    monkeypatch.delenv("HARNESS_ROLE", raising=False)
    rc = hook.main()
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_main_noop_for_unknown_role(monkeypatch, capsys, comms):
    # 'pipeline' is a SENDER only (role_mail.VALID_FROM), never a recipient,
    # so it has no inbox to notice -- and no payload means no [ctx] line.
    _make_msg(comms, "pipeline")
    monkeypatch.delenv("HARNESS_ROLE", raising=False)
    monkeypatch.setenv("SWING_ROLE", "pipeline")
    monkeypatch.setattr(hook, "comms_root_default", lambda: comms)
    rc = hook.main()
    assert rc == 0
    assert capsys.readouterr().out == ""


# --- T1: the unread line fires for EVERY comms role -------------------------

def test_comms_roles_single_sourced_from_role_mail_valid_to():
    spec = importlib.util.spec_from_file_location("_rm_probe", _DIR / "role_mail.py")
    rm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rm)
    assert tuple(hook.COMMS_ROLES) == tuple(rm.VALID_TO)
    assert "orchestrator" in hook.COMMS_ROLES
    # the stop hook's gate is NOT widened (it imports DIRECTOR_ROLES)
    assert hook.DIRECTOR_ROLES == ("charc", "rd")


def test_comms_roles_frozen_fallback_when_role_mail_unloadable(tmp_path):
    # A copy of the hook with NO role_mail.py beside it: the module must still
    # load (a hook must never block a prompt) and fall back to the frozen set.
    (tmp_path / "comms_unread_hook.py").write_bytes(_HOOK_PATH.read_bytes())
    spec = importlib.util.spec_from_file_location(
        "_hook_no_role_mail", tmp_path / "comms_unread_hook.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert tuple(mod.COMMS_ROLES) == ("charc", "rd", "operator", "orchestrator")


def test_main_prints_for_orchestrator_with_unread(monkeypatch, capsys, comms):
    _make_msg(comms, "orchestrator")
    monkeypatch.delenv("HARNESS_ROLE", raising=False)
    monkeypatch.setenv("SWING_ROLE", "orchestrator")
    monkeypatch.setattr(hook, "comms_root_default", lambda: comms)
    assert hook.main() == 0
    out = capsys.readouterr().out
    assert "[comms] 1 unread for orchestrator" in out
    assert "read --role orchestrator --all" in out


# --- T1: the [ctx] context-depth gauge (template ContextDepthNoticeTest) ----

def _usage_line(input_tokens: int, cache_creation: int = 0,
                cache_read: int = 0) -> str:
    """One transcript line whose message.usage sums to the given tokens."""
    return json.dumps({"message": {"usage": {
        "input_tokens": input_tokens,
        "cache_creation_input_tokens": cache_creation,
        "cache_read_input_tokens": cache_read,
    }}})


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_ctx_two_usage_lines_uses_the_last_ones_sum(tmp_path):
    # the first line sums to 100_000; the LAST sums to 250_000 across all
    # three fields -- the gauge must reflect the last, not the first.
    path = _write(tmp_path, "t.jsonl", "\n".join([
        _usage_line(100_000),
        _usage_line(200_000, cache_creation=30_000, cache_read=20_000),
    ]))
    assert hook.context_depth_notice(str(path), {}, "charc") == \
        "[ctx] 250K of 1000K (25%)"


def test_ctx_cap_line_appears_at_and_above_cap_not_below(tmp_path):
    below = _write(tmp_path, "below.jsonl", _usage_line(399_999))
    at = _write(tmp_path, "at.jsonl", _usage_line(400_000))
    above = _write(tmp_path, "above.jsonl", _usage_line(400_001))
    below_notice = hook.context_depth_notice(str(below), {}, "charc")
    at_notice = hook.context_depth_notice(str(at), {}, "charc")
    above_notice = hook.context_depth_notice(str(above), {}, "charc")
    assert "DEPTH CAP" not in below_notice
    assert "DEPTH CAP 400K REACHED" in at_notice
    assert "docs/charc-state.md" in at_notice
    assert "DEPTH CAP 400K REACHED" in above_notice


def test_ctx_cap_line_role_label_defaults_to_role_when_unknown(tmp_path):
    path = _write(tmp_path, "cap.jsonl", _usage_line(400_000))
    assert "docs/role-state.md" in hook.context_depth_notice(str(path), {}, None)
    assert "docs/role-state.md" in hook.context_depth_notice(str(path), {}, "")


def test_ctx_cap_line_names_the_orchestrator_handoff_doc(tmp_path):
    # this instance's orchestrator rolls into docs/orchestrator-handoff-<date>.md
    path = _write(tmp_path, "cap.jsonl", _usage_line(450_000))
    notice = hook.context_depth_notice(str(path), {}, "orchestrator")
    assert "docs/orchestrator-handoff-<date>.md" in notice
    assert "orchestrator-state.md" not in notice
    assert "docs/rd-state.md" in hook.context_depth_notice(str(path), {}, "rd")


def test_ctx_env_overrides_honored(tmp_path):
    path = _write(tmp_path, "t.jsonl", _usage_line(600))
    notice = hook.context_depth_notice(
        str(path), {"HARNESS_CTX_WINDOW": "1000", "HARNESS_CTX_CAP": "1000000"},
        "charc")
    assert notice == "[ctx] 1K of 1K (60%)"
    assert "DEPTH CAP" not in notice


def test_ctx_bad_env_values_ignored_defaults_kept(tmp_path):
    path = _write(tmp_path, "t.jsonl", _usage_line(250_000))
    notice = hook.context_depth_notice(
        str(path), {"HARNESS_CTX_WINDOW": "not-a-number",
                    "HARNESS_CTX_CAP": "also-bad"}, "charc")
    assert notice == "[ctx] 250K of 1000K (25%)"


def test_ctx_missing_file_returns_none(tmp_path):
    assert hook.context_depth_notice(
        str(tmp_path / "does-not-exist.jsonl"), {}, "charc") is None


def test_ctx_empty_file_returns_none(tmp_path):
    assert hook.context_depth_notice(
        str(_write(tmp_path, "empty.jsonl", "")), {}, "charc") is None


def test_ctx_malformed_only_line_returns_none(tmp_path):
    path = _write(tmp_path, "bad.jsonl", "not json at all {{{")
    assert hook.context_depth_notice(str(path), {}, "charc") is None


def test_ctx_no_transcript_path_returns_none():
    assert hook.context_depth_notice(None, {}, "charc") is None
    assert hook.context_depth_notice("", {}, "charc") is None


def test_ctx_non_string_transcript_path_returns_none():
    # a malformed payload (transcript_path: 123 / a list) must not raise
    assert hook.context_depth_notice(123, {}, "charc") is None
    assert hook.context_depth_notice(["x"], {}, "charc") is None


def test_ctx_big_file_still_finds_usage_past_600kb_of_filler(tmp_path):
    filler = ("x" * 200 + "\n") * 4000  # well over 600 KB of filler lines
    path = tmp_path / "big.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(filler)
        fh.write(_usage_line(300_000))
    assert path.stat().st_size > 600 * 1024
    assert hook.context_depth_notice(str(path), {}, "charc") == \
        "[ctx] 300K of 1000K (30%)"


def test_ctx_notice_is_ascii(tmp_path):
    path = _write(tmp_path, "cap.jsonl", _usage_line(450_000))
    hook.context_depth_notice(str(path), {}, "orchestrator").encode("ascii")


# --- T1: notice ORDER + the stdin payload ------------------------------------

def test_ctx_notice_prints_after_comms_notice(tmp_path, comms, capsys):
    _make_msg(comms, "charc")
    transcript = _write(tmp_path, "transcript.jsonl", _usage_line(250_000))
    hook.handle_user_prompt_submit(
        {"session_id": "sid-ctx", "transcript_path": str(transcript)},
        {"HARNESS_ROLE": "charc"}, comms)
    out = capsys.readouterr().out
    assert "[comms]" in out
    assert "[ctx] 250K of 1000K (25%)" in out
    assert out.index("[comms]") < out.index("[ctx]")


def test_no_ctx_line_when_transcript_path_absent(comms, capsys):
    _make_msg(comms, "charc")
    hook.handle_user_prompt_submit(
        {"session_id": "sid-noctx"}, {"HARNESS_ROLE": "charc"}, comms)
    out = capsys.readouterr().out
    assert "[comms]" in out
    assert "[ctx]" not in out


def test_ctx_line_fires_for_a_session_with_no_role(tmp_path, comms, capsys):
    # the template's step 4: the gauge is for ANY session with a transcript
    transcript = _write(tmp_path, "t.jsonl", _usage_line(120_000))
    hook.handle_user_prompt_submit(
        {"transcript_path": str(transcript)}, {}, comms)
    assert capsys.readouterr().out.strip() == "[ctx] 120K of 1000K (12%)"


def test_unread_failure_does_not_suppress_the_ctx_line(tmp_path, comms,
                                                        capsys, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(hook, "unread_notice", boom)
    transcript = _write(tmp_path, "t.jsonl", _usage_line(120_000))
    hook.handle_user_prompt_submit(
        {"transcript_path": str(transcript)}, {"SWING_ROLE": "charc"}, comms)
    assert "[ctx] 120K" in capsys.readouterr().out


class _FakeStdin:
    def __init__(self, data: bytes, tty: bool = False):
        self.buffer = io.BytesIO(data)
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def test_read_hook_payload_decodes_raw_bytes_utf8_sig(monkeypatch):
    data = b"\xef\xbb\xbf" + json.dumps({"transcript_path": "C:/t.jsonl"}).encode()
    monkeypatch.setattr(sys, "stdin", _FakeStdin(data))
    assert hook._read_hook_payload() == {"transcript_path": "C:/t.jsonl"}


@pytest.mark.parametrize("data", [b"", b"   \n", b"not json", b"[1, 2]", b"\xff\xfe"])
def test_read_hook_payload_degrades_to_empty(monkeypatch, data):
    monkeypatch.setattr(sys, "stdin", _FakeStdin(data))
    assert hook._read_hook_payload() == {}


def test_read_hook_payload_never_reads_a_tty(monkeypatch):
    fake = _FakeStdin(b'{"transcript_path": "x"}', tty=True)
    monkeypatch.setattr(sys, "stdin", fake)
    assert hook._read_hook_payload() == {}
    assert fake.buffer.tell() == 0        # never read -> never blocks


def test_read_hook_payload_no_stdin(monkeypatch):
    monkeypatch.setattr(sys, "stdin", None)
    assert hook._read_hook_payload() == {}


def test_main_reads_transcript_path_from_stdin(tmp_path, monkeypatch, capsys,
                                               comms):
    _make_msg(comms, "rd")
    transcript = _write(tmp_path, "t.jsonl", _usage_line(410_000))
    payload = json.dumps({"transcript_path": str(transcript)}).encode()
    monkeypatch.setattr(sys, "stdin", _FakeStdin(payload))
    monkeypatch.delenv("HARNESS_ROLE", raising=False)
    monkeypatch.setenv("SWING_ROLE", "rd")
    monkeypatch.setattr(hook, "comms_root_default", lambda: comms)
    assert hook.main() == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("[comms] 1 unread for rd")
    assert lines[1].startswith("[ctx] 410K of 1000K (41%) -- DEPTH CAP 400K REACHED")
    assert "docs/rd-state.md" in lines[1]


def test_main_prints_for_director_with_unread(monkeypatch, capsys, comms):
    _make_msg(comms, "charc")
    monkeypatch.delenv("HARNESS_ROLE", raising=False)
    monkeypatch.setenv("SWING_ROLE", "charc")
    monkeypatch.setattr(hook, "comms_root_default", lambda: comms)
    rc = hook.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "1 unread for charc" in out


# --- T2 (harness-template merge 2026-11-03): the HARNESS_ROLE alias --------
# The template renamed the role env var SWING_ROLE -> HARNESS_ROLE. This
# instance keeps every SWING_ROLE pin and reads HARNESS_ROLE FIRST, SWING_ROLE
# second (the launcher sets both), so a session carrying either is recognised.

def test_main_reads_harness_role_alias(monkeypatch, capsys, comms):
    _make_msg(comms, "charc")
    monkeypatch.delenv("SWING_ROLE", raising=False)
    monkeypatch.setenv("HARNESS_ROLE", "charc")
    monkeypatch.setattr(hook, "comms_root_default", lambda: comms)
    assert hook.main() == 0
    assert "1 unread for charc" in capsys.readouterr().out


def test_main_harness_role_wins_over_swing_role(monkeypatch, capsys, comms):
    _make_msg(comms, "charc")
    _make_msg(comms, "rd")
    _make_msg(comms, "rd")
    monkeypatch.setenv("HARNESS_ROLE", "charc")
    monkeypatch.setenv("SWING_ROLE", "rd")
    monkeypatch.setattr(hook, "comms_root_default", lambda: comms)
    assert hook.main() == 0
    out = capsys.readouterr().out
    assert "1 unread for charc" in out
    assert "for rd" not in out


def test_role_from_env_empty_harness_role_falls_through_to_swing_role():
    # an EMPTY HARNESS_ROLE is "unset" (the `or` chain), not a role of ''
    assert hook.role_from_env({"HARNESS_ROLE": "", "SWING_ROLE": "rd"}) == "rd"
    assert hook.role_from_env({}) == ""


def test_main_always_exit_0_on_internal_error(monkeypatch, capsys):
    monkeypatch.delenv("HARNESS_ROLE", raising=False)
    monkeypatch.setenv("SWING_ROLE", "charc")

    def boom():
        raise RuntimeError("kaboom")

    monkeypatch.setattr(hook, "comms_root_default", boom)
    rc = hook.main()  # an internal exception must never block the prompt
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_subprocess_noop_exit_0_no_output():
    # the unseeded default: a session WITHOUT SWING_ROLE prints nothing and
    # exits 0 (the seeded-gate-masks-default lesson -- witness the quiet path).
    env = {k: v for k, v in os.environ.items()
           if k not in ("SWING_ROLE", "HARNESS_ROLE")}
    proc = subprocess.run(
        [sys.executable, str(_HOOK_PATH)], stdin=subprocess.DEVNULL,
        capture_output=True, text=True, env=env, timeout=30)
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_subprocess_ctx_line_from_a_real_bom_payload(tmp_path):
    # the real process path: raw stdin bytes WITH a BOM, no role -> the [ctx]
    # line alone, exit 0 (no role -> the real comms/ tree is never read).
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(_usage_line(90_000), encoding="utf-8")
    env = {k: v for k, v in os.environ.items()
           if k not in ("SWING_ROLE", "HARNESS_ROLE")}
    payload = b"\xef\xbb\xbf" + json.dumps(
        {"session_id": "s", "transcript_path": str(transcript)}).encode("utf-8")
    proc = subprocess.run(
        [sys.executable, str(_HOOK_PATH)], input=payload,
        capture_output=True, env=env, timeout=30)
    assert proc.returncode == 0
    assert proc.stdout.decode("ascii").strip() == "[ctx] 90K of 1000K (9%)"


# --- Reviewer A round 1 fixes ----------------------------------------------------

def test_r1_f9_comms_roles_really_come_from_the_sibling_role_mail(tmp_path):
    # Non-vacuous single-source pin: a staged sibling role_mail with a
    # DISTINGUISHABLE VALID_TO must be adopted (the frozen fallback cannot
    # pass this).
    (tmp_path / "comms_unread_hook.py").write_bytes(_HOOK_PATH.read_bytes())
    (tmp_path / "role_mail.py").write_text(
        'VALID_TO = ("alpha", "beta")\n', encoding="utf-8")
    spec = importlib.util.spec_from_file_location(
        "_hook_stub_role_mail", tmp_path / "comms_unread_hook.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert tuple(mod.COMMS_ROLES) == ("alpha", "beta")


def test_r1_f8_unknown_role_never_reaches_the_cap_line(tmp_path):
    # An unrecognised (here non-ASCII) role must not be interpolated into the
    # state-doc path: the line stays ASCII and names the generic doc.
    path = _write(tmp_path, "cap.jsonl", _usage_line(450_000))
    notice = hook.context_depth_notice(str(path), {}, "r\u00e9le")
    notice.encode("ascii")
    assert "docs/role-state.md" in notice
    notice = hook.context_depth_notice(str(path), {}, "not-a-role")
    assert "docs/role-state.md" in notice


# --- Reviewer A round 3 fixes ----------------------------------------------------

def test_r3_f1_a_held_open_stdin_never_blocks_the_hook():
    # The producer writes a complete payload but keeps the pipe's write end
    # open (no EOF). The hook must give up on stdin after its deadline and
    # exit 0 promptly -- a UserPromptSubmit hook must never block a prompt.
    env = {k: v for k, v in os.environ.items()
           if k not in ("SWING_ROLE", "HARNESS_ROLE")}
    proc = subprocess.Popen(
        [sys.executable, str(_HOOK_PATH)], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    try:
        proc.stdin.write(b"{}\n")
        proc.stdin.flush()
        try:
            rc = proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            pytest.fail("the hook blocked on a held-open stdin")
        assert rc == 0
        out = proc.stdout.read()
        err = proc.stderr.read()
        assert out.strip() == b"", out
        assert b"Fatal Python error" not in err, err
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        import contextlib
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            with contextlib.suppress(OSError):
                stream.close()


def test_r3_f1_a_slow_payload_reader_degrades_to_empty(monkeypatch):
    # In-process: a stdin whose read never returns within the deadline yields
    # {} and flags the read as abandoned (the __main__ path then hard-exits).
    import threading
    release = threading.Event()

    class _Stuck:
        def isatty(self):
            return False

        class buffer:  # noqa: N801 -- mimics sys.stdin.buffer
            @staticmethod
            def read():
                release.wait(10)
                return b"{}"

    monkeypatch.setattr(sys, "stdin", _Stuck())
    monkeypatch.setattr(hook, "_STDIN_DEADLINE_S", 0.2)
    monkeypatch.setattr(hook, "_stdin_abandoned", False)
    try:
        assert hook._read_hook_payload() == {}
        assert hook._stdin_abandoned is True
    finally:
        release.set()


def test_r3_f1_a_non_regular_transcript_is_never_opened(tmp_path, monkeypatch):
    # A FIFO (or any non-regular file) at transcript_path could block open();
    # the gauge must refuse it from its stat, before opening. A directory is
    # the portable non-regular stand-in.
    opened: list[str] = []
    real_open = open

    def spy_open(path, *a, **k):
        opened.append(str(path))
        return real_open(path, *a, **k)

    monkeypatch.setattr(hook, "open", spy_open, raising=False)
    d = tmp_path / "not-a-file"
    d.mkdir()
    assert hook._last_usage_dict(d) is None
    assert opened == []


# --- Reviewer A round 4 fixes ----------------------------------------------------

def test_r4_f1_a_non_regular_inbox_entry_is_never_opened(comms, monkeypatch):
    # A FIFO named *.md in an inbox would block a synchronous open/read. The
    # decision-request scan must refuse any non-regular entry from its stat,
    # before opening it. A directory is the portable non-regular stand-in.
    _make_msg(comms, "orchestrator", mtype="decision_request", slug="real")
    special = comms / "orchestrator" / "inbox" / "stuck.md"
    special.mkdir()
    opened: list[str] = []
    real_open = open
    real_read_text = Path.read_text

    def spy_open(path, *a, **k):
        opened.append(Path(path).name)
        return real_open(path, *a, **k)

    def spy_read_text(self, *a, **k):
        opened.append(self.name)
        return real_read_text(self, *a, **k)

    monkeypatch.setattr(hook, "open", spy_open, raising=False)
    monkeypatch.setattr(Path, "read_text", spy_read_text)
    notice = hook.unread_notice("orchestrator", comms)
    assert "stuck.md" not in opened
    assert notice is not None and "(1 decision_request)" in notice


def test_r4_f1_the_decision_request_read_is_bounded(comms, monkeypatch):
    # Only the leading block is read, never a whole (possibly huge) file.
    path = _make_msg(comms, "orchestrator", mtype="decision_request")
    with open(path, "ab") as fh:
        fh.write(b"x" * (2 * hook._DR_HEAD_BYTES))
    assert hook._is_decision_request(path) is True


@pytest.mark.parametrize("hold_stdin", [True, False])
def test_r4_f2_a_closed_stdout_still_exits_0(tmp_path, hold_stdin):
    # The hook has a notice buffered when its stdout reader goes away. The
    # final flush fails; the hook must still exit 0 (never the 120 of a failed
    # finalization flush), on both the abandoned-stdin and the normal path.
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "comms_unread_hook.py").write_bytes(_HOOK_PATH.read_bytes())
    (scripts / "role_mail.py").write_text(
        'VALID_TO = ("charc", "rd", "operator", "orchestrator")\n',
        encoding="utf-8")
    _make_msg(tmp_path / "comms", "charc")
    env = {k: v for k, v in os.environ.items()
           if k not in ("SWING_ROLE", "HARNESS_ROLE")}
    env["SWING_ROLE"] = "charc"
    proc = subprocess.Popen(
        [sys.executable, str(scripts / "comms_unread_hook.py")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=env)
    import contextlib
    try:
        proc.stdout.close()  # the consumer is gone before the hook writes
        proc.stdin.write(b"{}\n")
        proc.stdin.flush()
        if not hold_stdin:
            proc.stdin.close()
        try:
            rc = proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            pytest.fail("the hook blocked")
        err = proc.stderr.read()
        assert rc == 0, err
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        for stream in (proc.stdin, proc.stderr):
            with contextlib.suppress(OSError):
                stream.close()


def test_r4_f5_the_unread_notice_is_ascii_under_a_non_ascii_checkout(
        comms, monkeypatch):
    # The notice names the role_mail path; a checkout under a CJK directory
    # must not make the line unprintable on cp1252 (it would be dropped).
    cjk = chr(0x4E2D)
    monkeypatch.setattr(hook, "__file__",
                        str(comms.parent / cjk / "scripts" / "comms_unread_hook.py"))
    _make_msg(comms, "orchestrator")
    notice = hook.unread_notice("orchestrator", comms)
    assert notice is not None
    notice.encode("ascii")
    assert "\\u4e2d" in notice


# --- Reviewer A round 5 fixes ----------------------------------------------------

class _ReadSizeSpy:
    """Wraps an open binary file; records the size of every read() call."""

    def __init__(self, fh, sizes: list):
        self._fh = fh
        self._sizes = sizes

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._fh.close()

    def read(self, n=-1):
        self._sizes.append(n)
        return self._fh.read(n)

    def __getattr__(self, name):
        return getattr(self._fh, name)


def _spy_reads(monkeypatch) -> list:
    sizes: list = []
    real_open = open
    monkeypatch.setattr(hook, "open",
                        lambda path, *a, **k: _ReadSizeSpy(
                            real_open(path, *a, **k), sizes),
                        raising=False)
    return sizes


def test_r5_f2_the_transcript_read_is_explicitly_bounded(tmp_path, monkeypatch):
    # Every read the gauge makes asks for at most _CTX_TAIL_BYTES, so a file
    # that grows between the size check and the read cannot be read whole.
    path = tmp_path / "big.jsonl"
    path.write_bytes(b"x" * (hook._CTX_TAIL_BYTES + 4096) + b"\n"
                     + _usage_line(123_000).encode("utf-8"))
    sizes = _spy_reads(monkeypatch)
    usage = hook._last_usage_dict(path)
    assert usage is not None and usage["input_tokens"] == 123_000
    assert sizes and all(0 < n <= hook._CTX_TAIL_BYTES for n in sizes), sizes
