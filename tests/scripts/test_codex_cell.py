"""The Codex implementer-lane driver (scripts/codex_cell.py): pure parts + the turn exit rule.

PORTED 2026-11-11 from harness-template 4335ff6 tests/harness/test_codex_cell.py (the
Codex-lane arc, P1). Edits from the template, each from a CHARC plan-stage ruling of
2026-11-11 (build ledger, codex-lane):

- the SEAM pins for this project (model/effort/footer/reviewer, no default writable root,
  no uv/.venv runner in the reviewer allowance, no diff excludes, the cell test command);
- the resume command: stage 0 found `codex exec resume` ACCEPTS `-m` at 0.167.1, so the
  test pins what matters instead -- every override rides on the resume too, because a resume
  without them falls back to the global model, effort and ELEVATED sandbox (stage0 4e);
- the in-turn identity witness (D-a): the driver appends a required first act to every
  turn's prompt and the turn FAILS unless the transcript carries `sandbox-user: <driver
  user>` and never the elevated sandbox's account (`ELEVATED_SANDBOX_USER`, which this file
  and the driver build from two parts, CHARC N4). The banner cannot see the windows.sandbox
  mode.

No network and no real codex process: `_run_to_file` is replaced by a fake that writes a
canned transcript, and CODEX_HOME points at an empty tmp dir so no real session is read.
"""

from __future__ import annotations

import getpass
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "codex_cell.py"
# The elevated sandbox's account, built from two parts (CHARC N4, 2026-11-11): the witness
# checks the WHOLE transcript, so a lane source file that spelled it would fail any Codex
# turn that printed that file -- a lane that could not work on its own driver.
_ELEVATED = "CodexSandbox" + "Offline"


def _load():
    spec = importlib.util.spec_from_file_location("codex_cell", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["codex_cell"] = mod
    spec.loader.exec_module(mod)
    return mod


BANNER = """OpenAI Codex v0.162.1 (research preview)
--------
workdir: C:\\x\\wt
model: gpt-6.1-sol
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR, C:\\x\\uv]
reasoning effort: high
reasoning summaries: auto
session id: 01a17b87-0f63-7081-a923-5c4cf10f1e02
--------
exec
powershell -Command 'git status --porcelain' in C:\\x\\wt
 succeeded in 258ms:
?? tools/note.md
ERROR codex_core::tools::router: error=exec_command failed
codex
done
tokens used
36,182
"""

RETURN = """Report text.

FILES CHANGED:
- src/pkg/mod.py
- `tests/test_mod.py`
COMMIT: feat(wp9.9): add the thing
VERDICT: TURN_DONE
"""


def _turn_transcript(identity_output: str, *, newline: str = "\n") -> str:
    """A turn transcript in the shape stage 0 recorded (stage0-ledger 4e/4f; P0 turn A).

    The banner carries the DRIVER's pins (gpt-6.1-sol / high / workspace-write), so
    model_ok, effort_ok and sandbox_ok all pass: the only thing that differs between the
    unelevated and the elevated-fallback case is the identity line, which is exactly the
    gap the banner cannot see (stage0-ledger :835). The prompt echo under ``user`` carries
    the witness act line, which begins with a quote and so never satisfies the witness.
    """
    lines = [
        "2026-11-11T17:28:03.441118Z ERROR codex_models_manager::manager: failed to refresh",
        "OpenAI Codex v0.167.1",
        "--------",
        "workdir: C:\\Users\\u\\wt",
        "model: gpt-6.1-sol",
        "provider: openai",
        "approval: never",
        "sandbox: workspace-write [workdir, /tmp, $TMPDIR]",
        "reasoning effort: high",
        "reasoning summaries: none",
        "session id: 01a1cb8d-ac61-7ca3-a024-8e680e0a4dc2",
        "--------",
        "user",
        "Do the task.",
        '"sandbox-user: " + [Environment]::UserName',
        "codex",
        "exec",
        '"C:\\\\Windows\\\\System32\\\\WindowsPowerShell\\\\v1.0\\\\powershell.exe" -Command '
        '"\\"sandbox-user: \\" + [Environment]::UserName" in C:\\Users\\u\\wt',
        " succeeded in 512ms:",
        identity_output,
        "",
        "codex",
        "done",
        "tokens used",
        "9,367",
    ]
    return newline.join(lines) + newline


class BannerParse(unittest.TestCase):
    def setUp(self) -> None:
        self.m = _load()

    def test_fields(self) -> None:
        b = self.m.parse_banner(BANNER)
        self.assertEqual(b["model"], "gpt-6.1-sol")
        self.assertEqual(b["effort"], "high")
        self.assertTrue(b["sandbox"].startswith("workspace-write"))
        self.assertEqual(b["session_id"], "01a17b87-0f63-7081-a923-5c4cf10f1e02")
        self.assertEqual(b["tokens_used"], 36182)
        self.assertEqual(b["succeeded_in"], 1)
        self.assertEqual(len(b["error_lines"]), 1)

    def test_missing_banner_is_none(self) -> None:
        b = self.m.parse_banner("nothing here\n")
        self.assertIsNone(b["model"])
        self.assertIsNone(b["tokens_used"])


class DepthReading(unittest.TestCase):
    """``read_depth``: the figure of record is the LAST request's input tokens, not the footer."""

    SID = "01a17c16-3707-7e30-b81b-ecb9320feb6b"

    def _event(self, ordinal: int, inp: int, total: int) -> str:
        return json.dumps(
            {
                "timestamp": "2026-10-27T09:27:00.708Z",
                "ordinal": ordinal,
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {"input_tokens": total, "total_tokens": total},
                        "last_token_usage": {"input_tokens": inp, "total_tokens": inp + 100},
                        "model_context_window": 475000,
                    },
                },
            }
        )

    def test_last_token_count_event_wins(self) -> None:
        m = _load()
        with tempfile.TemporaryDirectory() as td:
            day = Path(td) / "2026" / "10" / "26"
            day.mkdir(parents=True)
            f = day / f"rollout-2026-10-26T20-39-53-{self.SID}.jsonl"
            lines = [
                json.dumps({"type": "session_meta", "payload": {"id": self.SID}}),
                self._event(5, 279776, 13000000),
                "not json {",
                json.dumps({"type": "event_msg", "payload": {"type": "token_count", "info": None}}),
                self._event(9, 284234, 13712757),
            ]
            f.write_text("\n".join(lines) + "\n", encoding="utf-8")
            d = m.read_depth(self.SID, Path(td))
        self.assertEqual(d["depth_input_tokens"], 284234)
        self.assertEqual(d["context_window"], 475000)

    def test_missing_session_is_none(self) -> None:
        m = _load()
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(
                m.read_depth("no-such-session", Path(td)),
                {"depth_input_tokens": None, "context_window": None},
            )
            self.assertEqual(m.read_depth(None, Path(td))["depth_input_tokens"], None)
        self.assertIsNone(m.read_depth(self.SID, Path(td) / "gone")["depth_input_tokens"])

    def test_sessions_root_honours_codex_home(self) -> None:
        m = _load()
        old = os.environ.get("CODEX_HOME")
        try:
            os.environ["CODEX_HOME"] = str(Path("C:/x/codexhome"))
            self.assertEqual(m.sessions_root(), Path("C:/x/codexhome") / "sessions")
        finally:
            if old is None:
                del os.environ["CODEX_HOME"]
            else:
                os.environ["CODEX_HOME"] = old


