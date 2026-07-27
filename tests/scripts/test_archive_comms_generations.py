"""Tests for scripts/archive_comms_generations.py -- the 21-D one-shot
per-generation comms migration helper.

DRY-RUN FIRST is the whole safety property: the default run prints the plan and
touches nothing. Every test runs over a tmp comms root; the real comms/ tree is
never touched (and the helper is never executed against it by the suite).
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

_MODULE_PATH = (Path(__file__).resolve().parents[2] / "scripts"
                / "archive_comms_generations.py")
_spec = importlib.util.spec_from_file_location("archive_comms_generations",
                                               _MODULE_PATH)
mig = importlib.util.module_from_spec(_spec)
# Register BEFORE exec: a @dataclass resolves its module via
# sys.modules[cls.__module__] at class-creation time (Python 3.14).
sys.modules["archive_comms_generations"] = mig
_spec.loader.exec_module(mig)


@pytest.fixture
def comms(tmp_path):
    return tmp_path / "comms"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _seed_gen(comms, sid, *, unread=(), read=()):
    for name in unread:
        _write(comms / "orchestrator" / sid / "inbox" / name, f"body of {name}\n")
    for name in read:
        _write(comms / "orchestrator" / sid / "read" / name, f"body of {name}\n")


def _snapshot(root: Path) -> dict[str, str]:
    """relpath -> sha256 for every file under root (the intactness oracle)."""
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = hashlib.sha256(
                p.read_bytes()).hexdigest()
    return out


def _run(comms, *args):
    return mig.main(["--comms-root", str(comms), *args])


# --- dry run is the default and mutates NOTHING ----------------------------

def test_dry_run_is_the_default_and_changes_nothing(comms, capsys):
    _seed_gen(comms, "gen-a", unread=("20260101T010000Z-charc-a.md",))
    _seed_gen(comms, "gen-b", read=("20260102T010000Z-rd-b.md",))
    before = _snapshot(comms)
    rc = _run(comms)
    assert rc == 0
    assert _snapshot(comms) == before  # byte-for-byte untouched
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "--execute" in out  # tells the operator how to actually do it
    # it printed exactly what it WOULD move
    assert "gen-a" in out and "gen-b" in out
    assert "_archive/gen-a/inbox/20260101T010000Z-charc-a.md" in out


def test_dry_run_on_an_absent_tree_is_a_clean_noop(comms, capsys):
    rc = _run(comms)
    assert rc == 0
    assert not comms.exists()
    assert "nothing to migrate" in capsys.readouterr().out.lower()


# --- enumeration is AT RUN TIME, never a hard-coded list -------------------

def test_generations_enumerated_from_disk_not_a_hard_coded_list(comms):
    for sid in ("aaaaaaaa-1111", "bbbbbbbb-2222", "cccccccc-3333"):
        _seed_gen(comms, sid, unread=(f"20260101T010000Z-charc-{sid}.md",))
    plan = mig.build_plan(comms, live_session=None)
    assert sorted(plan.generations) == ["aaaaaaaa-1111", "bbbbbbbb-2222",
                                        "cccccccc-3333"]


def test_module_hard_codes_no_session_ids():
    import re
    src = _MODULE_PATH.read_text(encoding="utf-8")
    # a hard-coded list would orphan every generation it forgot (the exact
    # defect the brief corrected: 5 named, 8 on disk).
    assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-", src)


def test_reserved_names_are_never_treated_as_generations(comms):
    _write(comms / "orchestrator" / "inbox" / "20260101T010000Z-charc-s.md", "x\n")
    _write(comms / "orchestrator" / "read" / "20260101T020000Z-charc-r.md", "x\n")
    _write(comms / "orchestrator" / "_archive" / "old" / "read" / "z.md", "x\n")
    _write(comms / "orchestrator" / "stray.md", "not a generation\n")
    plan = mig.build_plan(comms, live_session=None)
    assert plan.generations == []
    assert plan.moves == []


# --- execute: non-live generations become _archive/<sid>/... ---------------

def test_execute_archives_generations_intact(comms, capsys):
    _seed_gen(comms, "gen-a", unread=("20260101T010000Z-charc-a.md",),
              read=("20260101T000000Z-rd-old.md",))
    _seed_gen(comms, "gen-b", read=("20260102T010000Z-rd-b.md",))
    before = _snapshot(comms)
    rc = _run(comms, "--execute")
    assert rc == 0
    arch = comms / "orchestrator" / "_archive"
    assert (arch / "gen-a" / "inbox" / "20260101T010000Z-charc-a.md").is_file()
    assert (arch / "gen-a" / "read" / "20260101T000000Z-rd-old.md").is_file()
    assert (arch / "gen-b" / "read" / "20260102T010000Z-rd-b.md").is_file()
    # D3 -- intact AND readable: same content, same count, nothing deleted
    after = _snapshot(comms)
    assert sorted(after.values()) == sorted(before.values())
    assert len(after) == len(before)
    assert (arch / "gen-a" / "inbox" / "20260101T010000Z-charc-a.md").read_text(
        encoding="utf-8") == "body of 20260101T010000Z-charc-a.md\n"
    # the old per-generation dirs are gone from the live tree (emptied, then
    # their empty shells removed -- no FILE was ever deleted)
    assert not (comms / "orchestrator" / "gen-a").exists()
    assert not (comms / "orchestrator" / "gen-b").exists()
    assert "VERIFIED" in capsys.readouterr().out


def test_execute_preserves_unexpected_subpaths(comms):
    _write(comms / "orchestrator" / "gen-a" / "notes" / "scratch.txt", "keep me\n")
    rc = _run(comms, "--execute")
    assert rc == 0
    kept = (comms / "orchestrator" / "_archive" / "gen-a" / "notes"
            / "scratch.txt")
    assert kept.read_text(encoding="utf-8") == "keep me\n"


# --- the LIVE generation is not history: its mail joins the singular inbox --

def test_live_generation_mail_lands_in_the_singular_inbox(comms):
    _seed_gen(comms, "live-gen", unread=("20260103T010000Z-charc-u.md",),
              read=("20260103T000000Z-charc-r.md",))
    _seed_gen(comms, "dead-gen", read=("20260101T010000Z-rd-d.md",))
    rc = _run(comms, "--execute", "--live-session", "live-gen")
    assert rc == 0
    orch = comms / "orchestrator"
    assert (orch / "inbox" / "20260103T010000Z-charc-u.md").is_file()
    assert (orch / "read" / "20260103T000000Z-charc-r.md").is_file()
    # ... and the live gen's mail is NOT filed away as history
    assert not (orch / "_archive" / "live-gen" / "inbox").exists()
    assert not (orch / "_archive" / "live-gen" / "read").exists()
    # the dead generation still archives normally
    assert (orch / "_archive" / "dead-gen" / "read"
            / "20260101T010000Z-rd-d.md").is_file()


def test_live_session_must_exist_on_disk(comms, capsys):
    _seed_gen(comms, "gen-a", read=("20260101T010000Z-rd-a.md",))
    rc = _run(comms, "--execute", "--live-session", "not-a-gen")
    assert rc == 1
    assert "not-a-gen" in capsys.readouterr().err
    # refused BEFORE any move
    assert (comms / "orchestrator" / "gen-a" / "read"
            / "20260101T010000Z-rd-a.md").is_file()


def test_unsafe_live_session_refused(comms, capsys):
    _seed_gen(comms, "gen-a", read=("m.md",))
    rc = _run(comms, "--execute", "--live-session", "../evil")
    assert rc == 1
    assert "session" in capsys.readouterr().err.lower()
    assert (comms / "orchestrator" / "gen-a" / "read" / "m.md").is_file()


# --- collisions never clobber (ack must never delete history) --------------

def test_existing_destination_is_never_overwritten(comms):
    _seed_gen(comms, "gen-a", read=("dup.md",))
    _write(comms / "orchestrator" / "_archive" / "gen-a" / "read" / "dup.md",
           "PRE-EXISTING\n")
    rc = _run(comms, "--execute")
    assert rc == 0
    arch = comms / "orchestrator" / "_archive" / "gen-a" / "read"
    assert arch.joinpath("dup.md").read_text(encoding="utf-8") == "PRE-EXISTING\n"
    assert arch.joinpath("dup-2.md").read_text(encoding="utf-8") == "body of dup.md\n"


def test_live_adoption_collision_never_overwrites(comms):
    _seed_gen(comms, "live-gen", unread=("dup.md",))
    _write(comms / "orchestrator" / "inbox" / "dup.md", "PRE-EXISTING\n")
    rc = _run(comms, "--execute", "--live-session", "live-gen")
    assert rc == 0
    inbox = comms / "orchestrator" / "inbox"
    assert inbox.joinpath("dup.md").read_text(encoding="utf-8") == "PRE-EXISTING\n"
    assert inbox.joinpath("dup-2.md").read_text(
        encoding="utf-8") == "body of dup.md\n"


# --- the move itself must not clobber (Codex R3 MAJOR 2) -------------------

def test_destination_appearing_after_planning_is_not_overwritten(comms,
                                                                 monkeypatch):
    """A file that appears BETWEEN build_plan and the move must survive.

    `_nonclobbering_dest` only consults disk at PLAN time, so a plain
    `os.replace` would silently overwrite a destination created in the gap --
    destroying archived history while the run still printed VERIFIED. The
    reservation must therefore happen at MOVE time. Simulated here by handing
    `run()` a stale plan whose destination already exists.
    """
    _seed_gen(comms, "gen-a", read=("m.md",))
    real_build = mig.build_plan

    def _stale_plan(root, live_session=None):
        plan = real_build(root, live_session)
        # the gap: something lands on the planned destination after planning
        for _src, dest, _kind in plan.moves:
            _write(dest, "APPEARED AFTER PLANNING\n")
        return plan

    monkeypatch.setattr(mig, "build_plan", _stale_plan)
    rc = _run(comms, "--execute")
    assert rc == 0
    arch = comms / "orchestrator" / "_archive" / "gen-a" / "read"
    # the interloper is INTACT ...
    assert arch.joinpath("m.md").read_text(
        encoding="utf-8") == "APPEARED AFTER PLANNING\n"
    # ... and the migrated message landed beside it, not on top of it
    assert arch.joinpath("m-2.md").read_text(
        encoding="utf-8") == "body of m.md\n"


def test_reserve_dest_never_returns_an_existing_path(comms):
    target = _write(comms / "orchestrator" / "_archive" / "g" / "read" / "m.md",
                    "taken\n")
    reserved = mig._reserve_dest(target)
    assert reserved != target
    assert reserved.name == "m-2.md"
    assert reserved.is_file()          # reserved by EXCLUSIVE create, not a guess
    assert target.read_text(encoding="utf-8") == "taken\n"


# --- a failed move must not leave a fake archived message (R4 MAJOR 2) -----

def test_failed_move_leaves_no_empty_placeholder(comms, capsys, monkeypatch):
    """If os.replace fails, the reserved placeholder must NOT survive.

    An orphaned zero-byte file at an archive path is worse than no file: a later
    run would treat it as an existing destination and file the REAL message
    beside it under `-2`, leaving a convincing empty impostor in the history.
    """
    _seed_gen(comms, "gen-a", read=("m.md",))

    def _boom(src, dest):
        raise OSError(13, "simulated failure")

    monkeypatch.setattr(mig.os, "replace", _boom)
    rc = _run(comms, "--execute")
    assert rc == 1
    err = capsys.readouterr().err
    assert "VERIFICATION FAILED" in err  # reported, not an escaped traceback
    # the source is untouched and NO placeholder was left behind
    assert (comms / "orchestrator" / "gen-a" / "read" / "m.md").read_text(
        encoding="utf-8") == "body of m.md\n"
    assert not (comms / "orchestrator" / "_archive" / "gen-a" / "read"
                / "m.md").exists()


# --- symlinks are refused, never silently mis-archived (R4 MAJOR 1) --------

def _symlink_or_skip(link: Path, target: Path, *, target_is_dir=False):
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=target_is_dir)
    except (OSError, NotImplementedError):  # Windows without developer mode
        pytest.skip("symlink creation not permitted in this environment")


def test_symlinked_message_is_refused_not_archived(comms, tmp_path, capsys):
    """A symlinked 'message' must not be archived as a link + reported VERIFIED.

    os.replace moves the LINK; the digest is read through it both times, so the
    run would print VERIFIED while the archive holds a pointer whose target can
    later change or vanish -- history that is not actually preserved.
    """
    outside = _write(tmp_path / "outside" / "live.md", "lives elsewhere\n")
    _symlink_or_skip(comms / "orchestrator" / "gen-a" / "read" / "m.md", outside)
    rc = _run(comms, "--execute")
    assert rc == 1
    err = capsys.readouterr().err
    assert "symlink" in err.lower()
    assert "gen-a" in err
    # nothing moved, and the external target is untouched
    assert (comms / "orchestrator" / "gen-a" / "read" / "m.md").is_symlink()
    assert outside.read_text(encoding="utf-8") == "lives elsewhere\n"
    assert not (comms / "orchestrator" / "_archive").exists()


def test_symlink_refusal_without_needing_symlink_privileges(comms, capsys,
                                                            monkeypatch):
    """The refusal itself, exercised through the _is_symlink seam.

    The two tests above need real symlinks, which Windows refuses without
    developer mode -- a skip there would leave the guard with ZERO coverage on
    the production box. This drives the same refusal by making one planned
    message report as a link.
    """
    _seed_gen(comms, "gen-a", read=("m.md",))
    victim = comms / "orchestrator" / "gen-a" / "read" / "m.md"
    monkeypatch.setattr(mig, "_is_symlink", lambda p: p == victim)
    before = _snapshot(comms)
    rc = _run(comms, "--execute")
    assert rc == 1
    err = capsys.readouterr().err
    assert "symlink" in err.lower()
    assert "gen-a/read/m.md" in err
    assert _snapshot(comms) == before  # refused BEFORE anything moved


@pytest.mark.parametrize("reserved", ["_archive", "inbox", "read"])
def test_symlinked_reserved_destination_dir_is_refused(comms, capsys,
                                                       monkeypatch, reserved):
    """A symlinked DESTINATION dir must be refused too (R5 MAJOR 1).

    `_archive`, `inbox` and `read` are skipped as generations by NAME -- but
    they are exactly where the migration WRITES. A symlinked one would send
    archived history (or adopted live mail) through the pointer while the report
    and the sha256 verification both read back through it: VERIFIED, over
    content that is not where it says it is.
    """
    _seed_gen(comms, "live-gen", unread=("u.md",), read=("r.md",))
    victim = comms / "orchestrator" / reserved
    victim.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(mig, "_is_symlink", lambda p: p == victim)
    before = _snapshot(comms)
    rc = _run(comms, "--execute", "--live-session", "live-gen")
    assert rc == 1
    err = capsys.readouterr().err
    assert "symlink" in err.lower()
    assert reserved in err
    assert _snapshot(comms) == before  # refused BEFORE anything moved


def test_symlinked_generation_directory_is_refused(comms, tmp_path, capsys):
    elsewhere = tmp_path / "elsewhere" / "read"
    _write(elsewhere / "m.md", "x\n")
    (comms / "orchestrator").mkdir(parents=True, exist_ok=True)
    _symlink_or_skip(comms / "orchestrator" / "gen-link",
                     elsewhere.parent, target_is_dir=True)
    rc = _run(comms, "--execute")
    assert rc == 1
    assert "symlink" in capsys.readouterr().err.lower()
    assert (elsewhere / "m.md").read_text(encoding="utf-8") == "x\n"


# --- idempotence: a second execute has nothing left to do ------------------

def test_second_execute_is_a_noop(comms, capsys):
    _seed_gen(comms, "gen-a", read=("m.md",))
    assert _run(comms, "--execute") == 0
    snap = _snapshot(comms)
    capsys.readouterr()
    assert _run(comms, "--execute") == 0
    assert _snapshot(comms) == snap
    assert "nothing to migrate" in capsys.readouterr().out.lower()
