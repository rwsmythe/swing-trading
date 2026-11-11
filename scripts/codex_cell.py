"""Driver for the Codex implementer lane (stdlib only): turn, commit, review.

The orchestrator runs a Codex implementer cell as `codex exec` PROCESSES in a
git worktree. Ported 2026-11-11 from harness-template 4335ff6 (the Codex-lane
arc, docs/codex-implementer-lane-arc-brief.md); this project's Stage-0 facts
(codex-cli 0.167.1, 2026-11-11) and CHARC's plan-stage rulings are recorded in
~/swing-data/review-transcripts/codex-lane/ (stage0-ledger.md, build-ledger.md).
This script pins the three operations so no seat improvises the flags:

``turn``
    One cell turn. The first turn pipes the staged preamble + brief into
    ``codex exec``; a later turn resumes the session. EVERY turn carries the
    model, effort, the unelevated Windows sandbox mode and the writable roots as
    ``-c`` overrides. ``codex exec resume`` rejects ``-s`` and ``--add-dir``
    (exit 2); it ACCEPTS ``-m`` at 0.167.1, but the driver carries the model as
    ``-c model=...`` on every turn either way. A resume without the overrides
    silently runs on the global config's model, effort and ELEVATED sandbox
    (stage0-ledger, probe 4e).
    The driver appends a required first act to every turn's prompt: print
    ``sandbox-user: `` + ``[Environment]::UserName``. The windows.sandbox mode is
    not in the banner, so this identity line is the only in-turn witness that the
    turn ran unelevated: the turn FAILS (``identity_ok`` false) unless the
    transcript carries the whole line ``sandbox-user: <the driver's user>`` and
    nowhere carries the elevated sandbox's account (``ELEVATED_SANDBOX_USER``). A
    brief that itself quotes that account name fails its turn: fail-safe. This
    source builds the name from two parts, so a turn that prints it does not.
    The transcript and the ``-o`` return file land in the evidence folder; the
    banner assertions (model, effort, sandbox line, session id), the anchored
    ``^ERROR`` lines, the ``tokens used`` footer, the context depth of record
    and the return file's ``FILES CHANGED`` / ``COMMIT`` block are printed as
    one JSON object. The footer is cumulative billing, NOT depth; the depth of
    record is ``last_token_usage.input_tokens`` of the last ``token_count``
    event in the session's ``rollout-*-<session id>.jsonl`` under
    ``$CODEX_HOME/sessions`` (default ``~/.codex/sessions``), printed as
    ``depth_input_tokens`` with ``context_window`` (pinned 2026-10-27).
    The turn exits 0 only when the exit code, the banner pins, the identity
    witness, the footer, a non-empty return file from THIS run and at least one
    ``succeeded in`` line all hold. ``^ERROR`` lines are reported, never a gate:
    a test run inside a tool block prints them (Codex R1-1, CHARC-confirmed).

``commit``
    The sandbox protects ``.git``, so the cell cannot commit. This reads the
    return file's ``FILES CHANGED`` block and ``COMMIT`` subject and commits
    exactly those paths by pathspec with the attribution footer naming the
    model (owner-approved form, 2026-10-27). Each entry must be ONE file inside
    the worktree (``check_files_changed``) that selects no other indexed path
    (``check_index_selection``, Codex R3-1), and a dry run of the add must succeed
    (Codex R4-2); one bad entry stages nothing, and git runs with
    ``--literal-pathspecs`` (Codex R1-2).

``review``
    The Claude reviewer pass for the Codex lane (Reviewer A between turns, run
    by the driver; Reviewer B at the orchestrator's seat): the pre-generated
    diff against the base plus the staged prompt piped into ``claude -p`` with
    a restricted tool policy and JSON output. The policy is NOT read-only in the
    tool sense (``Bash(python:*)`` stays so the reviewer can run the tests); the
    enforcement is the post-check: HEAD, every ref and the status INCLUDING
    ignored files are read before and after, and any difference FAILS the review.
    Writes OUTSIDE the worktree are not caught (CHARC R1-3, A1 amended; a
    filesystem sandbox for ``claude -p`` is banked). Asserts the model from the result's
    ``modelUsage``, a result that is not an error, exactly one verdict token on an
    anchored ``VERDICT: <token>`` line (``review_verdict``), and a clean worktree
    afterwards, read by a status command that itself succeeded (Codex R1-4).

Nothing here names the application; the pinned values are substrate facts.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
from typing import Any

# ---- SEAM (per-project lane and toolchain pins; CHARC rulings of 2026-11-11, build ledger P1) ----
# The Codex lane's model id and effort (explicit: the catalog's default effort for
# gpt-6.1-sol is low), and the attribution footer naming that model.
CODEX_MODEL = "gpt-6.1-sol"
CODEX_EFFORT = "high"
CODEX_FOOTER = "Co-Authored-By: GPT-6.1 Sol via Codex <noreply@openai.com>"
# The lane is the Windows-native CLI; every turn, resume included, carries this mode.
WINDOWS_SANDBOX = "unelevated"
# No extra writable root: the project's tests need only the sandbox defaults
# (workdir, /tmp, $TMPDIR = %TEMP%), stage0-ledger probe 2. --add-dir adds one per turn.
DEFAULT_WRITABLE_ROOTS: tuple[str, ...] = ()
# The cell's test command (PowerShell form; <worktree> is the worktree folder's name).
# The -p plugin widens pytest's 0o700 temp dirs, which the restricted token cannot read;
# the dispatcher's gate never loads it (build ledger, P0).
CELL_TEST_COMMAND = (
    'python -m pytest -p tests.codex_sandbox_tmp --basetemp '
    '"$env:TEMP\\codex-cell-<worktree>-pytest" -m "not slow" -q'
)
# The in-turn identity witness (CHARC D-a).
IDENTITY_PREFIX = "sandbox-user: "
# Built from two parts (CHARC N4): the check is transcript-wide, so a literal here would
# fail any Codex turn that printed this file.
ELEVATED_SANDBOX_USER = "CodexSandbox" + "Offline"

CLAUDE_MODEL = "opus"
CLAUDE_MODEL_PREFIX = "claude-opus"
CLAUDE_EFFORT = "high"
# The reviewer's tool allowance names the PROJECT's runner (the system python here).
# CHARC R1-3 (A1 amended, 2026-11-11): Bash(python:*) stays so the reviewer can run the
# tests, so the allowance is NOT read-only in the tool sense; the enforcement is the
# post-check in cmd_review. git branch is dropped (it mutates); git rev-parse reads refs.
CLAUDE_ALLOWED = (
    "Read,Grep,Glob,Bash(git diff:*),Bash(git log:*),Bash(git show:*),Bash(git status:*),"
    "Bash(git cat-file:*),Bash(git rev-parse:*),Bash(python:*),Bash(grep:*),Bash(ls:*),"
    "Bash(timeout:*)"
)
# The review process writes no .pyc, no pytest cache and no ruff cache, so the tools the
# reviewer runs do not change the ignored files the post-check compares. The writer set is
# CLOSED BY MEASUREMENT (CHARC C1, 20261111T200824Z): each tool the allowance admits was
# run once under this env in a scratch worktree and the C1 manifest diffed; ruff's cache
# was the one writer the first two did not switch off.
REVIEW_ENV = {
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTEST_ADDOPTS": "-p no:cacheprovider",
    "RUFF_NO_CACHE": "true",
}
CLAUDE_DISALLOWED = "Edit,Write,NotebookEdit,Agent,WebFetch,WebSearch"
# Pathspecs left out of the review diff: none (no lock file; the lane writes no proofs folder).
DIFF_EXCLUDES: tuple[str, ...] = ()
# ---- end SEAM ----

# The required first act appended to EVERY turn's prompt (CHARC D-a). It names neither
# the elevated account nor a line that satisfies the witness, so the transcript's echo
# of the prompt can neither fail nor pass the turn by itself.
IDENTITY_ACT = (
    "\n\nREQUIRED FIRST ACT (the driver's identity witness, appended to every turn): "
    "before any other command this turn, run the PowerShell line below verbatim as its "
    "own shell call and leave its output as printed. A turn whose transcript lacks that "
    "output fails.\n\n"
    f'"{IDENTITY_PREFIX}" + [Environment]::UserName\n'
)


def cell_test_command(worktree: str) -> str:
    """The cell's test command for ``worktree`` (its basetemp is named for the folder)."""
    name = pathlib.PurePath(worktree.replace("\\", "/")).name
    return CELL_TEST_COMMAND.replace("<worktree>", name)