class ReturnParse(unittest.TestCase):
    def setUp(self) -> None:
        self.m = _load()

    def test_files_and_subject(self) -> None:
        r = self.m.parse_return(RETURN)
        self.assertEqual(r["files_changed"], ["src/pkg/mod.py", "tests/test_mod.py"])
        self.assertEqual(r["commit_subject"], "feat(wp9.9): add the thing")
        self.assertEqual(r["verdict_lines"], ["VERDICT: TURN_DONE"])

    def test_no_block(self) -> None:
        r = self.m.parse_return("no block\n")
        self.assertEqual(r["files_changed"], [])
        self.assertIsNone(r["commit_subject"])


class SeamPins(unittest.TestCase):
    """The SEAM block, as CHARC ruled it for this project (build ledger, P1)."""

    def setUp(self) -> None:
        self.m = _load()

    def test_lane_pins(self) -> None:
        self.assertEqual(self.m.CODEX_MODEL, "gpt-6.1-sol")
        self.assertEqual(self.m.CODEX_EFFORT, "high")
        self.assertEqual(
            self.m.CODEX_FOOTER, "Co-Authored-By: GPT-6.1 Sol via Codex <noreply@openai.com>"
        )
        self.assertEqual(self.m.WINDOWS_SANDBOX, "unelevated")
        self.assertEqual(self.m.DEFAULT_WRITABLE_ROOTS, ())

    def test_reviewer_pins(self) -> None:
        self.assertEqual(self.m.CLAUDE_MODEL, "opus")
        self.assertEqual(self.m.CLAUDE_EFFORT, "high")
        self.assertIn("Bash(python:*)", self.m.CLAUDE_ALLOWED)
        self.assertNotIn("uv run", self.m.CLAUDE_ALLOWED)
        self.assertNotIn(".venv", self.m.CLAUDE_ALLOWED)
        self.assertEqual(self.m.DIFF_EXCLUDES, ())

    def test_cell_test_command(self) -> None:
        cmd = self.m.cell_test_command("C:/Users/u/swing-trading/.worktrees/codex-lane")
        self.assertEqual(
            cmd,
            'python -m pytest -p tests.codex_sandbox_tmp --basetemp '
            '"$env:TEMP\\codex-cell-codex-lane-pytest" -m "not slow" -q',
        )
        self.assertNotIn("no:randomly", self.m.CELL_TEST_COMMAND)


class Commands(unittest.TestCase):
    def setUp(self) -> None:
        self.m = _load()

    def test_first_turn_carries_every_override(self) -> None:
        cmd = self.m.build_turn_command(
            worktree="C:/x/wt", session_id=None, return_file="r.md", writable_roots=("C:\\x\\uv",)
        )
        joined = " ".join(cmd)
        self.assertIn('model="gpt-6.1-sol"', joined)
        self.assertIn("model_reasoning_effort=high", joined)
        self.assertIn('windows.sandbox="unelevated"', joined)
        self.assertIn('sandbox_workspace_write.writable_roots=["C:/x/uv"]', joined)
        self.assertIn("workspace-write", cmd)
        self.assertEqual(cmd[:2], ["codex", "exec"])
        self.assertEqual(cmd[-1], "-")

    def test_default_writable_roots_are_none_beyond_the_sandbox_defaults(self) -> None:
        cmd = self.m.build_turn_command(worktree="C:/x/wt", session_id=None, return_file="r.md")
        self.assertIn("sandbox_workspace_write.writable_roots=[]", " ".join(cmd))

    def test_resume_turn_carries_every_override(self) -> None:
        """Resume rejects -s/--add-dir (exit 2) and drops model, effort, roots and the
        windows.sandbox mode unless each is re-passed (stage0-ledger, the resume table)."""
        cmd = self.m.build_turn_command(worktree="C:/x/wt", session_id="abc", return_file="r.md")
        self.assertEqual(cmd[:4], ["codex", "exec", "resume", "abc"])
        self.assertNotIn("-s", cmd)
        self.assertNotIn("--add-dir", cmd)
        joined = " ".join(cmd)
        self.assertIn('model="gpt-6.1-sol"', joined)
        self.assertIn("model_reasoning_effort=high", joined)
        self.assertIn('windows.sandbox="unelevated"', joined)
        self.assertIn("sandbox_workspace_write.writable_roots=[]", joined)

    def test_review_is_read_only(self) -> None:
        cmd = self.m.build_review_command()
        joined = " ".join(cmd)
        self.assertNotIn("--bare", cmd)
        self.assertIn("--output-format", cmd)
        self.assertIn("Edit,Write", joined)
        self.assertIn("Bash(git diff:*)", joined)
        self.assertIn("--effort", cmd)


