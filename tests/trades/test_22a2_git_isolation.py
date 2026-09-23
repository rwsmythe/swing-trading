"""22-A2 Codex R4-01 + R4-07 -- the ``.6`` derivation pair: every git call the
tier-2 facts depend on reads ``repo_dir``'s OWN repository, ignores
replacement objects, and dates the ref only when the reflog names the sha the
ref resolved to.

RD ruling A-R4 (R4-01, ACCEPT (a)) and CHARC's ``.6`` shape: ``_run_git``
passes ``--no-replace-objects`` before the subcommand, sets
``GIT_NO_REPLACE_OBJECTS=1``, and runs with a copy of ``os.environ`` from
which EVERY ``GIT_*`` key is removed (a rule, not a roster).  R4-07 (CHARC,
folded into the same pair): the reflog read carries the entry's object sha
(``%H``) and ``_reflog_stage`` returns ``(None, None)`` -- age UNKNOWN, never a
refusal -- when it is not the resolved sha.

D1 is RD's replace-ref forgery with its twin; D2 is one case per variable that
can CHANGE a read, each shown RED on the running git before it was kept; the
R4-07 discriminator is a staged ref move between the two stages.  D3 (the
fixture diff is ``derivation_version`` only) lives beside the history pins in
``test_22a2_g_t7_followon.py``.
"""
from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from swing.trades import frozen_value_evidence as fve
from tests.trades._git_world import GitWorld, git

ART = "docs/rd-state.md"
GENUINE = "OII 2026-08-10 pivot 53.98 stop 41.42 -- the genuine record"
FORGED = "OII 2026-08-10 pivot 53.98 stop 41.42 -- a FORGED record"
D1_AUTHOR = "2026-08-10T02:41:33-10:00"
D0_AUTHOR = "2026-08-01T09:00:00-10:00"   # the forgery claims an EARLIER instant
NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


def _body(line: str) -> bytes:
    return f"line 1\n{line}\nline 3\n".encode()


def _genuine_world(root: Path) -> tuple[GitWorld, str]:
    """A published record S (the genuine line, dated d1); deterministic shas,
    so a second world built the same way carries the SAME S."""
    world = GitWorld(root)
    world.commit("README.md", b"base\n")
    sha = world.commit(ART, _body(GENUINE), author_date=D1_AUTHOR)
    world.push()
    return world, sha


def _forge(world: GitWorld, sha: str) -> str:
    """A commit F carrying the forged line at an earlier instant, off S's
    parent; ``main`` is left where it was.  Returns F."""
    git(world.work, "checkout", "-q", "-b", "forge", f"{sha}~1")
    forged = world.commit(ART, _body(FORGED), author_date=D0_AUTHOR,
                          message="forged record")
    git(world.work, "checkout", "-q", "main")
    return forged


def _read(world: GitWorld, sha: str, quoted: str) -> fve.PreflightResult:
    sel = fve.EvidenceSelection(artifact_path=ART, artifact_commit_sha=sha,
                                quoted_text=quoted)
    return fve.read_artifact_facts(sel, repo_dir=world.work, now_utc=NOW)


class _SubprocessCounter:
    """Counts the git processes ``fve`` starts (below ``_run_git``, so a fix
    that added a git call would show)."""

    def __init__(self, monkeypatch) -> None:
        self.calls: list[tuple[str, ...]] = []
        self._real = subprocess.run
        monkeypatch.setattr(fve.subprocess, "run", self)

    def __call__(self, args, *a, **kw):
        self.calls.append(tuple(args))
        return self._real(args, *a, **kw)


# --------------------------------------------------------------------------- D1

def test_r4_01_d1_a_replace_ref_forgery_under_the_genuine_sha_is_refused(
        tmp_path: Path) -> None:
    """PRE: ``git replace S F`` makes S read as F on this box -- the forged
    line is ADMITTED as S's content.  POST: replacement is ignored, the forged
    line is not in S's artifact."""
    world, sha = _genuine_world(tmp_path / "w")
    git(world.work, "replace", sha, _forge(world, sha))
    result = _read(world, sha, FORGED)
    assert result.facts is None, result
    assert result.failure == fve.FAILURE_QUOTED_TEXT_NOT_IN_ARTIFACT