def stage_turn_prompt(prompt_path: str, staged_path: pathlib.Path) -> pathlib.Path:
    """Write the turn's stdin: the given prompt's bytes followed by :data:`IDENTITY_ACT`."""
    body = pathlib.Path(prompt_path).read_bytes()
    staged_path.write_bytes(body + IDENTITY_ACT.encode("utf-8"))
    return staged_path


# ----------------------------------------------------------------- parsing --
def parse_banner(transcript: str) -> dict[str, Any]:
    """Extract the banner fields, the anchored ERROR lines and the tokens footer."""

    def field(name: str) -> str | None:
        m = re.search(rf"^{re.escape(name)}:\s*(.+?)\s*$", transcript, flags=re.M)
        return m.group(1) if m else None

    errors = [ln for ln in transcript.splitlines() if ln.startswith("ERROR")]
    tokens = None
    # The CLI's footer is the LAST one, and no exec or codex marker follows it (the CLI then
    # prints the final message again, plain). An earlier footer is a command's output, e.g.
    # a printed transcript fixture, and is no completion evidence (Codex R2-2).
    footers = list(re.finditer(r"^tokens used\s*\n\s*([\d,]+)", transcript, flags=re.M))
    if footers and not re.search(
        r"^(?:exec|codex)\r?$", transcript[footers[-1].end() :], flags=re.M
    ):
        tokens = int(footers[-1].group(1).replace(",", ""))
    return {
        "model": field("model"),
        "effort": field("reasoning effort"),
        "sandbox": field("sandbox"),
        "session_id": field("session id"),
        "error_lines": errors,
        "tokens_used": tokens,
        "succeeded_in": len(re.findall(r"^\s*succeeded in \d", transcript, flags=re.M)),
    }