# ------------------------------------------------------- the identity witness (D-a) --
ELEVATED_FALLBACK_4E = _turn_transcript("sandbox-user: " + _ELEVATED)


def test_identity_witness_accepts_the_unelevated_user() -> None:
    m = _load()
    w = m.identity_witness(_turn_transcript("sandbox-user: rwsmy"), "rwsmy")
    assert w["identity_ok"] is True
    assert w["identity_line_present"] is True
    assert w["elevated_marker_present"] is False


def test_identity_witness_accepts_crlf_transcripts() -> None:
    m = _load()
    text = _turn_transcript("sandbox-user: rwsmy", newline="\r\n")
    assert m.identity_witness(text, "rwsmy")["identity_ok"] is True


def test_identity_witness_refuses_the_4e_elevated_fallback() -> None:
    m = _load()
    w = m.identity_witness(ELEVATED_FALLBACK_4E, "rwsmy")
    assert w["identity_ok"] is False
    assert w["identity_line_present"] is False
    assert w["elevated_marker_present"] is True


def test_identity_witness_absence_of_the_line_fails() -> None:
    m = _load()
    w = m.identity_witness(_turn_transcript("nothing printed"), "rwsmy")
    assert w["identity_ok"] is False
    assert w["identity_line_present"] is False
    assert w["elevated_marker_present"] is False


def test_identity_witness_a_right_line_beside_the_marker_still_fails() -> None:
    m = _load()
    text = _turn_transcript("sandbox-user: rwsmy") + f"note: {_ELEVATED}\n"
    w = m.identity_witness(text, "rwsmy")
    assert w["identity_line_present"] is True
    assert w["identity_ok"] is False


def test_identity_witness_needs_the_whole_line() -> None:
    m = _load()
    for out in ("sandbox-user: rwsmy2", "  sandbox-user: rwsmy", "xsandbox-user: rwsmy"):
        assert m.identity_witness(_turn_transcript(out), "rwsmy")["identity_ok"] is False, out


def test_no_lane_source_spells_the_elevated_account() -> None:
    """CHARC N4: the driver and this test file build the elevated account's name from two
    parts, so a Codex turn that prints either file does not fail its own witness. The
    driver's constant still equals the whole name, so the transcript check is unchanged."""
    m = _load()
    assert m.ELEVATED_SANDBOX_USER == _ELEVATED
    for path in (SCRIPT, Path(__file__)):
        assert _ELEVATED not in path.read_text(encoding="utf-8"), path


def _run_turn(
    m,
    tmp_path,
    monkeypatch,
    capsys,
    transcript: str,
    session: str | None = None,
    return_text: str | None = RETURN,
):
    """Drive ``cmd_turn`` through ``main`` with a fake runner; return (exit, json, stdin).

    The fake writes the transcript and, unless ``return_text`` is None, the ``-o`` return
    file, as a completed codex turn does."""
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codexhome"))
    prompt = tmp_path / "brief.md"
    prompt.write_bytes(b"Do the task.\n")
    seen: dict[str, bytes] = {}

    def fake_run(cmd, stdin_path, out_path, cwd):
        seen["stdin"] = Path(stdin_path).read_bytes()
        seen["cmd"] = cmd
        seen["cwd"] = cwd
        Path(out_path).write_bytes(transcript.encode("utf-8"))
        if return_text is not None:
            Path(cmd[cmd.index("-o") + 1]).write_text(return_text, encoding="utf-8")
        return 0

    monkeypatch.setattr(m, "_run_to_file", fake_run)
    argv = [
        "turn",
        "--worktree",
        str(tmp_path),
        "--prompt",
        str(prompt),
        "--evidence",
        str(tmp_path / "ev"),
        "--turn",
        "1",
    ]
    if session:
        argv += ["--session", session]
    rc = m.main(argv)
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    return rc, out, seen


def test_turn_fails_on_the_4e_elevated_fallback(tmp_path, monkeypatch, capsys) -> None:
    """RED first against the template driver: its banner checks all pass on this
    transcript (the pins are in the banner), so it exits 0 on an elevated turn."""
    m = _load()
    rc, out, _ = _run_turn(m, tmp_path, monkeypatch, capsys, ELEVATED_FALLBACK_4E)
    assert out["model_ok"] and out["effort_ok"] and out["sandbox_ok"]
    assert rc == 1, "an elevated-fallback turn must fail the exit rule"
    assert out["identity_ok"] is False


def test_turn_passes_on_the_unelevated_identity(tmp_path, monkeypatch, capsys) -> None:
    m = _load()
    me = getpass.getuser()
    text = _turn_transcript(f"sandbox-user: {me}")
    rc, out, _ = _run_turn(m, tmp_path, monkeypatch, capsys, text)
    assert out["identity_ok"] is True
    assert rc == 0


