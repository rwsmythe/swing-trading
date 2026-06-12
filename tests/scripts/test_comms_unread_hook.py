"""Tests for scripts/comms_unread_hook.py -- the UserPromptSubmit unread hook.

The hook is stdlib-only and a no-op in any session without SWING_ROLE in
{charc, rd}. The bulk logic is a pure function exercised over a tmp_path comms
tree (never the real comms/); main()'s env + __file__ wiring is exercised by
monkeypatching the default root and by a real subprocess for the no-op path.
"""

from __future__ import annotations

import importlib.util
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
    rc = hook.main()
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_main_noop_for_non_director_role(monkeypatch, capsys):
    monkeypatch.setenv("SWING_ROLE", "orchestrator")
    rc = hook.main()
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_main_prints_for_director_with_unread(monkeypatch, capsys, comms):
    _make_msg(comms, "charc")
    monkeypatch.setenv("SWING_ROLE", "charc")
    monkeypatch.setattr(hook, "comms_root_default", lambda: comms)
    rc = hook.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "1 unread for charc" in out


def test_main_always_exit_0_on_internal_error(monkeypatch, capsys):
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
    env = {k: v for k, v in os.environ.items() if k != "SWING_ROLE"}
    proc = subprocess.run(
        [sys.executable, str(_HOOK_PATH)],
        capture_output=True, text=True, env=env, timeout=30)
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