def identity_witness(transcript: str, user: str) -> dict[str, bool]:
    """The in-turn identity witness (CHARC D-a): did the turn run as ``user``, unelevated?

    ``identity_line_present`` is true when some transcript line is exactly
    ``sandbox-user: <user>`` (CRLF or LF); ``elevated_marker_present`` when the
    elevated sandbox's account name appears ANYWHERE in the transcript. The turn is
    ``identity_ok`` only with the line present and the marker absent; absence of the
    line fails it. The prompt's own act line begins with a quote, so its echo in the
    transcript never satisfies the witness.
    """
    expected = f"{IDENTITY_PREFIX}{user}"
    present = any(ln == expected for ln in transcript.splitlines())
    elevated = ELEVATED_SANDBOX_USER in transcript
    return {
        "identity_line_present": present,
        "elevated_marker_present": elevated,
        "identity_ok": present and not elevated,
    }


def sessions_root() -> pathlib.Path:
    """The Codex sessions folder: ``$CODEX_HOME/sessions`` or ``~/.codex/sessions``."""
    home = os.environ.get("CODEX_HOME")
    base = pathlib.Path(home) if home else pathlib.Path.home() / ".codex"
    return base / "sessions"


def read_depth(session_id: str | None, root: pathlib.Path | None = None) -> dict[str, int | None]:
    """The context depth of record for a session: the last request's input tokens.

    Scans the newest ``rollout-*-<session_id>.jsonl`` under ``root`` (default
    :func:`sessions_root`) for ``token_count`` events and returns
    ``last_token_usage.input_tokens`` and ``model_context_window`` of the last
    one. Both are ``None`` when the session, the file or the event is missing;
    a malformed line is skipped. Reads only; stdlib only.
    """
    out: dict[str, int | None] = {"depth_input_tokens": None, "context_window": None}
    if not session_id:
        return out
    base = root if root is not None else sessions_root()
    if not base.is_dir():
        return out
    files = sorted(base.rglob(f"rollout-*-{session_id}.jsonl"))
    if not files:
        return out
    for line in files[-1].read_text("utf-8", errors="replace").splitlines():
        if '"token_count"' not in line:
            continue
        try:
            info = json.loads(line).get("payload", {}).get("info") or {}
        except (ValueError, AttributeError):
            continue
        last = info.get("last_token_usage") or {}
        if isinstance(last.get("input_tokens"), int):
            out["depth_input_tokens"] = last["input_tokens"]
            out["context_window"] = info.get("model_context_window")
    return out


VERDICT_TOKENS = ("NO_NEW_CRITICAL_MAJOR", "NEW_CRITICAL_MAJOR_FOUND")