# ------------------------------------------- the commit's FILES CHANGED gate (R1-2) --
def _commit(m, tmp_path, monkeypatch, capsys, entries: list[str]):
    """Run ``commit`` on a return file listing ``entries``; git calls are recorded, not run
    (no real git, so the test stays outside the sandbox's git-family residue)."""
    wt = tmp_path / "wt"
    (wt / "sub").mkdir(parents=True)
    ret = tmp_path / "return-1.md"
    block = "".join(f"- {e}\n" for e in entries)
    ret.write_text(f"Done.\n\nFILES CHANGED:\n{block}COMMIT: feat(x): y\n", encoding="utf-8")
    calls: list[list[str]] = []

    class _Done:
        stdout = "abc1234\n"
        returncode = 0

    def fake_run(cmd, *a, **k):
        calls.append(list(cmd))
        return _Done()

    monkeypatch.setattr(m.subprocess, "run", fake_run)
    rc = m.main(["commit", "--worktree", str(wt), "--return-file", str(ret)])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    return rc, out, calls


@pytest.mark.parametrize(
    "bad",
    [
        ":(glob)**",
        ":!src",
        "sub",
        "../outside.txt",
        "a/../../outside.txt",
        "C:/Users/x/file.py",
        "/etc/passwd",
        ".git/config",
        "pkg/.GIT/hooks/pre-commit",
    ],
)
def test_commit_refuses_an_entry_that_is_not_one_worktree_file(
    tmp_path, monkeypatch, capsys, bad
) -> None:
    """Codex R1-2: an entry is model-written text. Pathspec magic, a directory, a path
    outside the worktree or into .git would commit files the turn never reported. The WHOLE
    list is checked before anything is staged, so a good entry beside it stages nothing."""
    m = _load()
    rc, out, calls = _commit(m, tmp_path, monkeypatch, capsys, ["src/ok.py", bad])
    assert rc == 1
    assert calls == []
    assert out["problems"] and bad in out["problems"][0]


def test_commit_stages_and_commits_with_literal_pathspecs(tmp_path, monkeypatch, capsys):
    m = _load()
    rc, out, calls = _commit(m, tmp_path, monkeypatch, capsys, ["src/ok.py", "tests/t.py"])
    assert rc == 0
    assert out["files"] == ["src/ok.py", "tests/t.py"]
    add, commit = calls[0], calls[1]
    for c in (add, commit):
        assert c[:4] == ["git", "-C", str(tmp_path / "wt"), "--literal-pathspecs"]
        assert c[-3:] == ["--", "src/ok.py", "tests/t.py"]
    assert add[4] == "add" and commit[4] == "commit"
    assert m.CODEX_FOOTER in commit


def test_turn_resolves_relative_worktree_and_evidence_paths(tmp_path, monkeypatch, capsys):
    """Codex R1-8: the worktree is both the child's cwd and its ``-C`` argument, and the
    ``-o`` path is resolved by the child. A relative value resolved twice
    (``wt/wt``) and the return file landed under the child's cwd."""
    m = _load()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codexhome"))
    (tmp_path / "wt").mkdir()
    (tmp_path / "brief.md").write_bytes(b"Do the task.\n")
    seen: dict = {}

    def fake_run(cmd, stdin_path, out_path, cwd):
        seen["cmd"], seen["cwd"] = cmd, cwd
        Path(out_path).write_text(_turn_transcript("x"), encoding="utf-8")
        return 0

    monkeypatch.setattr(m, "_run_to_file", fake_run)
    m.main(["turn", "--worktree", "wt", "--prompt", "brief.md", "--evidence", "ev", "--turn", "1"])
    capsys.readouterr()
    cmd = seen["cmd"]
    assert cmd[cmd.index("-C") + 1] == str(tmp_path / "wt")
    assert seen["cwd"] == str(tmp_path / "wt")
    assert cmd[cmd.index("-o") + 1] == str(tmp_path / "ev" / "return-1.md")


# ---------------------------------------- completion evidence in the exit rule (R1-1) --
def test_turn_aborted_after_the_witness_fails(tmp_path, monkeypatch, capsys) -> None:
    """Codex R1-1: banner and identity right, then an abort -- no footer. The footer is
    the line written at completion, so its absence fails the turn whatever else passed."""
    m = _load()
    me = getpass.getuser()
    text = _turn_transcript(f"sandbox-user: {me}").replace(
        "tokens used\n9,367\n", "ERROR: aborted after witness\n"
    )
    assert "tokens used" not in text
    rc, out, _ = _run_turn(m, tmp_path, monkeypatch, capsys, text)
    assert out["identity_ok"] and out["model_ok"] and out["effort_ok"] and out["sandbox_ok"]
    assert out["footer_ok"] is False
    assert rc == 1


def test_turn_without_a_return_file_from_this_run_fails(tmp_path, monkeypatch, capsys) -> None:
    """Codex R1-1: the -o return file is the turn's handoff. A turn that wrote none fails,
    and a return-N.md left by an earlier attempt of the same turn is not this run's."""
    m = _load()
    me = getpass.getuser()
    stale = tmp_path / "ev" / "return-1.md"
    stale.parent.mkdir(parents=True)
    stale.write_text(RETURN, encoding="utf-8")
    text = _turn_transcript(f"sandbox-user: {me}")
    rc, out, _ = _run_turn(m, tmp_path, monkeypatch, capsys, text, return_text=None)
    assert out["footer_ok"] is True
    assert out["return_ok"] is False
    assert rc == 1


def test_turn_with_an_empty_return_file_fails(tmp_path, monkeypatch, capsys) -> None:
    m = _load()
    me = getpass.getuser()
    text = _turn_transcript(f"sandbox-user: {me}")
    rc, out, _ = _run_turn(m, tmp_path, monkeypatch, capsys, text, return_text="")
    assert out["return_ok"] is False
    assert rc == 1


