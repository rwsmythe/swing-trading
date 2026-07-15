"""Tests for scripts/comms_stop_hook.py -- the Stop hook decision matrix.

Rider R1 (Phase-19 close housekeeping H1): back-ports the harness-template
scaffold's Arc-C hardened Stop-hook decision logic (docs/reviews/
comms-gui-resync-arc-c-executing-codex-findings.md) so swing's copy shares the
same three fail-open guarantees:
  (a) a strict-decode failure (incl. invalid UTF-8) ALLOWS the stop;
  (b) a MISSING stop_hook_active key ALLOWS the stop;
  (c) the stop is blocked ONLY on an exact boolean `False` -- any other
      present-but-non-boolean falsey value (None/0/""/[]) ALLOWS the stop.

These tests drive the testable seam (handle_stop / _parse_stop_payload /
_stop_hook_active) over a tmp comms root so the real comms/ tree is never
touched.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

_DIR = Path(__file__).resolve().parents[2] / "scripts"
_HOOK_PATH = _DIR / "comms_stop_hook.py"


def _load():
    # Sibling import: comms_stop_hook imports comms_unread_hook by bare name,
    # so scripts/ must be on sys.path (matches the hook's own runtime shape).
    sys.path.insert(0, str(_DIR))
    spec = importlib.util.spec_from_file_location("comms_stop_hook", _HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["comms_stop_hook"] = mod
    spec.loader.exec_module(mod)
    return mod


hook = _load()


def _seed_inbox(comms: Path, role: str, subject: str = "ping") -> Path:
    inbox = comms / role / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    path = inbox / "20260601T120000Z-operator-ping.md"
    path.write_text(
        f"---\nfrom: operator\nto: {role}\ntype: fyi\nsubject: {subject}\n---\n\n"
        "body\n",
        encoding="utf-8")
    return path


@pytest.fixture
def comms(tmp_path):
    return tmp_path / "comms"


# --- handle_stop: role gating -----------------------------------------------

def test_non_director_role_is_silent_noop(comms):
    _seed_inbox(comms, "charc")
    assert hook.handle_stop(
        {"stop_hook_active": False}, {}, comms) is None
    assert hook.handle_stop(
        {"stop_hook_active": False},
        {"SWING_ROLE": "orchestrator"}, comms) is None


def test_charc_and_rd_are_both_gated(comms):
    for role in ("charc", "rd"):
        _seed_inbox(comms, role, subject=f"hello-{role}")
        reason = hook.handle_stop(
            {"stop_hook_active": False}, {"SWING_ROLE": role}, comms)
        assert isinstance(reason, str)
        assert reason


# --- handle_stop: the single-continuation loop guard ------------------------

def test_stop_hook_active_true_allows_stop(comms):
    _seed_inbox(comms, "charc")
    assert hook.handle_stop(
        {"stop_hook_active": True}, {"SWING_ROLE": "charc"}, comms) is None


def test_empty_inbox_allows_stop(comms):
    assert hook.handle_stop(
        {"stop_hook_active": False}, {"SWING_ROLE": "charc"}, comms) is None


# --- (b) missing key -> allow stop -------------------------------------------

def test_key_absent_allows_stop(comms):
    # A valid payload lacking stop_hook_active is ambiguous (first stop vs Nth
    # continuation indistinguishable) -> allow stop, never block, even with
    # unread mail. A naive absent->False impl would block here.
    _seed_inbox(comms, "charc")
    assert hook.handle_stop(
        {"session_id": "x"}, {"SWING_ROLE": "charc"}, comms) is None


# --- (c) block ONLY on exact boolean False ----------------------------------

def test_non_boolean_falsey_values_allow_stop(comms):
    _seed_inbox(comms, "charc")
    for value in (None, 0, "", []):
        assert hook.handle_stop(
            {"stop_hook_active": value}, {"SWING_ROLE": "charc"}, comms
        ) is None, f"a non-boolean falsey stop_hook_active {value!r} must allow stop"


def test_exact_false_blocks(comms):
    _seed_inbox(comms, "charc")
    reason = hook.handle_stop(
        {"stop_hook_active": False}, {"SWING_ROLE": "charc"}, comms)
    assert isinstance(reason, str) and reason


# --- (a) strict-decode fail-open --------------------------------------------

def test_malformed_stdin_allows_stop(comms):
    _seed_inbox(comms, "charc")
    payload = hook._parse_stop_payload(b"not json at all")
    assert payload.get("stop_hook_active") is True
    assert hook.handle_stop(payload, {"SWING_ROLE": "charc"}, comms) is None


def test_empty_and_unreadable_stdin_default_to_allow_stop():
    for raw in (b"", b"  \n", b"\xef\xbb\xbf"):
        payload = hook._parse_stop_payload(raw)
        assert payload.get("stop_hook_active") is True, (
            f"empty/unreadable stdin {raw!r} must allow stop")


def test_invalid_utf8_payload_allows_stop(comms):
    # A byte-corrupted payload that would otherwise (under errors="replace")
    # decode to a stale `false` must NOT be salvaged into a block: the strict
    # decode raises -> the allow-stop sentinel.
    raw = b'{"stop_hook_active": false, "x": "\xff"}'
    payload = hook._parse_stop_payload(raw)
    assert payload.get("stop_hook_active") is True, (
        "an invalid-UTF-8 payload must allow stop (fail-open)")
    _seed_inbox(comms, "charc")
    assert hook.handle_stop(payload, {"SWING_ROLE": "charc"}, comms) is None


def test_non_dict_payload_allows_stop(comms):
    payload = hook._parse_stop_payload(b"[1, 2, 3]")
    assert payload.get("stop_hook_active") is True
    _seed_inbox(comms, "charc")
    assert hook.handle_stop(payload, {"SWING_ROLE": "charc"}, comms) is None


def test_output_is_ascii(comms):
    _seed_inbox(comms, "charc")
    reason = hook.handle_stop(
        {"stop_hook_active": False}, {"SWING_ROLE": "charc"}, comms)
    reason.encode("cp1252")  # must not raise


# --- main() wiring -----------------------------------------------------------

def test_main_blocks_and_emits_decision_json(comms, monkeypatch):
    _seed_inbox(comms, "charc")
    buf = io.StringIO()
    fake_stdin = mock.Mock()
    fake_stdin.buffer = io.BytesIO(b'{"stop_hook_active": false}')
    monkeypatch.setattr(hook, "comms_root_default", lambda: comms)
    monkeypatch.setenv("SWING_ROLE", "charc")
    with mock.patch.object(sys, "stdin", fake_stdin), \
            contextlib.redirect_stdout(buf):
        rc = hook.main()
    assert rc == 0
    out = json.loads(buf.getvalue())
    assert out["decision"] == "block"
    assert out["reason"]


def test_main_always_exit_0_on_internal_error(monkeypatch):
    monkeypatch.setenv("SWING_ROLE", "charc")

    def boom():
        raise RuntimeError("kaboom")

    monkeypatch.setattr(hook, "comms_root_default", boom)
    fake_stdin = mock.Mock()
    fake_stdin.buffer = io.BytesIO(b'{"stop_hook_active": false}')
    with mock.patch.object(sys, "stdin", fake_stdin):
        rc = hook.main()
    assert rc == 0


def test_subprocess_noop_exit_0_no_block_without_role():
    # the unseeded default: a session WITHOUT SWING_ROLE never blocks the stop.
    env = {k: v for k, v in os.environ.items() if k != "SWING_ROLE"}
    proc = subprocess.run(
        [sys.executable, str(_HOOK_PATH)],
        input=b'{"stop_hook_active": false}',
        capture_output=True, env=env, timeout=30)
    assert proc.returncode == 0
    assert proc.stdout.strip() == b""


def test_subprocess_exit_0_when_sibling_import_broken(tmp_path):
    # Phase-20 rider R1: the sibling `comms_unread_hook` import must be GUARDED
    # so a missing/corrupt sibling degrades to allow-stop (exit 0) -- the same
    # fail-OPEN direction as every other path. A bare top-level import (outside
    # main()'s try/except) crashes the hook at IMPORT time = fail-CLOSED, which
    # could trap the agent. Copy the hook next to a BROKEN sibling so
    # `python comms_stop_hook.py` resolves the broken one from sys.path[0].
    (tmp_path / "comms_stop_hook.py").write_bytes(_HOOK_PATH.read_bytes())
    (tmp_path / "comms_unread_hook.py").write_text(
        "raise ImportError('simulated corrupt/missing sibling')\n", encoding="utf-8")
    env = {**os.environ, "SWING_ROLE": "charc"}
    proc = subprocess.run(
        [sys.executable, str(tmp_path / "comms_stop_hook.py")],
        input=b'{"stop_hook_active": false}',
        capture_output=True, env=env, timeout=30)
    assert proc.returncode == 0, (
        "a broken sibling import must fail-OPEN (exit 0), got "
        f"{proc.returncode}: {proc.stderr.decode('utf-8', 'replace')}")
    assert proc.stdout.strip() == b""  # degraded hook emits no block