def review_verdict(text: str) -> str | None:
    """The Claude review pass's verdict, or None (Codex R1-4 (a); CHARC B1).

    The pass prints an anchored ``VERDICT: <token>`` line. The verdict is the token only
    when exactly ONE distinct token appears on such lines and it is one of
    :data:`VERDICT_TOKENS`; an unknown token, both tokens, or none is no verdict. A line
    may end in CRLF (Codex R4-3).
    """
    found = {
        m.group(1) for m in re.finditer(r"^VERDICT:[ \t]*(\S+)[ \t]*\r?$", text, flags=re.M)
    }
    if len(found) == 1 and found <= set(VERDICT_TOKENS):
        return found.pop()
    return None


def parse_return(text: str) -> dict[str, Any]:
    """Extract the FILES CHANGED paths, the COMMIT subject and VERDICT lines."""
    files: list[str] = []
    m = re.search(r"^FILES CHANGED:\s*\n((?:\s*-\s+.*\n?)+)", text, flags=re.M)
    if m:
        for ln in m.group(1).splitlines():
            ln = ln.strip()
            if ln.startswith("-"):
                path = ln[1:].strip().strip("`")
                if path:
                    files.append(path.replace("\\", "/"))
    c = re.search(r"^COMMIT:\s*(.+?)\s*$", text, flags=re.M)
    return {
        "files_changed": files,
        "commit_subject": c.group(1) if c else None,
        "verdict_lines": re.findall(r"^VERDICT:.*$", text, flags=re.M),
    }


def build_turn_command(
    *,
    worktree: str,
    session_id: str | None,
    return_file: str,
    model: str = CODEX_MODEL,
    effort: str = CODEX_EFFORT,
    writable_roots: tuple[str, ...] = DEFAULT_WRITABLE_ROOTS,
) -> list[str]:
    """The pinned ``codex exec`` (first turn) or ``codex exec resume`` (later) command."""
    roots = json.dumps([r.replace("\\", "/") for r in writable_roots])
    overrides = [
        "-c",
        f'model="{model}"',
        "-c",
        f"model_reasoning_effort={effort}",
        "-c",
        f'windows.sandbox="{WINDOWS_SANDBOX}"',
        "-c",
        f"sandbox_workspace_write.writable_roots={roots}",
    ]
    if session_id:
        return ["codex", "exec", "resume", session_id, *overrides, "-o", return_file, "-"]
    return [
        "codex",
        "exec",
        "-C",
        worktree,
        *overrides,
        "-s",
        "workspace-write",
        "--skip-git-repo-check",
        "-o",
        return_file,
        "-",
    ]


def build_review_command(*, model: str = CLAUDE_MODEL, effort: str = CLAUDE_EFFORT) -> list[str]:
    """The pinned read-only ``claude -p`` reviewer command (stdin = prompt + diff)."""
    return [
        "claude",
        "-p",
        "--model",
        model,
        "--effort",
        effort,
        "--no-session-persistence",
        "--disallowedTools",
        CLAUDE_DISALLOWED,
        "--allowedTools",
        CLAUDE_ALLOWED,
        "--output-format",
        "json",
    ]


# ----------------------------------------------------------------- running --
# A child started from the dispatcher's Claude session must not inherit that session's
# identity or role (Codex R3-2): with these set, a child claude starts as the PARENT's
# session, and the comms hooks register it as the dispatcher's role. The markers are the
# launcher's own list (scripts/start_directors.ps1 $SessionMarkers; a test reads both and
# fails on drift); the roles are what the comms hooks read. Other settings pass through
# (CLAUDE_CODE_GIT_BASH_PATH, which Claude Code needs on Windows, among them).
# The last three are not on the launcher's list (SS-1-1): Claude Code writes them into
# every shell it runs a command in (read from the CLI build of 2026-11-11, 2.1.322). A child
# claude reads the attended flag at startup; codex reads the trace context.
SESSION_MARKERS = (
    "CLAUDE_CODE_CHILD_SESSION",
    "CLAUDE_CODE_SESSION_ID",
    "CLAUDECODE",
    "CLAUDE_PID",
    "CLAUDE_CODE_MESSAGING_SOCKET",
    "CLAUDE_CODE_MESSAGING_TOKEN",
    "CLAUDE_CODE_BRIDGE_SESSION_ID",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_EXECPATH",
    "CLAUDE_EFFORT",
    "NO_COLOR",
    "GIT_EDITOR",
    "CLAUDE_CODE_SESSION_ATTENDED",
    "AI_AGENT",
    "TRACEPARENT",
)
ROLE_VARS = ("HARNESS_ROLE", "SWING_ROLE")