def test_turn_in_which_no_command_succeeded_fails(tmp_path, monkeypatch, capsys) -> None:
    """The positive control (docs/codex-reviewer.md assertion 5): a turn that completed no
    command is void, even when its transcript carries a right identity line."""
    m = _load()
    me = getpass.getuser()
    text = _turn_transcript(f"sandbox-user: {me}").replace(" succeeded in 512ms:\n", "")
    assert "succeeded in" not in text
    rc, out, _ = _run_turn(m, tmp_path, monkeypatch, capsys, text)
    assert out["identity_ok"] is True
    assert out["executed_ok"] is False
    assert rc == 1


def test_a_column_zero_error_line_alone_does_not_fail_a_turn(tmp_path, monkeypatch, capsys):
    """The DECLINED half of R1-1, pinned: a test run inside a tool block prints line-initial
    ERROR lines, so the token alone does not fail the turn (docs/codex-reviewer.md
    assertions 2 and 5); the lines are reported in ``error_lines`` for the dispatcher."""
    m = _load()
    me = getpass.getuser()
    text = _turn_transcript(f"sandbox-user: {me}").replace(
        "\ncodex\ndone\n", "\nERROR tests/test_x.py::test_y - boom\ncodex\ndone\n"
    )
    rc, out, _ = _run_turn(m, tmp_path, monkeypatch, capsys, text)
    assert out["error_lines"] == ["ERROR tests/test_x.py::test_y - boom"]
    assert rc == 0


@pytest.mark.parametrize("session", [None, "01a1cb8d-ac61-7ca3-a024-8e680e0a4dc2"])
def test_every_turn_prompt_carries_the_witness_act(tmp_path, monkeypatch, capsys, session) -> None:
    """First turn and resume alike: the piped stdin is the prompt plus the required first
    act. The appended text names neither the elevated marker nor a satisfying line, so the
    transcript's echo of the prompt can neither fail nor pass the witness by itself."""
    m = _load()
    me = getpass.getuser()
    _, _, seen = _run_turn(
        m, tmp_path, monkeypatch, capsys, _turn_transcript(f"sandbox-user: {me}"), session
    )
    stdin = seen["stdin"].decode("utf-8")
    assert stdin.startswith("Do the task.\n")
    assert '"sandbox-user: " + [Environment]::UserName' in stdin
    assert _ELEVATED not in stdin
    assert m.identity_witness(stdin, me)["identity_line_present"] is False
    assert ("resume" in seen["cmd"]) is bool(session)


# ------------------------------------------------- the review pass's exit (R1-4, R1-3) --
OPUS_USAGE = {"claude-opus-4-7": {"inputTokens": 10}}


def _review(m, tmp_path, monkeypatch, capsys, result: dict, git: dict | None = None,
            after: dict | None = None, real_run: bool = False, out: str | None = None):
    """Drive ``cmd_review`` with no real git and no real claude.

    ``git`` maps a git read (``status``, ``status --ignored``, ``rev-parse``,
    ``rev-parse --symbolic-full-name``, ``for-each-ref``) to ``(returncode, stdout)``;
    ``after`` overrides those answers once the reviewer has run, which is how a write by the
    reviewer is simulated. ``real_run`` keeps the driver's own ``_run_to_file``, so the
    claude process (faked at ``subprocess.run``) receives the env the driver builds. ``out``
    replaces the default ``--out`` (``<tmp>/out``, outside the worktree)."""
    wt = tmp_path / "wt"
    wt.mkdir(exist_ok=True)
    prompt = tmp_path / "p.md"
    prompt.write_text("Review.\n", encoding="utf-8")
    answers = {
        "status": (0, ""),
        "status --ignored": (0, "!! .pytest_cache/\n"),
        "rev-parse": (0, "abc1234\n"),
        "rev-parse --symbolic-full-name": (0, "refs/heads/lane\n"),
        "for-each-ref": (0, "refs/heads/lane abc1234\n"),
    }
    answers.update(git or {})
    state = {"ran": False}
    seen: dict = {}

    class _P:
        def __init__(self, rc: int, out: str) -> None:
            self.returncode, self.stdout = rc, out

    def fake_git(cmd, *a, **k):
        if cmd[0] != "git":  # the claude process, reached only with real_run
            state["ran"] = True
            seen["cmd"], seen["env"] = cmd, k["env"]
            k["stdout"].write(json.dumps(result).encode("utf-8"))
            return _P(0, "")
        sub = cmd[3]
        if sub == "diff":
            k["stdout"].write(b"diff --git a/x b/x\n")
            return _P(0, "")
        key = sub
        if sub == "status" and "--ignored" in cmd:
            key = "status --ignored"
        elif sub == "rev-parse" and "--symbolic-full-name" in cmd:
            key = "rev-parse --symbolic-full-name"
        table = {**answers, **(after or {})} if state["ran"] else answers
        return _P(*table[key])

    def fake_claude(cmd, stdin_path, out_path, cwd, extra_env=None):
        state["ran"] = True
        seen["cmd"], seen["env"] = cmd, extra_env
        Path(out_path).write_text(json.dumps(result), encoding="utf-8")
        return 0

    monkeypatch.setattr(m.subprocess, "run", fake_git)
    if real_run:
        monkeypatch.setattr(m.shutil, "which", lambda name: None)
    else:
        monkeypatch.setattr(m, "_run_to_file", fake_claude)
    argv = ["review", "--worktree", str(wt), "--base", "abc", "--prompt", str(prompt),
            "--out", out if out is not None else str(tmp_path / "out")]
    rc = m.main(argv)
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    return rc, out, seen


def _result(text: str, *, is_error: bool = False) -> dict:
    return {"result": text, "is_error": is_error, "modelUsage": OPUS_USAGE, "num_turns": 3,
            "permission_denials": []}


