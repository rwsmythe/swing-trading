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
  user>` and never `CodexSandboxOffline`. The banner cannot see the windows.sandbox mode.

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
ELEVATED_FALLBACK_4E = _turn_transcript("sandbox-user: CodexSandboxOffline")


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
    text = _turn_transcript("sandbox-user: rwsmy") + "note: CodexSandboxOffline\n"
    w = m.identity_witness(text, "rwsmy")
    assert w["identity_line_present"] is True
    assert w["identity_ok"] is False


def test_identity_witness_needs_the_whole_line() -> None:
    m = _load()
    for out in ("sandbox-user: rwsmy2", "  sandbox-user: rwsmy", "xsandbox-user: rwsmy"):
        assert m.identity_witness(_turn_transcript(out), "rwsmy")["identity_ok"] is False, out


def _run_turn(m, tmp_path, monkeypatch, capsys, transcript: str, session: str | None = None):
    """Drive ``cmd_turn`` through ``main`` with a fake runner; return (exit, json, stdin)."""
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codexhome"))
    prompt = tmp_path / "brief.md"
    prompt.write_bytes(b"Do the task.\n")
    seen: dict[str, bytes] = {}

    def fake_run(cmd, stdin_path, out_path, cwd):
        seen["stdin"] = Path(stdin_path).read_bytes()
        seen["cmd"] = cmd
        Path(out_path).write_bytes(transcript.encode("utf-8"))
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
    assert "CodexSandboxOffline" not in stdin
    assert m.identity_witness(stdin, me)["identity_line_present"] is False
    assert ("resume" in seen["cmd"]) is bool(session)
