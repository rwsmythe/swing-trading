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


def _record(inp, read, create, text=None, version=None, model=None):
    msg = {"usage": {"input_tokens": inp, "cache_read_input_tokens": read,
                     "cache_creation_input_tokens": create}}
    if text is not None:
        msg["content"] = [{"type": "text", "text": text}]
    if model is not None:
        msg["model"] = model
    rec: dict = {"type": "assistant", "message": msg}
    if version is not None:
        rec["version"] = version
    return json.dumps(rec)


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


# --- build (top-level version) + model (message.model) ----------------------

def test_single_build_and_model_read_from_real_locations(projects):
    projects_dir, repo, sub = projects
    # baseline: version/model read from their real top-level / message.model locations
    _write_cell(sub, "plain", [
        _record(1000, 0, 200_000, text="hi", version="2.1.280", model="claude-opus-5-5"),
        _record(500, 450_000, 3_000, version="2.1.280", model="claude-opus-5-5"),
    ])
    # discriminator: a record with NO usage, carrying a DIFFERENT, earlier version, as
    # the first record -- an implementation that reads only usage-bearing records
    # never sees it and gets the wrong build
    _write_cell(sub, "plant", [
        json.dumps({"type": "system", "version": "2.1.270"}),
        _record(1000, 0, 200_000, text="hi", version="2.1.280", model="claude-opus-5-5"),
        _record(500, 450_000, 3_000, version="2.1.280", model="claude-opus-5-5"),
    ])
    cells = {c.name: c for c in cell_depth.scan(projects_dir, repo)}
    assert cells["agent-aplain.jsonl"].build == "2.1.280"
    assert cells["agent-aplain.jsonl"].model == "claude-opus-5-5"
    assert cells["agent-aplant.jsonl"].build == "2.1.270+2.1.280"
    assert cells["agent-aplant.jsonl"].model == "claude-opus-5-5"


def test_synthetic_model_excluded(projects):
    projects_dir, repo, sub = projects
    _write_cell(sub, "mix", [
        _record(0, 0, 0, model="<synthetic>"),
        _record(100, 0, 0, model="claude-sonnet-5"),
    ])
    _write_cell(sub, "onlysynthetic", [
        _record(0, 0, 0, model="<synthetic>"),
    ])
    cells = {c.name: c for c in cell_depth.scan(projects_dir, repo)}
    assert cells["agent-amix.jsonl"].model == "claude-sonnet-5"
    assert cells["agent-aonlysynthetic.jsonl"].model == "-"


def test_mixed_values_shown_first_seen_order_not_collapsed(projects):
    projects_dir, repo, sub = projects
    _write_cell(sub, "mixed", [
        _record(0, 0, 0, version="2.1.272", model="claude-opus-5"),
        _record(0, 0, 0, version="2.1.272", model="claude-opus-5-5"),
        _record(0, 0, 0, version="2.1.280", model="claude-opus-5"),
    ])
    [cell] = cell_depth.scan(projects_dir, repo)
    assert cell.build == "2.1.272+2.1.280"
    assert cell.model == "claude-opus-5+claude-opus-5-5"


def test_mixed_model_order_is_first_seen_not_alphabetical(projects):
    # sorted() would put claude-opus-5-5 before claude-sonnet-5 ('o' < 's'); the
    # first-seen order here is the opposite, so a sorted-implementation fails this
    projects_dir, repo, sub = projects
    _write_cell(sub, "order", [
        _record(0, 0, 0, model="claude-sonnet-5"),
        _record(0, 0, 0, model="claude-opus-5-5"),
    ])
    [cell] = cell_depth.scan(projects_dir, repo)
    assert cell.model == "claude-sonnet-5+claude-opus-5-5"


def test_absent_build_and_model_degrade_to_dash(projects):
    projects_dir, repo, sub = projects
    _write_cell(sub, "noinfo", [_record(100, 100, 100)])
    [cell] = cell_depth.scan(projects_dir, repo)
    assert cell.build == "-"
    assert cell.model == "-"


