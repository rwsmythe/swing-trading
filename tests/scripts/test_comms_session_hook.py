"""Tests for scripts/comms_session_hook.py -- the lifecycle hook (G6 Arc A).

Exercises handle_session_start / handle_heartbeat directly over a tmp comms
tree with synthetic payload + env dicts + a frozen now (the pure-handler seam),
plus the ALWAYS-exit-0 resilience contract of main().
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_HOOK_PATH = _SCRIPTS / "comms_session_hook.py"
_REG_PATH = _SCRIPTS / "comms_session_registry.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Put scripts/ on the path so the hook's `import comms_session_registry` resolves.
sys.path.insert(0, str(_SCRIPTS))
reg = _load("comms_session_registry", _REG_PATH)
hook = _load("comms_session_hook", _HOOK_PATH)

_NOW = datetime(2026, 6, 25, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def root(tmp_path):
    return tmp_path / "comms"


@pytest.fixture(autouse=True)
def _never_the_real_comms_tree(tmp_path, monkeypatch):
    """Redirect the hook's DEFAULT comms root away from the operator's tree.

    Codex R3 MAJOR 1 (a PRE-EXISTING hole this arc inherited): `hook.main()`
    resolves `comms_root_from_file()` -- the REAL `<repo>/comms` -- and
    `handle_session_start` calls `prune_stale` BEFORE the role gate, so any
    `main(["session-start"])` in the suite UNLINKS the operator's stale
    `comms/sessions/*.json` role-recovery records. The pure handlers already
    take an explicit root; this closes the `main()` seam the same way (the
    function-scoped seam-redirect that CLAUDE.md names as the real prevention,
    as opposed to a session-scoped world-frozen belt).
    """
    safe = tmp_path / "redirected-comms"
    monkeypatch.setattr(hook._reg, "comms_root_from_file", lambda: safe)
    return safe


# --- sub-cycle 1: session-start registers PRESENCE ONLY (21-D) -------------

def test_session_start_registers_orchestrator(root):
    hook.handle_session_start(
        {"session_id": "g1", "transcript_path": "/t.jsonl"},
        {"SWING_ROLE": "orchestrator"}, root, _NOW)
    entry = reg.read_entry(root, "g1")
    assert entry is not None
    assert entry["role"] == "orchestrator"


def test_session_start_creates_no_mailbox_directory(root):
    """21-D: registration is presence-only -- it builds NO per-gen mailbox.

    Pre-21-D the hook created comms/orchestrator/<sid>/{inbox,read}; the
    orchestrator inbox is now the singular comms/orchestrator/inbox that
    role_mail bootstraps on first delivery, so the hook must touch nothing
    under comms/orchestrator/ at all.
    """
    hook.handle_session_start(
        {"session_id": "g1", "transcript_path": "/t.jsonl"},
        {"SWING_ROLE": "orchestrator"}, root, _NOW)
    assert not (root / "orchestrator").exists()
    # the ONLY thing written is the presence record
    assert [p.name for p in sorted(root.rglob("*")) if p.is_file()] == [
        "g1.json"]


# --- sub-cycle 2: session-start ALWAYS prunes ------------------------------

def test_session_start_always_prunes_even_for_director(root):
    stale_seen = (_NOW - timedelta(seconds=reg.STALE_SECONDS + 1)).isoformat()
    reg.write_entry(root, "stale", "orchestrator", "", _NOW,
                    started_ts=stale_seen)
    _force_last_seen(root, "stale", stale_seen)
    # A DIFFERENT new session-start (role=charc) still prunes the stale entry.
    hook.handle_session_start(
        {"session_id": "d1"}, {"SWING_ROLE": "charc"}, root, _NOW)
    assert reg.read_entry(root, "stale") is None


# --- sub-cycle 3: director registers, no mailbox side effects --------------

def test_session_start_director_no_per_gen_inbox(root):
    hook.handle_session_start(
        {"session_id": "d1"}, {"SWING_ROLE": "charc"}, root, _NOW)
    entry = reg.read_entry(root, "d1")
    assert entry is not None
    assert entry["role"] == "charc"
    assert not (root / "orchestrator" / "d1").exists()


def test_session_start_unregistrable_role_no_entry(root):
    hook.handle_session_start(
        {"session_id": "x1"}, {"SWING_ROLE": "operator"}, root, _NOW)
    assert reg.read_entry(root, "x1") is None


# --- sub-cycle 4: heartbeat refreshes an orchestrator's last_seen (SEAM) ----

def test_heartbeat_refreshes_orchestrator_last_seen(root):
    t0 = _NOW
    t1 = _NOW + timedelta(minutes=10)
    reg.write_entry(root, "g1", "orchestrator", "", t0)
    hook.handle_heartbeat(
        {"session_id": "g1"}, {"SWING_ROLE": "orchestrator"}, root, t1)
    entry = reg.read_entry(root, "g1")
    # The heartbeat has NO {charc,rd} gate -- an orchestrator DOES refresh. A
    # reintroduced director-only gate would leave last_seen == t0 -> fails.
    assert entry["last_seen"] == t1.isoformat()
    assert entry["started_ts"] == t0.isoformat()


# --- sub-cycle 5: heartbeat recreate-if-missing (resume path) --------------

def test_heartbeat_recreates_pruned_entry(root):
    t1 = _NOW + timedelta(minutes=10)
    hook.handle_heartbeat(
        {"session_id": "g1", "transcript_path": "/t.jsonl"},
        {"SWING_ROLE": "orchestrator"}, root, t1)
    entry = reg.read_entry(root, "g1")
    assert entry is not None
    assert entry["role"] == "orchestrator"
    assert entry["last_seen"] == t1.isoformat()
    # 21-D: presence-only -- the heartbeat builds no mailbox directory either
    assert not (root / "orchestrator").exists()


# --- sub-cycle 6: degraded / unsafe sid ------------------------------------

def test_unsafe_session_id_no_registration_no_escape(root, capsys):
    hook.handle_session_start(
        {"session_id": "../evil"}, {"SWING_ROLE": "orchestrator"}, root, _NOW)
    err = capsys.readouterr().err
    assert "session_id" in err.lower()
    # No file escaped the per-gen tree; sessions/ holds no 'evil' entry.
    assert not (root.parent / "evil").exists()
    leaked = list(root.rglob("*evil*")) if root.exists() else []
    assert leaked == []


def test_no_session_id_no_registration(root, capsys):
    hook.handle_session_start(
        {}, {"SWING_ROLE": "orchestrator"}, root, _NOW)
    capsys.readouterr()
    # nothing registered
    assert reg.read_entries(root) == []


def test_env_fallback_session_id_used_when_payload_absent(root, capsys):
    # PRIMARY is payload["session_id"]; the degraded fallback is the live
    # CLAUDE_CODE_SESSION_ID env var (grounded against the live hook contract).
    hook.handle_session_start(
        {}, {"SWING_ROLE": "orchestrator",
             "CLAUDE_CODE_SESSION_ID": "envgen"}, root, _NOW)
    err = capsys.readouterr().err
    assert "DEGRADED" in err or "degraded" in err
    assert reg.read_entry(root, "envgen") is not None


# --- sub-cycle 7: ALWAYS exit 0 resilience ---------------------------------

def test_main_unknown_mode_exits_zero():
    assert hook.main(["bogus-mode"]) == 0


def test_main_no_args_exits_zero():
    assert hook.main([]) == 0


def test_main_session_start_no_stdin_exits_zero(monkeypatch):
    # pytest's DontReadFromInput raises on stdin.read(); the hook must swallow it.
    monkeypatch.delenv("SWING_ROLE", raising=False)
    assert hook.main(["session-start"]) == 0
    assert hook.main(["heartbeat"]) == 0


def test_main_internal_raise_exits_zero(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(hook, "handle_session_start", boom)
    monkeypatch.setattr(hook, "_read_payload", lambda: {"session_id": "g1"})
    monkeypatch.setenv("SWING_ROLE", "orchestrator")
    assert hook.main(["session-start"]) == 0


def test_main_never_prunes_the_real_comms_tree(monkeypatch,
                                               _never_the_real_comms_tree):
    """main()'s DEFAULT root must never be the operator's live comms/ tree.

    Discriminating: without the redirect fixture this sees the real
    `<repo>/comms` and fails -- which is exactly the state in which the suite
    was silently unlinking real `comms/sessions/*.json` entries.
    """
    seen: list[Path] = []
    real_prune = hook._reg.prune_stale
    monkeypatch.setattr(hook._reg, "prune_stale",
                        lambda root, now, *a, **k: (seen.append(Path(root)),
                                                    real_prune(root, now))[1])
    monkeypatch.delenv("SWING_ROLE", raising=False)
    assert hook.main(["session-start"]) == 0
    assert seen == [_never_the_real_comms_tree]
    real_comms = Path(_SCRIPTS).parent / "comms"
    assert seen[0].resolve() != real_comms.resolve()


def test_subprocess_no_swing_role_exits_zero_no_registration(tmp_path):
    # The quiet default (no SWING_ROLE) -- witness it, the seeded-gate-masks-
    # default discipline. Runs the hook as a real subprocess via stdin. Inherit
    # the real env (so the interpreter starts) but with SWING_ROLE removed.
    #
    # The hook resolves its comms root from __file__ (<script dir>/../comms), so
    # a subprocess of the REAL script would prune the operator's live tree (a
    # monkeypatch cannot cross the process boundary). Run a COPY staged under
    # tmp_path instead: identical code, and its resolved root is tmp_path/comms.
    import os
    import shutil
    staged = tmp_path / "scripts"
    staged.mkdir()
    for src in (_HOOK_PATH, _REG_PATH):
        shutil.copy2(src, staged / src.name)
    env = {k: v for k, v in os.environ.items() if k != "SWING_ROLE"}
    proc = subprocess.run(
        [sys.executable, str(staged / _HOOK_PATH.name), "session-start"],
        input=b'{"session_id":"g1"}',
        capture_output=True, env=env, check=False,
    )
    assert proc.returncode == 0
    # and it touched only the staged tree (never the real repo comms/)
    assert not (Path(_SCRIPTS).parent / "comms" / "sessions"
                / "g1.json").exists()


def _force_last_seen(root, sid, value):
    import json
    path = reg.entry_path(root, sid)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["last_seen"] = value
    path.write_text(json.dumps(data), encoding="utf-8")