def _run_to_file(
    cmd: list[str],
    stdin_path: str,
    out_path: str,
    cwd: str,
    extra_env: dict[str, str] | None = None,
) -> int:
    # PATH is inherited unchanged (CHARC D-b): no reorder, because System32\bash.exe
    # is the WSL launcher and must not shadow or be shadowed by Git Bash.
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDECODE")}
    for name in (*SESSION_MARKERS, *ROLE_VARS):
        env.pop(name, None)
    env.update(extra_env or {})
    # Resolve the executable (on Windows the npm shim is codex.cmd) and run WITHOUT a shell,
    # so the argv list is passed as is rather than re-parsed by cmd.exe.
    exe = shutil.which(cmd[0]) or cmd[0]
    with open(stdin_path, "rb") as fin, open(out_path, "wb") as fout:
        proc = subprocess.run(
            [exe, *cmd[1:]],
            stdin=fin,
            stdout=fout,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            env=env,
        )
    return proc.returncode


def cmd_turn(args: argparse.Namespace) -> int:
    """Run one cell turn and print the assertions as JSON."""
    # Absolute first (Codex R1-8): the worktree is both the child's cwd and its -C argument,
    # and the child resolves the -o path, so a relative value would resolve twice.
    worktree = str(pathlib.Path(args.worktree).resolve())
    ev = pathlib.Path(args.evidence).resolve()
    ev.mkdir(parents=True, exist_ok=True)
    n = args.turn
    transcript = ev / f"turn-{n}.txt"
    return_file = ev / f"return-{n}.md"
    roots = tuple(args.add_dir) if args.add_dir else DEFAULT_WRITABLE_ROOTS
    cmd = build_turn_command(
        worktree=worktree,
        session_id=args.session,
        return_file=str(return_file),
        model=args.model,
        effort=args.effort,
        writable_roots=roots,
    )
    staged = stage_turn_prompt(args.prompt, ev / f"prompt-{n}.md")
    # The transcript is rewritten by this run; a return file left by an earlier attempt of
    # the same turn is removed too, so a return file present afterwards is THIS run's.
    return_file.unlink(missing_ok=True)
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rc = _run_to_file(cmd, str(staged), str(transcript), worktree)
    text = transcript.read_text("utf-8", errors="replace")
    banner = parse_banner(text)
    identity = identity_witness(text, getpass.getuser())
    depth = read_depth(banner["session_id"] or args.session)
    ret = (
        parse_return(return_file.read_text("utf-8", errors="replace"))
        if return_file.exists()
        else {}
    )
    out = {
        "turn": n,
        "started": started,
        "exit": rc,
        "transcript": str(transcript),
        "return_file": str(return_file) if return_file.exists() else None,
        "model_ok": banner["model"] == args.model,
        "effort_ok": banner["effort"] == args.effort,
        "sandbox_ok": bool(banner["sandbox"] and banner["sandbox"].startswith("workspace-write")),
        # Completion evidence (Codex R1-1): the footer is written at completion, the -o
        # return file is the turn's handoff, and a turn that completed no command is void
        # (docs/codex-reviewer.md assertion 5). Column-0 ERROR lines are NOT a gate here:
        # a test run inside a tool block prints them, so ``error_lines`` is reported for
        # the dispatcher to classify by provenance (assertions 2 and 5).
        "footer_ok": banner["tokens_used"] is not None,
        "return_ok": return_file.exists() and return_file.stat().st_size > 0,
        "executed_ok": banner["succeeded_in"] >= 1,
        **identity,
        **banner,
        **depth,
        **ret,
    }
    print(json.dumps(out))
    ok = (
        rc == 0
        and out["model_ok"]
        and out["effort_ok"]
        and out["sandbox_ok"]
        and out["identity_ok"]
        and out["footer_ok"]
        and out["return_ok"]
        and out["executed_ok"]
    )
    return 0 if ok else 1