def test_r4_01_d1_twin_the_genuine_line_admits_with_the_genuine_instant(
        tmp_path: Path, monkeypatch) -> None:
    """The twin, same repo, same replace ref: the GENUINE line admits with
    ``author_instant == d1`` by EQUALITY (PRE it reads d0 -- F's date -- and
    the genuine line is refused); a refuse-everything fix fails here.  The
    per-row git process count is today's six (rev-parse, show, cat-file,
    merge-base, rev-list, the reflog read): the fix adds no git call."""
    world, sha = _genuine_world(tmp_path / "w")
    git(world.work, "replace", sha, _forge(world, sha))
    counter = _SubprocessCounter(monkeypatch)
    result = _read(world, sha, GENUINE)
    row_calls = list(counter.calls)
    assert result.failure is None, result
    assert result.facts.author_instant == datetime.fromisoformat(D1_AUTHOR)
    assert result.facts.committer_instant == datetime.fromisoformat(D1_AUTHOR)
    assert result.facts.is_ancestor is True
    assert result.facts.resolved_remote_ref_sha == world.remote_tip() == sha
    assert [c[2] for c in row_calls] == [
        "rev-parse", "show", "cat-file", "merge-base", "rev-list", "log"], row_calls
    assert all(c[:2] == ("git", "--no-replace-objects") for c in row_calls), row_calls


# --------------------------------------------------------------------------- D2

def _second_world(root: Path, *, grow: int) -> GitWorld:
    """The same history as ``_genuine_world`` (so it holds the SAME S), with
    ``grow`` more commits published: a DIFFERENT origin/main."""
    other, _sha = _genuine_world(root)
    if grow:
        other.grow_remote(grow)
    return other


def _poison_git_dir(tmp_path, world, sha):
    other = _second_world(tmp_path / "other", grow=2)
    return {"GIT_DIR": str(other.work / ".git")}, sha


def _poison_git_common_dir(tmp_path, world, sha):
    """A second repo with its OWN, different origin/main and none of this
    repo's objects.  MEASURED on git 2.52: GIT_COMMON_DIR moves the OBJECT
    read (and not, in this shape, the ref read), so origin/main resolves by
    name here and cannot be peeled there -- a same-history second repo holds
    the same objects and moves nothing (that first shape was GREEN pre-fix
    and was replaced, never kept)."""
    stranger = GitWorld(tmp_path / "stranger")
    stranger.commit("x.txt", b"unrelated\n")
    stranger.push()
    return {"GIT_COMMON_DIR": str(stranger.work / ".git")}, sha


def _poison_git_object_directory(tmp_path, world, sha):
    """An object store that does not hold origin/main's commit: the ref
    resolves by name and cannot be peeled."""
    stranger = GitWorld(tmp_path / "stranger", with_remote=False)
    stranger.commit("x.txt", b"unrelated\n")
    return {"GIT_OBJECT_DIRECTORY": str(stranger.work / ".git" / "objects")}, sha


def _poison_git_alternate_object_directories(tmp_path, world, sha):
    """An alternate store that holds a commit this repo does NOT: the row
    cites it, and the poisoned read finds it readable (and not an ancestor)
    where the clean read finds it absent."""
    other = _second_world(tmp_path / "other", grow=0)
    foreign = other.commit(ART, _body(GENUINE + " (foreign)"),
                           author_date="2026-08-11T00:00:00+00:00")
    return ({"GIT_ALTERNATE_OBJECT_DIRECTORIES": str(other.work / ".git" / "objects")},
            foreign)


def _poison_git_replace_ref_base(tmp_path, world, sha):
    """A replacement of S stored under a NON-default base: invisible to a
    default read, live once the base variable points at it."""
    forged = _forge(world, sha)
    git(world.work, "update-ref", f"refs/alt-replace/{sha}", forged)
    return {"GIT_REPLACE_REF_BASE": "refs/alt-replace/"}, sha


# GIT_NAMESPACE is DROPPED, not kept green as coverage (CHARC's D2 rule): on
# git 2.52 a namespace holding a DIFFERENT origin/main
# (``refs/namespaces/ns/refs/remotes/origin/main``) did NOT move the read --
# ``rev-parse`` and ``log -g`` of ``refs/remotes/origin/main`` returned the
# repo's own ref with ``GIT_NAMESPACE=ns`` set, and the case was GREEN pre-fix.
# Namespaces apply to the transport commands; none of the six calls is one.
# The scrub removes the variable anyway (every ``GIT_*`` key).
_POISONS = {
    "GIT_DIR": _poison_git_dir,
    "GIT_COMMON_DIR": _poison_git_common_dir,
    "GIT_OBJECT_DIRECTORY": _poison_git_object_directory,
    "GIT_ALTERNATE_OBJECT_DIRECTORIES": _poison_git_alternate_object_directories,
    "GIT_REPLACE_REF_BASE": _poison_git_replace_ref_base,
}