@pytest.mark.parametrize("token", ["NO_NEW_CRITICAL_MAJOR", "NEW_CRITICAL_MAJOR_FOUND"])
def test_review_with_one_verdict_token_exits_0(tmp_path, monkeypatch, capsys, token) -> None:
    """Exit 0 means the review COMPLETED with a readable verdict; the verdict itself is
    printed for the dispatcher (a findings-found review is a completed review)."""
    m = _load()
    rc, out, _ = _review(m, tmp_path, monkeypatch, capsys, _result(f"Notes.\nVERDICT: {token}\n"))
    assert out["verdict"] == token
    assert rc == 0


@pytest.mark.parametrize(
    "text",
    [
        "VERDICT: INCONCLUSIVE\n",
        "VERDICT: NO_NEW_CRITICAL_MAJOR\nVERDICT: NEW_CRITICAL_MAJOR_FOUND\n",
        "VERDICT: NO_NEW_CRITICAL_MAJOR\nVERDICT: INCONCLUSIVE\n",
        "VERDICT: NO_NEW_CRITICAL_MAJOR_PENDING\n",
        "no verdict at all\n",
    ],
)
def test_review_without_exactly_one_known_verdict_fails(tmp_path, monkeypatch, capsys, text):
    """Codex R1-4 (a): any ``VERDICT:`` line used to pass. Only exactly one distinct token
    of the two, on an anchored ``VERDICT: <token>`` line (CHARC B1), is a verdict."""
    m = _load()
    rc, out, _ = _review(m, tmp_path, monkeypatch, capsys, _result(text))
    assert out["verdict"] is None
    assert rc == 1


def test_review_whose_result_is_an_error_fails(tmp_path, monkeypatch, capsys) -> None:
    """Codex R1-4 (c): ``is_error: true`` with exit 0 used to pass."""
    m = _load()
    text = "VERDICT: NO_NEW_CRITICAL_MAJOR\n"
    rc, out, _ = _review(m, tmp_path, monkeypatch, capsys, _result(text, is_error=True))
    assert out["is_error"] is True
    assert rc == 1


def test_review_with_a_failed_status_read_fails(tmp_path, monkeypatch, capsys) -> None:
    """Codex R1-4 (c): a failed ``git status`` (rc 128, empty stdout) read as a clean tree."""
    m = _load()
    rc, out, _ = _review(
        m, tmp_path, monkeypatch, capsys, _result("VERDICT: NO_NEW_CRITICAL_MAJOR\n"),
        after={"status": (128, "")},
    )
    assert out["worktree_clean_after"] is False
    assert rc == 1


def test_reviewer_allowance_reads_refs_with_rev_parse_never_git_branch() -> None:
    """CHARC R1-3 (A1 amended): ``git branch`` mutates and the reviewer has no need of it;
    ``git rev-parse`` reads the branch and HEAD. ``Bash(python:*)`` stays (the reviewer
    runs the project's tests; the post-check is the enforcement)."""
    m = _load()
    assert "Bash(git branch" not in m.CLAUDE_ALLOWED
    assert "Bash(git rev-parse:*)" in m.CLAUDE_ALLOWED
    assert "Bash(python:*)" in m.CLAUDE_ALLOWED


@pytest.mark.parametrize(
    ("read", "changed"),
    [
        ("rev-parse", (0, "def5678\n")),
        ("for-each-ref", (0, "refs/heads/lane abc1234\nrefs/heads/made abc1234\n")),
        ("status --ignored", (0, "!! .pytest_cache/\n!! notes.txt\n")),
    ],
)
def test_review_fails_when_the_worktree_snapshot_changed(
    tmp_path, monkeypatch, capsys, read, changed
) -> None:
    """CHARC R1-3 (A1 amended): HEAD, every ref and the status INCLUDING ignored files are
    read before and after the pass; any difference FAILS the review. A plain ``status``
    stays clean in every case here, so only the snapshot can catch these writes."""
    m = _load()
    rc, out, _ = _review(
        m, tmp_path, monkeypatch, capsys, _result("VERDICT: NO_NEW_CRITICAL_MAJOR\n"),
        after={read: changed},
    )
    assert out["worktree_clean_after"] is True
    assert out["snapshot_unchanged"] is False
    names = {"rev-parse": "head", "for-each-ref": "refs", "status --ignored": "status_ignored"}
    assert out["snapshot_changed"] == [names[read]]
    assert rc == 1


def test_review_fails_when_a_snapshot_read_fails(tmp_path, monkeypatch, capsys) -> None:
    m = _load()
    rc, out, _ = _review(
        m, tmp_path, monkeypatch, capsys, _result("VERDICT: NO_NEW_CRITICAL_MAJOR\n"),
        git={"for-each-ref": (128, "")},
    )
    assert out["snapshot_unchanged"] is False
    assert rc == 1


def test_review_with_an_unchanged_snapshot_passes(tmp_path, monkeypatch, capsys) -> None:
    m = _load()
    rc, out, _ = _review(
        m, tmp_path, monkeypatch, capsys, _result("VERDICT: NO_NEW_CRITICAL_MAJOR\n")
    )
    assert out["snapshot_unchanged"] is True
    assert out["snapshot_changed"] == []
    assert rc == 0


# CHARC 2a (2026-11-11T19:36:51Z): a worktree shares every ref with the main repo, so the
# ref comparison is narrowed. An ADDED or DELETED ref fails the review; a CHANGED value
# fails it only for this branch's ref (and HEAD); every ref list is recorded.
SHARED_REFS = (
    "refs/heads/lane abc1234\nrefs/heads/main 1111111\n"
    "refs/heads/other-wt 3333333\nrefs/remotes/origin/main 1111111\n"
)
SHARED_REFS_MOVED = (
    "refs/heads/lane abc1234\nrefs/heads/main 2222222\n"
    "refs/heads/other-wt 4444444\nrefs/remotes/origin/main 2222222\n"
)