def check_files_changed(files: list[str], worktree: str) -> list[str]:
    """Problems with a FILES CHANGED list; empty when every entry is ONE worktree file.

    The entries are model-written text (Codex R1-2). Each must be relative (no drive, no
    leading ``/``), carry no ``..`` or ``.git`` segment and no leading ``:`` (git pathspec
    magic), stay inside the worktree, and not name a directory (which selects a subtree).
    A deleted file passes: it no longer exists, and git stages the deletion. The commit
    also runs git with ``--literal-pathspecs``.
    """
    root = pathlib.Path(worktree).resolve()
    problems: list[str] = []
    for f in files:
        parts = pathlib.PurePosixPath(f).parts
        if not f or f.startswith(("/", ":")) or re.match(r"^[A-Za-z]:", f):
            problems.append(f"{f}: absolute, drive-qualified or pathspec magic")
        elif any(p == ".." for p in parts) or any(p.lower() == ".git" for p in parts):
            problems.append(f"{f}: a '..' or '.git' segment")
        elif (root / f).is_dir():
            problems.append(f"{f}: a directory, not one file")
        elif not (root / f).resolve().is_relative_to(root):
            problems.append(f"{f}: resolves outside the worktree")
    return problems


def check_index_selection(files: list[str], worktree: str) -> list[str]:
    """Problems with what each entry SELECTS in the index (Codex R3-1).

    A deleted directory is no directory on disk, so ``check_files_changed`` passes it, yet
    its name still selects every indexed file under it (a directory prefix, literal
    pathspecs or not). Each entry may select nothing (a new file, which must then exist)
    or exactly itself (a changed or deleted file), never another indexed path.
    """
    root = pathlib.Path(worktree).resolve()
    problems: list[str] = []
    for f in files:
        proc = subprocess.run(
            ["git", "-C", worktree, "--literal-pathspecs", "ls-files", "-z", "--", f],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        selected = [p for p in proc.stdout.split("\0") if p]
        own = pathlib.PurePosixPath(f.replace("\\", "/")).as_posix()
        if proc.returncode != 0:
            problems.append(f"{f}: the index read failed")
        elif any(p != own for p in selected):
            problems.append(f"{f}: selects {len(selected)} indexed path(s), not one file")
        elif not selected and not (root / f).is_file():
            problems.append(f"{f}: neither a file on disk nor an indexed file")
    return problems


def cmd_commit(args: argparse.Namespace) -> int:
    """Commit the turn's FILES CHANGED by literal pathspec with the model's footer."""
    ret = parse_return(pathlib.Path(args.return_file).read_text("utf-8", errors="replace"))
    files = ret["files_changed"]
    subject = args.subject or ret["commit_subject"]
    if not files or not subject:
        print(json.dumps({"error": "no FILES CHANGED block or COMMIT subject", **ret}))
        return 1
    problems = check_files_changed(files, args.worktree) or check_index_selection(
        files, args.worktree
    )
    git = ["git", "-C", args.worktree, "--literal-pathspecs"]
    if not problems:
        # Whatever the add itself would refuse (an ignored file, a path git will not store),
        # refused before staging: git's add refuses AFTER staging the entries beside it
        # (Codex R4-2). A dry run stages nothing.
        dry = subprocess.run(
            [*git, "add", "--dry-run", "--", *files],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if dry.returncode != 0:
            problems = [f"git add --dry-run refused the list: {dry.stderr.strip()}"]
    if problems:
        print(json.dumps({"error": "FILES CHANGED refused; nothing staged", "problems": problems}))
        return 1
    subprocess.run([*git, "add", "--", *files], check=True)
    subprocess.run(
        [*git, "commit", "-q", "-m", subject, "-m", args.footer, "--", *files], check=True
    )
    sha = subprocess.run(
        [*git, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    print(json.dumps({"committed": sha, "files": files, "subject": subject}))
    return 0


def worktree_snapshot(worktree: str) -> dict[str, Any]:
    """HEAD, its branch, every ref and the status INCLUDING ignored files (CHARC R1-3).

    Compared before and after the review pass (``ref_differences`` for the refs, CHARC
    2a; ``ignored_files`` for the C1 manifest): a failing difference, or a read that
    failed (``ok`` false), FAILS the review. Writes OUTSIDE the worktree are not seen.
    """
    reads = {
        "head": ["rev-parse", "HEAD"],
        # The ref HEAD names ("HEAD" itself when detached): this branch's ref for CHARC 2a.
        "branch": ["rev-parse", "--symbolic-full-name", "HEAD"],
        "refs": ["for-each-ref", "--format=%(refname) %(objectname)"],
        "status_ignored": ["status", "--porcelain", "--ignored"],
        # Every ignored file, one per entry, even under a wholly ignored directory.
        "ignored": ["ls-files", "-z", "--others", "--ignored", "--exclude-standard"],
    }
    snap: dict[str, Any] = {"ok": True}
    for name, cmd in reads.items():
        proc = subprocess.run(
            ["git", "-C", worktree, *cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        snap["ok"] = snap["ok"] and proc.returncode == 0
        snap[name] = proc.stdout
    snap["ignored_files"] = ignored_manifest(worktree, snap.pop("ignored"))
    # A listed path whose metadata read failed is a failed read (Codex R3-3).
    snap["ignored_unreadable"] = sorted(k for k, v in snap["ignored_files"].items() if v is None)
    snap["ok"] = snap["ok"] and not snap["ignored_unreadable"]
    return snap


def ignored_manifest(worktree: str, listing: str) -> dict[str, tuple[int, int] | None]:
    """Each ignored file's ``(size, mtime_ns)``; ``None`` for a path that cannot be read.

    ``lstat``, not ``stat``: the entry itself is read, so a dangling link is a reading and
    not a failure.

    CHARC C1 (20261111T200824Z, on Codex R2-1): ``status --ignored`` names an existing
    ignored file, or a wholly ignored directory, once, so it cannot see a rewrite of the
    one or a new file under the other; this manifest can. A write that restores the mtime
    it overwrote is not seen (a DECLARED limitation, docs/codex-reviewer.md delta 10).
    """
    root = pathlib.Path(worktree)
    manifest: dict[str, tuple[int, int] | None] = {}
    for rel in filter(None, listing.split("\0")):
        try:
            st = (root / rel).lstat()
            manifest[rel] = (st.st_size, st.st_mtime_ns)
        except OSError:
            manifest[rel] = None
    return manifest


def ref_differences(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """The refs added, deleted and moved between two snapshots, and whether they FAIL.

    CHARC 2a (2026-11-11): a worktree shares every ref with the main repo, so a ref that
    other seats move mid-review (main, remotes, another worktree's branch) is not the
    reviewer's write. Any ref ADDED or DELETED fails the review; a CHANGED value fails it
    only for this branch's ref, the one HEAD named BEFORE the pass (HEAD itself is
    compared separately). The moved refs are reported either way.
    """

    def table(text: str) -> dict[str, str]:
        pairs = (line.rpartition(" ") for line in text.splitlines() if line.strip())
        return {name: oid for name, _, oid in pairs}

    b, a = table(before["refs"]), table(after["refs"])
    added = sorted(a.keys() - b.keys())
    deleted = sorted(b.keys() - a.keys())
    moved = sorted(k for k in b.keys() & a.keys() if b[k] != a[k])
    own = before["branch"].strip()
    return {
        "refs_added": added,
        "refs_deleted": deleted,
        "refs_moved": moved,
        "fail": bool(added or deleted or own in moved),
    }


def cmd_review(args: argparse.Namespace) -> int:
    """Run the Claude reviewer pass on the worktree's diff against the base."""
    out = pathlib.Path(args.out)
    # CHARC 2c: the review's own files inside the worktree would read as the reviewer's
    # write, so an --out at or under the worktree is refused before anything runs.
    real_out, real_wt = pathlib.Path(args.out).resolve(), pathlib.Path(args.worktree).resolve()
    if real_out.is_relative_to(real_wt):
        print(
            json.dumps(
                {
                    "error": "--out is inside the worktree; put the review's files outside it",
                    "out": str(real_out),
                    "worktree": str(real_wt),
                }
            )
        )
        return 1
    out.mkdir(parents=True, exist_ok=True)
    diff = out / "review-diff.txt"
    with open(diff, "wb") as f:
        subprocess.run(
            [
                "git",
                "-C",
                args.worktree,
                "diff",
                "-U8",
                f"{args.base}..HEAD",
                "--",
                ".",
                *DIFF_EXCLUDES,
            ],
            stdout=f,
            check=True,
        )
    combined = out / "review-input.txt"
    combined.write_bytes(pathlib.Path(args.prompt).read_bytes() + b"\n" + diff.read_bytes())
    result_json = out / "review.json"
    before = worktree_snapshot(args.worktree)
    rc = _run_to_file(
        build_review_command(model=args.model, effort=args.effort),
        str(combined),
        str(result_json),
        args.worktree,
        extra_env=REVIEW_ENV,
    )
    after = worktree_snapshot(args.worktree)
    refs = ref_differences(before, after)
    changed = [k for k in ("head", "branch") if before[k] != after[k]]
    changed += ["refs"] if refs.pop("fail") else []
    changed += ["status_ignored"] if before["status_ignored"] != after["status_ignored"] else []
    # The C1 manifest: a path added, removed, resized or re-timed; failure names the paths.
    b_ign, a_ign, absent = before["ignored_files"], after["ignored_files"], object()
    ignored_changed = sorted(
        k for k in b_ign.keys() | a_ign.keys() if b_ign.get(k, absent) != a_ign.get(k, absent)
    )
    changed += ["ignored_files"] if ignored_changed else []
    summary: dict[str, Any] = {
        "exit": rc,
        "diff": str(diff),
        "json": str(result_json),
        "snapshot_unchanged": before["ok"] and after["ok"] and not changed,
        "snapshot_changed": changed,
        **refs,
        # The full lists (CHARC 2a), so a moved ref is visible even when it does not fail.
        "refs_before": before["refs"].splitlines(),
        "refs_after": after["refs"].splitlines(),
        "ignored_changed": ignored_changed,
        "ignored_unreadable": sorted(
            set(before["ignored_unreadable"]) | set(after["ignored_unreadable"])
        ),
    }
    try:
        data = json.loads(result_json.read_text("utf-8", errors="replace"))
        text = data.get("result", "")
        (out / "review.txt").write_text(text, "utf-8", newline="\n")
        models = list(data.get("modelUsage", {}).keys())
        summary.update(
            {
                "models": models,
                "model_ok": any(m.startswith(CLAUDE_MODEL_PREFIX) for m in models),
                "effort_requested": args.effort,
                "num_turns": data.get("num_turns"),
                "is_error": data.get("is_error"),
                "permission_denials": len(data.get("permission_denials", [])),
                "verdict_lines": re.findall(r"^VERDICT:.*$", text, flags=re.M),
                "verdict": review_verdict(text),
                "review_txt": str(out / "review.txt"),
            }
        )
    except (OSError, ValueError) as exc:
        summary["error"] = f"{type(exc).__name__}: {exc}"
    status = subprocess.run(
        ["git", "-C", args.worktree, "status", "--porcelain"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    # A failed status read (e.g. rc 128) has empty stdout; it is no evidence of a clean
    # tree (Codex R1-4 (c)).
    summary["worktree_clean_after"] = status.returncode == 0 and status.stdout.strip() == ""
    print(json.dumps(summary))
    ok = (
        rc == 0
        and summary.get("model_ok")
        and summary.get("is_error") is False
        and summary["worktree_clean_after"]
        and summary["snapshot_unchanged"]
        and summary.get("verdict") is not None
    )
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    """Command-line entry."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("turn", help="run one Codex cell turn (first or resumed)")
    t.add_argument("--worktree", required=True)
    t.add_argument(
        "--prompt",
        required=True,
        help="staged file piped to stdin (preamble + brief, or the next prompt)",
    )
    t.add_argument("--evidence", required=True, help="folder for turn-N.txt and return-N.md")
    t.add_argument("--turn", type=int, required=True)
    t.add_argument("--session", default=None, help="session id to resume (omit on the first turn)")
    t.add_argument("--model", default=CODEX_MODEL)
    t.add_argument("--effort", default=CODEX_EFFORT)
    t.add_argument("--add-dir", action="append", help="extra writable root (default: none)")
    t.set_defaults(fn=cmd_turn)

    c = sub.add_parser("commit", help="commit a turn's FILES CHANGED by pathspec")
    c.add_argument("--worktree", required=True)
    c.add_argument("--return-file", required=True)
    c.add_argument("--subject", default=None, help="override the COMMIT subject")
    c.add_argument("--footer", default=CODEX_FOOTER)
    c.set_defaults(fn=cmd_commit)

    r = sub.add_parser("review", help="run the Claude reviewer pass on the worktree diff")
    r.add_argument("--worktree", required=True)
    r.add_argument("--base", required=True)
    r.add_argument("--prompt", required=True)
    r.add_argument(
        "--out",
        required=True,
        help="folder for the review's files, OUTSIDE the worktree (a path inside it is refused)",
    )
    r.add_argument("--model", default=CLAUDE_MODEL)
    r.add_argument("--effort", default=CLAUDE_EFFORT)
    r.set_defaults(fn=cmd_review)

    args = ap.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())
