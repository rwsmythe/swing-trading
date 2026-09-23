"""22-A2 test helper: a throwaway git world for the tier-2 preflight / replay.

``GitWorld`` is a work repo plus a BARE "remote" at ``origin``; pushing
updates ``refs/remotes/origin/main`` (the preflight's ``REMOTE_REF``) and, when
the ref moves, writes a reflog entry whose instant is the pinned committer date
(git stamps reflog entries with the committer ident, ``GIT_COMMITTER_DATE``
honoured).  Every commit carries explicit ``GIT_AUTHOR_DATE`` /
``GIT_COMMITTER_DATE``.  The repo is isolated from the box's git config
(``core.autocrlf`` is forced off locally -- the Windows SYSTEM config sets it
true -- so committed bytes are the bytes written).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

DEFAULT_AUTHOR_DATE = "2026-08-01T12:00:00+00:00"
DEFAULT_PUSH_DATE = "2026-09-20T12:00:00+00:00"


def _env(author_date: str | None = None, committer_date: str | None = None) -> dict[str, str]:
    env = dict(os.environ)
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(key, None)
    env.update({
        "GIT_AUTHOR_NAME": "world", "GIT_AUTHOR_EMAIL": "world@example.invalid",
        "GIT_COMMITTER_NAME": "world", "GIT_COMMITTER_EMAIL": "world@example.invalid",
    })
    if author_date is not None:
        env["GIT_AUTHOR_DATE"] = author_date
    if committer_date is not None:
        env["GIT_COMMITTER_DATE"] = committer_date
    return env


def git(cwd: Path, *args: str, author_date: str | None = None,
        committer_date: str | None = None) -> bytes:
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True,
        env=_env(author_date, committer_date), check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"git {args!r} failed ({proc.returncode}): "
            f"{proc.stderr.decode('utf-8', 'replace')}")
    return proc.stdout


class GitWorld:
    """A work repo at ``root/work`` with (optionally) a bare remote at ``root/remote.git``."""

    def __init__(self, root: Path, *, with_remote: bool = True) -> None:
        self.work = root / "work"
        self.remote = root / "remote.git"
        self.work.mkdir(parents=True)
        git(self.work, "init", "-q", "-b", "main")
        for key, value in (("core.autocrlf", "false"), ("commit.gpgsign", "false"),
                           ("core.hooksPath", os.devnull), ("user.name", "world"),
                           ("user.email", "world@example.invalid")):
            git(self.work, "config", key, value)
        self.with_remote = with_remote
        if with_remote:
            git(root, "init", "-q", "--bare", str(self.remote))
            git(self.work, "remote", "add", "origin", str(self.remote))
        self._n = 0

    def commit(self, rel_path: str, content: bytes, *, author_date: str = DEFAULT_AUTHOR_DATE,
               committer_date: str | None = None, message: str | None = None) -> str:
        """Write ``content`` BYTES to ``rel_path`` and commit; return the full sha."""
        self._n += 1
        target = self.work / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        git(self.work, "add", "--", rel_path)
        git(self.work, "commit", "-q", "-m", message or f"world commit {self._n}",
            author_date=author_date, committer_date=committer_date or author_date)
        return self.head()

    def head(self) -> str:
        return git(self.work, "rev-parse", "HEAD").decode("ascii").strip()

    def remote_tip(self) -> str:
        return git(self.remote, "rev-parse", "main").decode("ascii").strip()

    def push(self, *, push_date: str = DEFAULT_PUSH_DATE, force: bool = False) -> None:
        """Push ``main`` and fetch, so ``refs/remotes/origin/main`` equals the remote tip."""
        args = ["push", "-q"] + (["-f"] if force else []) + ["origin", "main"]
        git(self.work, *args, committer_date=push_date)
        git(self.work, "fetch", "-q", "origin", committer_date=push_date)

    def grow_remote(self, n: int, *, push_date: str = DEFAULT_PUSH_DATE) -> None:
        """Add ``n`` descendant commits and publish them."""
        for i in range(n):
            self.commit(f"growth/{self._n + 1}.txt", f"growth {i}\n".encode("ascii"))
        self.push(push_date=push_date)

    def rewrite_remote_dropping(self, sha: str, *,
                                push_date: str = DEFAULT_PUSH_DATE) -> None:
        """Rewrite published history so ``sha`` is no longer an ancestor of the remote.

        Local ``main`` is reset to ``sha``'s parent, a replacement commit is made,
        and the result is FORCE-pushed and fetched.  The dropped object stays in
        the local object store (readable), but is no longer reachable from
        ``refs/remotes/origin/main``.
        """
        git(self.work, "reset", "-q", "--hard", f"{sha}~1")
        self.commit("rewritten.txt", b"history rewritten\n")
        self.push(push_date=push_date, force=True)
