"""scripts/cell_depth.py -- the dispatcher-read cell context gauge.

Synthetic transcripts are built to the REAL record shape (``message.usage``
with the three input counters; a ``content`` list whose first text part is the
dispatch prompt), including a partial trailing line (a cell mid-write).
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "cell_depth.py"


def _load():
    spec = importlib.util.spec_from_file_location("cell_depth", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["cell_depth"] = mod  # dataclass field-type resolution needs the module registered
    spec.loader.exec_module(mod)
    return mod


cell_depth = _load()


def _record(inp, read, create, text=None):
    msg = {"usage": {"input_tokens": inp, "cache_read_input_tokens": read,
                     "cache_creation_input_tokens": create}}
    if text is not None:
        msg["content"] = [{"type": "text", "text": text}]
    return json.dumps({"type": "assistant", "message": msg})


def _write_cell(subagents: Path, name: str, lines: list[str], *, mtime: float | None = None,
                partial_tail: bool = False) -> Path:
    subagents.mkdir(parents=True, exist_ok=True)
    p = subagents / f"agent-a{name}.jsonl"
    body = "\n".join(lines) + "\n"
    if partial_tail:
        body += '{"type": "assistant", "message": {"usage": {"input_tokens": 9'  # cut mid-write
    p.write_text(body, encoding="utf-8")
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


@pytest.fixture
def projects(tmp_path):
    """A fake ~/.claude/projects with one project dir for a fake repo root."""
    repo = tmp_path / "Users" / "x" / "repo"
    repo.mkdir(parents=True)
    pdir = tmp_path / "projects" / cell_depth.project_slug(repo)
    session = pdir / "sess-1" / "subagents"
    return tmp_path / "projects", repo, session


# --- slug derivation ---------------------------------------------------------

def test_project_slug_windows_shape():
    assert cell_depth.project_slug(Path(r"C:\Users\rwsmy\swing-trading")) == \
        "c--Users-rwsmy-swing-trading"


def test_project_dirs_match_case_insensitively(tmp_path):
    repo = Path(r"C:\Users\rwsmy\swing-trading")
    (tmp_path / "C--Users-rwsmy-swing-trading").mkdir()   # memory-dir spelling
    (tmp_path / "unrelated-repo").mkdir()
    found = cell_depth.find_project_dirs(tmp_path, repo)
    assert [p.name for p in found] == ["C--Users-rwsmy-swing-trading"]


# --- depth arithmetic --------------------------------------------------------

def test_depth_is_sum_of_three_counters_peak_and_current(projects):
    projects_dir, repo, sub = projects
    _write_cell(sub, "1", [
        _record(1000, 0, 200_000, text="You are dispatched as the **X** implementer"),
        _record(500, 450_000, 3_000),   # 453,500 = the peak
        _record(200, 300_000, 1_000),   # 301,200 = current (a compaction happened)
    ])
    [cell] = cell_depth.scan(projects_dir, repo)
    assert cell.peak == 453_500
    assert cell.current == 301_200
    assert cell.turns == 3
    assert cell.label.startswith("You are dispatched as the **X** implementer")


def test_partial_trailing_line_is_tolerated(projects):
    # a cell still writing leaves a cut JSON line at the tail; the gauge must
    # neither crash nor count it
    projects_dir, repo, sub = projects
    _write_cell(sub, "2", [_record(100, 100, 100)], partial_tail=True)
    [cell] = cell_depth.scan(projects_dir, repo)
    assert (cell.peak, cell.turns) == (300, 1)


def test_scan_descends_into_subagents_only(projects):
    # a transcript at the session level (the main session) is NOT a cell
    projects_dir, repo, sub = projects
    _write_cell(sub, "3", [_record(1, 1, 1)])
    main_session = sub.parent / "main.jsonl"
    main_session.write_text(_record(999_999, 0, 0) + "\n", encoding="utf-8")
    cells = cell_depth.scan(projects_dir, repo)
    assert [c.name for c in cells] == ["agent-a3.jsonl"]


# --- the CLI: precondition semantics ----------------------------------------

def _run(projects_dir, repo, *extra, capsys):
    rc = cell_depth.main(["--projects-dir", str(projects_dir), "--repo-root", str(repo), *extra])
    return rc, capsys.readouterr().out


def test_exit_1_when_a_listed_cell_exceeds_cap(projects, capsys):
    projects_dir, repo, sub = projects
    _write_cell(sub, "deep", [_record(0, 500_000, 0)])
    _write_cell(sub, "ok", [_record(0, 100_000, 0)])
    rc, out = _run(projects_dir, repo, "--cap", "400000", capsys=capsys)
    assert rc == 1
    assert "OVER" in out and "1 over the 400,000 cap" in out
    # deepest first
    assert out.index("agent-adeep") < out.index("agent-aok")


def test_exit_0_when_every_listed_cell_is_under_cap(projects, capsys):
    projects_dir, repo, sub = projects
    _write_cell(sub, "ok", [_record(0, 100_000, 0)])
    rc, out = _run(projects_dir, repo, capsys=capsys)
    assert rc == 0 and "0 over" in out


def test_live_filter_selects_by_transcript_age(projects, capsys):
    projects_dir, repo, sub = projects
    now = time.time()
    _write_cell(sub, "old", [_record(0, 900_000, 0)], mtime=now - 48 * 3600)
    _write_cell(sub, "new", [_record(0, 100_000, 0)], mtime=now - 60)
    rc, out = _run(projects_dir, repo, "--live", "6", capsys=capsys)
    assert rc == 0                      # the deep cell is not live; not the dispatcher's concern
    assert "agent-anew" in out and "agent-aold" not in out


def test_exit_2_when_no_transcripts_for_repo(projects, capsys):
    projects_dir, repo, _sub = projects
    rc, out = _run(projects_dir, repo, capsys=capsys)
    assert rc == 2 and "no cell transcripts found" in out


# --- --sessions: a MAIN session reads its own depth ---------------------------

def test_sessions_mode_reads_main_transcripts_and_excludes_cells(projects, capsys):
    projects_dir, repo, sub = projects
    _write_cell(sub, "cell", [_record(0, 700_000, 0)])            # a deep cell
    # the main session lives BESIDE its own <session-id>/subagents/ dir
    main = sub.parent.parent / "sess-1.jsonl"
    main.write_text(_record(1000, 390_000, 5_000,
                            text="Read and follow scripts/director_bootstrap_charc.md")
                    + "\n", encoding="utf-8")
    rc, out = _run(projects_dir, repo, "--sessions", capsys=capsys)
    assert rc == 0                                   # 396,000 is under the cap
    assert "sess-1.jsonl" in out and "agent-acell" not in out
    assert "director_bootstrap_charc" in out         # the launch prompt labels the seat
    assert "1 session(s); 0 over" in out
    # and the default (cell) mode still excludes the main session
    rc, out = _run(projects_dir, repo, capsys=capsys)
    assert rc == 1 and "agent-acell" in out and "sess-1.jsonl" not in out