def test_review_passes_when_only_refs_other_than_its_branch_moved(
    tmp_path, monkeypatch, capsys
) -> None:
    """CHARC 2a: main, a remote-tracking ref and another worktree's branch moving mid-review
    are not the reviewer's writes and do not fail it; the moved refs are still reported."""
    m = _load()
    rc, out, _ = _review(
        m, tmp_path, monkeypatch, capsys, _result("VERDICT: NO_NEW_CRITICAL_MAJOR\n"),
        git={"for-each-ref": (0, SHARED_REFS)}, after={"for-each-ref": (0, SHARED_REFS_MOVED)},
    )
    assert out["snapshot_changed"] == []
    assert out["snapshot_unchanged"] is True
    assert out["refs_moved"] == [
        "refs/heads/main", "refs/heads/other-wt", "refs/remotes/origin/main"
    ]
    assert out["refs_added"] == [] and out["refs_deleted"] == []
    assert rc == 0


@pytest.mark.parametrize(
    ("after_refs", "field", "ref"),
    [
        (SHARED_REFS + "refs/heads/made abc1234\n", "refs_added", "refs/heads/made"),
        (SHARED_REFS.replace("refs/heads/other-wt 3333333\n", ""), "refs_deleted",
         "refs/heads/other-wt"),
        (SHARED_REFS.replace("refs/heads/lane abc1234", "refs/heads/lane def5678"), "refs_moved",
         "refs/heads/lane"),
    ],
    ids=["added", "deleted", "own-branch-moved"],
)
def test_review_fails_on_an_added_or_deleted_ref_or_its_own_branch_moving(
    tmp_path, monkeypatch, capsys, after_refs, field, ref
) -> None:
    """CHARC 2a: any ref ADDED or DELETED fails the review, and so does a changed value for
    this branch's own ref (``refs/heads/lane``, read from the symbolic HEAD before the pass)."""
    m = _load()
    rc, out, _ = _review(
        m, tmp_path, monkeypatch, capsys, _result("VERDICT: NO_NEW_CRITICAL_MAJOR\n"),
        git={"for-each-ref": (0, SHARED_REFS)}, after={"for-each-ref": (0, after_refs)},
    )
    assert out[field] == [ref]
    assert out["snapshot_changed"] == ["refs"]
    assert out["snapshot_unchanged"] is False
    assert rc == 1


def test_review_fails_when_head_points_at_another_branch(tmp_path, monkeypatch, capsys) -> None:
    """CHARC 2a keeps HEAD failing on any change: HEAD switched to another branch at the same
    commit leaves ``rev-parse HEAD`` and every ref value as they were."""
    m = _load()
    rc, out, _ = _review(
        m, tmp_path, monkeypatch, capsys, _result("VERDICT: NO_NEW_CRITICAL_MAJOR\n"),
        after={"rev-parse --symbolic-full-name": (0, "refs/heads/other\n")},
    )
    assert out["snapshot_changed"] == ["branch"]
    assert rc == 1


def test_review_records_the_full_ref_lists_before_and_after(
    tmp_path, monkeypatch, capsys
) -> None:
    """CHARC 2a: the full before/after ref lists are in the review's JSON, so a moved ref is
    visible even when it does not fail the review."""
    m = _load()
    _, out, _ = _review(
        m, tmp_path, monkeypatch, capsys, _result("VERDICT: NO_NEW_CRITICAL_MAJOR\n"),
        git={"for-each-ref": (0, SHARED_REFS)}, after={"for-each-ref": (0, SHARED_REFS_MOVED)},
    )
    assert out["refs_before"] == SHARED_REFS.splitlines()
    assert out["refs_after"] == SHARED_REFS_MOVED.splitlines()