@pytest.mark.parametrize("variable", sorted(_POISONS))
def test_r4_01_d2_a_poisoned_git_variable_never_moves_the_facts(
        tmp_path: Path, monkeypatch, variable: str) -> None:
    """One case per variable (RD's D2): the FULL preflight result under the
    poisoned environment equals the clean-environment result.  PRE every case
    here differs (each was shown red on the running git before it was kept);
    a scrub naming only GIT_DIR passes one case and fails the rest."""
    world, sha = _genuine_world(tmp_path / "w")
    poison, cited = _POISONS[variable](tmp_path, world, sha)
    for key in [k for k in os.environ if k.startswith("GIT_")]:
        monkeypatch.delenv(key)
    clean = _read(world, cited, GENUINE if cited == sha else GENUINE + " (foreign)")
    for key, value in poison.items():
        monkeypatch.setenv(key, value)
    poisoned = _read(world, cited, GENUINE if cited == sha else GENUINE + " (foreign)")
    assert poisoned == clean, (variable, clean, poisoned)


def test_r4_01_the_forged_line_under_a_poisoned_replace_base_is_refused(
        tmp_path: Path, monkeypatch) -> None:
    """GIT_REPLACE_REF_BASE's forgery read as the forger would cite it: the
    forged line under S is refused (PRE: admitted)."""
    world, sha = _genuine_world(tmp_path / "w")
    poison, _ = _poison_git_replace_ref_base(tmp_path, world, sha)
    for key, value in poison.items():
        monkeypatch.setenv(key, value)
    result = _read(world, sha, FORGED)
    assert result.failure == fve.FAILURE_QUOTED_TEXT_NOT_IN_ARTIFACT, result


# --------------------------------------------------------------------------- R4-07

def _move_ref_before_the_reflog_read(monkeypatch, world: GitWorld) -> None:
    """Stage the move: the rev-parse stage answers A; the ref is then moved to
    B, so the reflog stage's newest entry names B."""
    real = fve._run_git
    moved = []

    def staged(repo_dir, *args):
        if args[:2] == ("log", "-g") and not moved:
            world.grow_remote(1, push_date="2026-09-21T12:00:00+00:00")
            moved.append(world.remote_tip())
        return real(repo_dir, *args)

    monkeypatch.setattr(fve, "_run_git", staged)


def test_r4_07_a_ref_moved_between_the_stages_dates_nothing(
        tmp_path: Path, monkeypatch) -> None:
    """PRE: the reflog instant of B is recorded as the age of A.  POST: the
    reflog names B, not the resolved A -> ``updated_at`` None, no failure."""
    world, sha = _genuine_world(tmp_path / "w")
    _move_ref_before_the_reflog_read(monkeypatch, world)
    resolution = fve.resolve_remote_ref(world.work)
    assert resolution.resolved_sha == sha
    assert world.remote_tip() != sha
    assert resolution.ref_failure is None and resolution.reflog_failure is None
    assert resolution.updated_at is None


def test_r4_07_read_artifact_facts_moved_between_the_stages_has_no_age(
        tmp_path: Path, monkeypatch) -> None:
    world, sha = _genuine_world(tmp_path / "w")
    _move_ref_before_the_reflog_read(monkeypatch, world)
    result = _read(world, sha, GENUINE)
    assert result.failure is None, result
    assert result.facts.resolved_remote_ref_sha == sha
    assert result.facts.remote_ref_updated_at is None
    assert result.facts.remote_ref_age_seconds is None


def test_r4_07_the_unmoved_ref_is_dated_as_today(tmp_path: Path) -> None:
    """The control: no move -> the reflog instant, exactly as before."""
    world, sha = _genuine_world(tmp_path / "w")
    pushed = datetime.fromisoformat("2026-09-20T12:00:00+00:00")
    resolution = fve.resolve_remote_ref(world.work)
    assert resolution.resolved_sha == sha
    assert resolution.updated_at == pushed
    result = _read(world, sha, GENUINE)
    assert result.facts.remote_ref_updated_at == pushed
    assert result.facts.remote_ref_age_seconds == int((NOW - pushed).total_seconds())
