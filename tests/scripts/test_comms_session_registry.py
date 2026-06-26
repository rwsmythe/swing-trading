"""Tests for scripts/comms_session_registry.py -- the single-sourced session
registry library (G6 Arc A).

Stdlib-only, clock-injected: every time-comparing function takes an injectable
`now` so staleness boundaries are frozen (debt D9 -- no wall-clock flake). All
behavioral tests run over a tmp_path comms tree; the real comms/ is never
touched.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "comms_session_registry.py")
_spec = importlib.util.spec_from_file_location("comms_session_registry", _MODULE_PATH)
reg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reg)

_NOW = datetime(2026, 6, 25, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def root(tmp_path):
    return tmp_path / "comms"


# --- sub-cycle 1: is_valid_session_id [guard #5] ---------------------------

def test_is_valid_session_id_accepts_safe_segments():
    for sid in ("g1", "2026-06-25T12.00.00", "abc_DEF-1"):
        assert reg.is_valid_session_id(sid) is True


def test_is_valid_session_id_rejects_unsafe():
    for sid in ("", ".", "..", "../evil", "/abs", "a/b", "a\\b", "a*b"):
        assert reg.is_valid_session_id(sid) is False
    # non-str
    assert reg.is_valid_session_id(None) is False
    assert reg.is_valid_session_id(123) is False


# --- sub-cycle 2: path helpers [guard #2, #5] ------------------------------

def test_entry_path_under_sessions(root):
    p = reg.entry_path(root, "g1")
    assert p == root / "sessions" / "g1.json"


def test_per_generation_paths(root):
    assert reg.per_generation_inbox(root, "g1") == (
        root / "orchestrator" / "g1" / "inbox")
    assert reg.per_generation_read(root, "g1") == (
        root / "orchestrator" / "g1" / "read")


def test_path_helpers_raise_on_unsafe_sid(root):
    for builder in (reg.entry_path, reg.per_generation_inbox,
                    reg.per_generation_read):
        with pytest.raises(ValueError):
            builder(root, "../evil")


def test_ensure_per_generation_inbox_idempotent(root):
    inbox = reg.ensure_per_generation_inbox(root, "g1")
    assert inbox.is_dir()
    assert (root / "orchestrator" / "g1" / "read").is_dir()
    # second call must not raise
    reg.ensure_per_generation_inbox(root, "g1")
    assert inbox.is_dir()


def test_ensure_per_generation_inbox_raises_on_unsafe(root):
    with pytest.raises(ValueError):
        reg.ensure_per_generation_inbox(root, "../evil")


# --- sub-cycle 3: write_entry / read_entry [guard #3] ----------------------

def test_write_then_read_round_trip_fresh_tree(root):
    # No pre-made comms/sessions/ -- the first write_entry must bootstrap it.
    assert not (root / "sessions").exists()
    reg.write_entry(root, "g1", "orchestrator", "/x/transcript.jsonl", _NOW)
    entry = reg.read_entry(root, "g1")
    assert entry is not None
    assert entry["session_id"] == "g1"
    assert entry["role"] == "orchestrator"
    assert entry["transcript_path"] == "/x/transcript.jsonl"
    assert entry["started_ts"] == _NOW.isoformat()
    assert entry["last_seen"] == _NOW.isoformat()


def test_write_entry_preserves_started_ts(root):
    t0 = _NOW
    t1 = _NOW + timedelta(minutes=5)
    reg.write_entry(root, "g1", "orchestrator", "", t1, started_ts=t0.isoformat())
    entry = reg.read_entry(root, "g1")
    assert entry["started_ts"] == t0.isoformat()
    assert entry["last_seen"] == t1.isoformat()


def test_read_entry_missing_returns_none(root):
    assert reg.read_entry(root, "nope") is None


def test_read_entry_malformed_returns_none(root):
    path = reg.entry_path(root, "g1")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00not json{{{")
    # degrade-gracefully: None, never raises
    assert reg.read_entry(root, "g1") is None


# --- sub-cycle 4: read_entries identity invariant [guard #3, #5] ----------

def test_read_entries_skips_malformed_and_mismatched(root):
    reg.write_entry(root, "g1", "orchestrator", "", _NOW)
    reg.write_entry(root, "g2", "orchestrator", "", _NOW)
    # a malformed file
    bad = reg.entry_path(root, "g3")
    bad.write_text("garbage", encoding="utf-8")
    # an internally inconsistent entry: filename g4 but embedded session_id g9
    mismatch = root / "sessions" / "g4.json"
    mismatch.write_text(
        json.dumps({"session_id": "g9", "role": "orchestrator",
                    "last_seen": _NOW.isoformat()}), encoding="utf-8")
    entries = reg.read_entries(root)
    ids = sorted(e["session_id"] for e in entries)
    assert ids == ["g1", "g2"]


# --- sub-cycle 5: touch_last_seen ------------------------------------------

def test_touch_last_seen_refreshes_and_preserves(root):
    t0 = _NOW
    t1 = _NOW + timedelta(minutes=10)
    reg.write_entry(root, "g1", "orchestrator", "/t.jsonl", t0)
    reg.touch_last_seen(root, "g1", t1, role="orchestrator")
    entry = reg.read_entry(root, "g1")
    assert entry["last_seen"] == t1.isoformat()
    assert entry["started_ts"] == t0.isoformat()
    assert entry["role"] == "orchestrator"


def test_touch_last_seen_recreates_if_missing(root):
    t1 = _NOW + timedelta(minutes=10)
    reg.touch_last_seen(root, "g1", t1, role="orchestrator",
                        transcript_path="/t.jsonl")
    entry = reg.read_entry(root, "g1")
    assert entry is not None
    assert entry["role"] == "orchestrator"
    assert entry["last_seen"] == t1.isoformat()


def test_touch_last_seen_missing_without_role_raises(root):
    with pytest.raises(ValueError):
        reg.touch_last_seen(root, "g1", _NOW)


# --- sub-cycle 6: prune_stale [clock frozen] -------------------------------

def test_prune_stale_deletes_only_stale(root):
    stale_seen = (_NOW - timedelta(seconds=reg.STALE_SECONDS + 1)).isoformat()
    live_seen = (_NOW - timedelta(seconds=reg.STALE_SECONDS - 1)).isoformat()
    reg.write_entry(root, "stale", "orchestrator", "", _NOW,
                    started_ts=stale_seen)
    # overwrite last_seen explicitly to the stale value
    _force_last_seen(reg, root, "stale", stale_seen)
    reg.write_entry(root, "live", "orchestrator", "", _NOW,
                    started_ts=live_seen)
    _force_last_seen(reg, root, "live", live_seen)
    pruned = reg.prune_stale(root, _NOW)
    assert pruned == ["stale"]
    assert reg.read_entry(root, "stale") is None
    assert reg.read_entry(root, "live") is not None


def test_prune_stale_removes_malformed_last_seen(root):
    path = root / "sessions" / "g1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"session_id": "g1", "role": "orchestrator",
                    "last_seen": "not-a-timestamp"}), encoding="utf-8")
    pruned = reg.prune_stale(root, _NOW)
    assert pruned == ["g1"]
    assert not path.exists()


# --- sub-cycle 7: newest_live [guard #1 substrate] -------------------------

def test_newest_live_none_when_empty(root):
    assert reg.newest_live(root, _NOW) is None


def test_newest_live_returns_max_started(root):
    older = (_NOW - timedelta(minutes=5)).isoformat()
    newer = (_NOW - timedelta(minutes=1)).isoformat()
    reg.write_entry(root, "old", "orchestrator", "", _NOW, started_ts=older)
    _force_last_seen(reg, root, "old", _NOW.isoformat())
    reg.write_entry(root, "new", "orchestrator", "", _NOW, started_ts=newer)
    _force_last_seen(reg, root, "new", _NOW.isoformat())
    win = reg.newest_live(root, _NOW)
    assert win["session_id"] == "new"


def test_newest_live_ignores_non_orchestrator_role(root):
    reg.write_entry(root, "d1", "charc", "", _NOW)
    _force_last_seen(reg, root, "d1", _NOW.isoformat())
    assert reg.newest_live(root, _NOW) is None


def test_newest_live_deprioritizes_malformed_started(root):
    reg.write_entry(root, "good", "orchestrator", "", _NOW,
                    started_ts=(_NOW - timedelta(minutes=5)).isoformat())
    _force_last_seen(reg, root, "good", _NOW.isoformat())
    # garbage started_ts -- must never win newest
    bad = root / "sessions" / "bad.json"
    bad.write_text(
        json.dumps({"session_id": "bad", "role": "orchestrator",
                    "started_ts": "zzz-not-a-date",
                    "last_seen": _NOW.isoformat()}), encoding="utf-8")
    win = reg.newest_live(root, _NOW)
    assert win["session_id"] == "good"


def test_newest_live_tie_breaks_on_lexically_greatest_sid(root):
    # All-equal started_ts: the deterministic final tiebreaker is the lexically
    # GREATEST session_id (pinned by this oracle; see plan 2.1).
    same = (_NOW - timedelta(minutes=1)).isoformat()
    for sid in ("aaa", "zzz", "mmm"):
        reg.write_entry(root, sid, "orchestrator", "", _NOW, started_ts=same)
        _force_last_seen(reg, root, sid, _NOW.isoformat())
    win = reg.newest_live(root, _NOW)
    assert win["session_id"] == "zzz"


# --- sub-cycle 8: dependency posture [lock: stdlib-only] -------------------

def test_registry_imports_are_stdlib_only():
    import ast
    import sys

    tree = ast.parse(_MODULE_PATH.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    roots.discard("__future__")
    nonstdlib = roots - set(sys.stdlib_module_names)
    assert nonstdlib == set(), f"non-stdlib imports: {nonstdlib}"


# --- sub-cycle 9: atomic-write same-dir guard [lock: cross-volume-safe] -----

def test_atomic_write_lands_at_target_only(root, monkeypatch):
    import tempfile as _tempfile
    target = root / "sessions" / "g1.json"
    seen_dirs = []
    orig_mkstemp = _tempfile.mkstemp

    def wrapped_mkstemp(*args, **kwargs):
        seen_dirs.append(kwargs.get("dir"))
        return orig_mkstemp(*args, **kwargs)

    monkeypatch.setattr(reg.tempfile, "mkstemp", wrapped_mkstemp)
    reg._atomic_write_text(target, "first")
    assert target.read_text(encoding="utf-8") == "first"
    # (c) staging dir is target.parent
    assert seen_dirs and seen_dirs[-1] == str(target.parent)
    # (b) after a successful write, the ONLY artifact anywhere in the tree is
    # target (no stray temp leftover -- proves clean staging + no cross-volume).
    artifacts = [p for p in root.rglob("*") if p.is_file()]
    assert artifacts == [target]
    # (d) overwrite fully replaces -- never torn.
    reg._atomic_write_text(target, "second")
    assert target.read_text(encoding="utf-8") == "second"
    artifacts = [p for p in root.rglob("*") if p.is_file()]
    assert artifacts == [target]


def _force_last_seen(reg_mod, root, sid, value):
    """Test helper: stamp an exact last_seen onto an entry (bypass the clock)."""
    path = reg_mod.entry_path(root, sid)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["last_seen"] = value
    path.write_text(json.dumps(data), encoding="utf-8")