def test_review_runs_tests_without_writing_bytecode_or_a_pytest_cache(
    tmp_path, monkeypatch, capsys
) -> None:
    """The reviewer keeps ``Bash(python:*)`` to run the tests, and the snapshot reads
    ignored files, so the pass runs with no .pyc writes and no pytest cache: a test run
    must not trip the check that exists to catch a write."""
    m = _load()
    _, _, seen = _review(
        m, tmp_path, monkeypatch, capsys, _result("VERDICT: NO_NEW_CRITICAL_MAJOR\n")
    )
    assert seen["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert "-p no:cacheprovider" in seen["env"]["PYTEST_ADDOPTS"]


def test_the_review_process_env_carries_both_settings(tmp_path, monkeypatch, capsys) -> None:
    """CHARC 2b (2026-11-11T19:36:51Z): the claude process the review command starts runs
    with PYTHONDONTWRITEBYTECODE=1 and PYTEST_ADDOPTS=-p no:cacheprovider. Read at the
    process boundary (the driver's own ``_run_to_file``), over inherited values that
    disagree, so the settings are the driver's and not the test runner's."""
    m = _load()
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "")
    monkeypatch.setenv("PYTEST_ADDOPTS", "-x")
    rc, _, seen = _review(
        m, tmp_path, monkeypatch, capsys, _result("VERDICT: NO_NEW_CRITICAL_MAJOR\n"),
        real_run=True,
    )
    assert seen["cmd"][:2] == ["claude", "-p"]
    assert seen["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert seen["env"]["PYTEST_ADDOPTS"] == "-p no:cacheprovider"
    assert rc == 0


# CHARC 2c (2026-11-11T19:36:51Z): the review's own files inside the worktree would read as
# the reviewer's write, so --out inside the worktree is refused (one realpath comparison).
@pytest.mark.parametrize(
    "make_out",
    [
        pytest.param(lambda tmp, wt: str(wt / "out"), id="inside"),
        pytest.param(lambda tmp, wt: str(wt), id="the-worktree"),
        pytest.param(lambda tmp, wt: "review-out", id="relative-from-inside"),
        pytest.param(lambda tmp, wt: str(tmp / "elsewhere" / ".." / "wt" / "out"), id="dotdot"),
        pytest.param(
            lambda tmp, wt: str(wt).upper() + "\\out",
            id="case",
            marks=pytest.mark.skipif(sys.platform != "win32", reason="case-insensitive paths"),
        ),
    ],
)
def test_review_refuses_an_out_path_inside_the_worktree(
    tmp_path, monkeypatch, capsys, make_out
) -> None:
    """CHARC 2c: refused before anything runs or is written -- no claude process, and
    nothing created in the worktree."""
    m = _load()
    wt = tmp_path / "wt"
    wt.mkdir()
    monkeypatch.chdir(wt)
    rc, out, seen = _review(
        m, tmp_path, monkeypatch, capsys, _result("VERDICT: NO_NEW_CRITICAL_MAJOR\n"),
        out=make_out(tmp_path, wt),
    )
    assert "inside the worktree" in out["error"]
    assert seen == {}
    assert list(wt.iterdir()) == []
    assert rc == 1


def test_review_accepts_an_out_path_beside_the_worktree(tmp_path, monkeypatch, capsys) -> None:
    """CHARC 2c: a sibling folder whose name starts with the worktree's is outside it (the
    comparison is by path, not by string prefix)."""
    m = _load()
    rc, out, seen = _review(
        m, tmp_path, monkeypatch, capsys, _result("VERDICT: NO_NEW_CRITICAL_MAJOR\n"),
        out=str(tmp_path / "wt-review"),
    )
    assert "error" not in out
    assert seen["cmd"][:2] == ["claude", "-p"]
    assert rc == 0


RECIPE = REPO_ROOT / "docs" / "implementer-dispatch-recipe.md"


def test_recipe_states_the_claude_pass_verdict_line_and_the_two_transcript_rules() -> None:
    """CHARC B1 (Codex R1-4b) and the R1-1 decline: the Claude pass's verdict line is
    ``VERDICT: <token>`` with exactly one token, the bare tokens and the zero-ERROR
    assertion are the Codex chain's transcript rules, and a Codex turn never fails on a
    bare ERROR line. One clause of the recipe's other-model sentence, so nobody re-files
    either finding."""
    m = _load()
    rows = [
        ln
        for ln in RECIPE.read_text(encoding="utf-8").splitlines()
        if ln.startswith("**Two implementer lanes, one rule:")
    ]
    assert len(rows) == 1
    for phrase in (
        "`VERDICT: <token>`",
        "exactly one distinct token",
        "the CODEX CHAIN's transcript rules",
        "never on a bare `ERROR` line",
        "the `succeeded in` line",
        *m.VERDICT_TOKENS,
    ):
        assert phrase in rows[0], phrase


# ------------------------------------------- the cell's agent file (P3, the preamble) --
AGENT_FILE = REPO_ROOT / ".claude" / "agents" / "implementer-codex-sol-high.md"

# The five sandbox-only residue tests that are NOT in the git family (build ledger, P0).
NON_GIT_RESIDUE = (
    "tests/pipeline/test_runner_chart_targets.py::test_step_charts_records_too_few_bars",
    "tests/pipeline/test_runner_chart_targets.py::"
    "test_step_charts_writes_chart_targets_with_ok_status",
    "tests/pipeline/test_step_charts_classification.py::"
    "test_step_charts_classifier_exception_persists_null_pattern_with_error",
    "tests/pipeline/test_step_charts_classification.py::"
    "test_step_charts_too_few_bars_persists_pattern_none",
    "tests/research/test_l2_lock_sys_modules_isolation_regression.py::"
    "test_research_l2lock_del_does_not_break_web_route_exception_identity",
)


def test_agent_file_frontmatter_names_the_lane() -> None:
    text = AGENT_FILE.read_text(encoding="utf-8")
    head = text.split("---")[1]
    assert "name: implementer-codex-sol-high" in head
    assert "model: codex/gpt-6.1-sol" in head
    assert "effort: high" in head


def test_the_staged_preamble_cannot_decide_the_identity_witness() -> None:
    """The agent file is piped into every first turn, and the transcript echoes it: a
    literal elevated marker would fail EVERY turn, a satisfying line would pass any."""
    m = _load()
    text = AGENT_FILE.read_text(encoding="utf-8")
    w = m.identity_witness(text, getpass.getuser())
    assert w["elevated_marker_present"] is False
    assert w["identity_line_present"] is False


def test_agent_file_quotes_the_driver_test_command_verbatim() -> None:
    m = _load()
    assert m.CELL_TEST_COMMAND in AGENT_FILE.read_text(encoding="utf-8")


def test_agent_file_points_at_the_main_repo_recipe() -> None:
    text = AGENT_FILE.read_text(encoding="utf-8")
    assert "C:/Users/rwsmy/swing-trading/docs/implementer-dispatch-recipe.md" in text


def test_agent_file_names_the_residue_and_each_name_is_a_real_test() -> None:
    text = AGENT_FILE.read_text(encoding="utf-8")
    for node in NON_GIT_RESIDUE:
        assert node in text, node
        path, name = node.split("::")
        assert f"def {name}(" in (REPO_ROOT / path).read_text(encoding="utf-8"), node
    assert "GitWorld" in text
    assert "class GitWorld" in (REPO_ROOT / "tests/trades/_git_world.py").read_text("utf-8")