def test_cli_rows_carry_build_and_model_in_both_modes(projects, capsys):
    projects_dir, repo, sub = projects
    _write_cell(sub, "cell1", [_record(0, 0, 0, version="2.1.280", model="claude-sonnet-5")])
    rc, out = _run(projects_dir, repo, capsys=capsys)
    assert rc == 0
    header = out.splitlines()[0]
    assert "build" in header and "model" in header
    cell_row = next(line for line in out.splitlines() if "agent-acell1" in line)
    assert "2.1.280" in cell_row and "claude-sonnet-5" in cell_row
    out.encode("ascii")

    main = sub.parent.parent / "sess-1.jsonl"
    main.write_text(_record(0, 0, 0, version="2.1.272", model="claude-fable-5-1") + "\n",
                    encoding="utf-8")
    rc2, out2 = _run(projects_dir, repo, "--sessions", capsys=capsys)
    assert rc2 == 0
    header2 = out2.splitlines()[0]
    assert "build" in header2 and "model" in header2
    session_row = next(line for line in out2.splitlines() if "sess-1.jsonl" in line)
    assert "2.1.272" in session_row and "claude-fable-5-1" in session_row
    out2.encode("ascii")


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


# --- --agent: the round-gate read of ONE named cell ----------------------------
#
# The selection-rule defect is INFERRED FROM THE CODE, not measured from an
# incident (CHARC ruling (a), 2026-09-24): --live selects by transcript MTIME,
# and an executing cell PARKED at a review-round gate writes nothing, so after
# the window it drops out of --live while a newer cell's row stands alone --
# the gate would read the wrong cell's depth with nothing saying one is missing.
# --agent reads the cell the dispatcher names, at any age.

def test_agent_reads_a_parked_cell_older_than_the_live_window(projects, capsys):
    projects_dir, repo, sub = projects
    now = time.time()
    _write_cell(sub, "parked", [_record(0, 350_000, 0, text="the gated cell")],
                mtime=now - 3 * 3600)                     # parked for 3h at a round gate
    _write_cell(sub, "newer", [_record(0, 50_000, 0, text="another cell")], mtime=now - 60)
    # the defect: the one-hour window shows only the newer cell
    rc, out = _run(projects_dir, repo, "--live", "1", capsys=capsys)
    assert rc == 0 and "agent-anewer" in out and "agent-aparked" not in out
    # the fix: the named cell is read regardless of age, and only it
    rc, out = _run(projects_dir, repo, "--agent", "aparked", capsys=capsys)
    assert rc == 0
    assert "agent-aparked" in out and "agent-anewer" not in out
    assert "350,000" in out and "1 cell(s); 0 over" in out
    out.encode("ascii")


def test_agent_is_repeatable_and_applies_the_cap(projects, capsys):
    projects_dir, repo, sub = projects
    _write_cell(sub, "one", [_record(0, 450_000, 0)])
    _write_cell(sub, "two", [_record(0, 100_000, 0)])
    _write_cell(sub, "three", [_record(0, 200_000, 0)])
    rc, out = _run(projects_dir, repo, "--agent", "aone", "--agent", "atwo", capsys=capsys)
    assert rc == 1 and "1 over the 400,000 cap" in out
    assert "agent-aone" in out and "agent-atwo" in out and "agent-athree" not in out


def test_agent_unknown_id_exits_2_naming_the_searched_glob(projects, capsys):
    projects_dir, repo, sub = projects
    _write_cell(sub, "present", [_record(0, 100_000, 0)])
    rc, out = _run(projects_dir, repo, "--agent", "amissing", capsys=capsys)
    assert rc == 2
    assert "amissing" in out and "subagents" in out and "agent-amissing.jsonl" in out
    out.encode("ascii")


def test_agent_with_live_is_a_usage_error(projects, capsys):
    projects_dir, repo, sub = projects
    _write_cell(sub, "x", [_record(0, 100_000, 0)])
    with pytest.raises(SystemExit) as exc:
        cell_depth.main(["--projects-dir", str(projects_dir), "--repo-root", str(repo),
                         "--agent", "ax", "--live", "1"])
    assert exc.value.code == 2
