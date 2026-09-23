"""22-A2 Task 4 -- the tier-2 git preflight (A2-32..A2-41).

The preflight reads the operator's SELECTION (F9: a path, a commit sha and a
quoted text -- never a value), reads the artifact at that sha from git as
BYTES, and gathers the facts the conjunction (Task 5) and the replay (Task 9)
consume.  It never raises (E-6) and never touches a DB (F4).  Every git world
here is a temp repo with a bare "remote" (``tests/trades/_git_world.py``); the
acceptance bytes are line 57 of ``docs/rd-state.md`` at ``9f315cc6`` (the
pinned fixture, 1015 bytes, three-byte em-dashes).
"""
from __future__ import annotations

import ast
import inspect
import json
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from swing.trades import frozen_value_evidence as fve
from tests.trades._git_world import DEFAULT_PUSH_DATE, GitWorld, git

FIXTURE = (Path(__file__).resolve().parents[1] / "fixtures" / "tier2"
           / "rd_state_9f315cc6_line57.txt")
LINE57 = FIXTURE.read_bytes()
LINE57_TEXT = LINE57.decode("utf-8")
AUTHOR_9F315CC6 = "2026-08-10T02:41:33-10:00"
NOW = datetime(2026, 9, 23, 12, 0, 0, tzinfo=UTC)
RD_STATE = "docs/rd-state.md"
_SHA = "9f315cc6" + "0" * 32


def _rd_state_bytes() -> bytes:
    """An rd-state.md whose line 57 (1-based) is the pinned fixture line."""
    lines = [f"line {i}".encode("ascii") for i in range(1, 57)]
    return b"\n".join([*lines, LINE57, b"line 58", b""])


def _world(tmp_path: Path, *, push: bool = True) -> tuple[GitWorld, str]:
    world = GitWorld(tmp_path / "git")
    world.commit("README.md", b"base\n")
    sha = world.commit(RD_STATE, _rd_state_bytes(), author_date=AUTHOR_9F315CC6)
    if push:
        world.push()
    return world, sha


def _good_payload(sha: str, quoted: str = LINE57_TEXT) -> dict[str, str]:
    return {"artifact_path": RD_STATE, "artifact_commit_sha": sha, "quoted_text": quoted}


def _evidence(tmp_path: Path, payload: object, name: str = "evidence.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_text(raw: str) -> Callable[[Path], Path]:
    def write(tmp_path: Path) -> Path:
        path = tmp_path / "evidence.json"
        path.write_text(raw, encoding="utf-8")
        return path
    return write


def _write_non_utf8(tmp_path: Path) -> Path:
    path = tmp_path / "evidence.json"
    # A cp1252 em-dash (0x97) inside the quoted text: not valid UTF-8.
    path.write_bytes(
        b'{"artifact_path": "docs/rd-state.md", "artifact_commit_sha": "'
        + _SHA.encode("ascii") + b'", "quoted_text": "a \x97 b"}')
    return path


def _missing(tmp_path: Path) -> Path:
    return tmp_path / "absent.json"


_MALFORMED: dict[str, Callable[[Path], Path]] = {
    "fourth_key": _write_text(json.dumps({**_good_payload(_SHA), "uncovered_window": "x"})),
    "missing_key": _write_text(json.dumps(
        {"artifact_path": RD_STATE, "artifact_commit_sha": _SHA})),
    "non_str": _write_text(json.dumps({**_good_payload(_SHA), "quoted_text": 53.98})),
    "empty_value": _write_text(json.dumps({**_good_payload(_SHA), "quoted_text": ""})),
    # json.loads alone would silently keep the LAST duplicate.
    "duplicate_key": _write_text(
        '{"artifact_path": "docs/rd-state.md", "artifact_commit_sha": "' + _SHA + '", '
        '"quoted_text": "a", "quoted_text": "b"}'),
    "sha_39": _write_text(json.dumps(_good_payload(_SHA[:39]))),
    "sha_upper": _write_text(json.dumps(_good_payload(_SHA.upper()))),
    "not_object": _write_text(json.dumps([RD_STATE, _SHA, "q"])),
    "not_json": _write_text("{not json"),
    "non_utf8": _write_non_utf8,
    "missing_file": _missing,
}


# --------------------------------------------------------------------------- A2-32

@pytest.mark.parametrize("case", sorted(_MALFORMED))
def test_a2_32_malformed_evidence_file_refuses_evidence_file_malformed(
    tmp_path: Path, case: str,
) -> None:
    path = _MALFORMED[case](tmp_path)
    loaded = fve.load_evidence_selection(path)
    assert isinstance(loaded, fve.PreflightResult)
    assert loaded.failure == "evidence_file_malformed"
    assert loaded.facts is None
    result = fve.run_preflight(path, repo_dir=tmp_path, now_utc=NOW)
    assert result.failure == "evidence_file_malformed"
    assert result.facts is None
    assert result.detail


# --------------------------------------------------------------------------- A2-33

def test_a2_33_quoted_text_not_in_artifact(tmp_path: Path) -> None:
    _, sha = _world(tmp_path)
    # A real numeral changed by one cent: the selection no longer occurs.
    forged = LINE57_TEXT.replace("53.98", "53.99", 1)
    assert forged != LINE57_TEXT
    result = fve.run_preflight(_evidence(tmp_path, _good_payload(sha, forged)),
                               repo_dir=tmp_path / "git" / "work", now_utc=NOW)
    assert result.failure == "quoted_text_not_in_artifact"
    assert result.facts is None
    # Counterpart: the true selection passes the same check.
    ok = fve.run_preflight(_evidence(tmp_path, _good_payload(sha), "ok.json"),
                           repo_dir=tmp_path / "git" / "work", now_utc=NOW)
    assert ok.failure is None


# --------------------------------------------------------------------------- A2-34

def test_a2_34_quoted_text_spanning_two_lines_refuses_not_a_whole_line(tmp_path: Path) -> None:
    _, sha = _world(tmp_path)
    two_lines = LINE57_TEXT + "\nline 58"
    # Pre-fix arithmetic: the two-line selection IS a byte-substring of the
    # artifact, so an implementation without the one-line bound admits it.
    assert two_lines.encode("utf-8") in _rd_state_bytes()
    result = fve.run_preflight(_evidence(tmp_path, _good_payload(sha, two_lines)),
                               repo_dir=tmp_path / "git" / "work", now_utc=NOW)
    assert result.failure == "quoted_text_not_a_whole_line"
    whole_file = _rd_state_bytes().decode("utf-8")
    result = fve.run_preflight(_evidence(tmp_path, _good_payload(sha, whole_file), "w.json"),
                               repo_dir=tmp_path / "git" / "work", now_utc=NOW)
    assert result.failure == "quoted_text_not_a_whole_line"


def test_codex_r1_02_a_nul_in_the_selection_refuses_at_the_load_boundary(
    tmp_path: Path,
) -> None:
    """Codex R1-02: SQLite's ``length()`` stops at the first U+0000 while
    Python counts past it, so a quoted text that BEGINS with NUL passed every
    service check (byte-substring, one line, the ``_tp_quoted_text_one_line``
    mirror) and then aborted in the citation trigger's ``length(...) > 0`` --
    an authorize-then-abort disagreement (brief 4.4): the dry run reads
    admissible and the apply dies on a raw ``IntegrityError``.  The selection
    is refused where the operator's input enters, ``evidence_file_malformed``.

    Pre-fix arithmetic (measured on SQLite 3.50.4): ``length(json_extract(
    '{"q":"\\u0000OII"}', '$.q')) = 0``; the NUL-led line IS a byte-substring
    of the artifact below and carries no line break, so the pre-fix preflight
    returns FACTS (``failure is None``).  Post-fix: ``evidence_file_malformed``
    for the quoted text (leading and interior NUL alike) and for a NUL in
    either other key; the same line without the NUL still reads facts."""
    import sqlite3

    measured = sqlite3.connect(":memory:").execute(
        "SELECT length(json_extract(?, '$.q'))",
        (json.dumps({"q": "\x00OII"}),)).fetchone()[0]
    assert measured == 0

    world = GitWorld(tmp_path / "git")
    world.commit("README.md", b"base\n")
    nul_line = b"\x00" + LINE57
    lines = [f"line {i}".encode("ascii") for i in range(1, 57)]
    # Line 58 is line 57 without its NUL: the counterpart below quotes a WHOLE
    # line (OBS-1, RD ruling A-R1 item 2), not a substring of the NUL-led one.
    sha = world.commit(RD_STATE, b"\n".join([*lines, nul_line, LINE57, b"line 59", b""]),
                       author_date=AUTHOR_9F315CC6)
    world.push()
    repo = tmp_path / "git" / "work"

    for name, payload in (
            ("leading.json", _good_payload(sha, "\x00" + LINE57_TEXT)),
            ("interior.json", _good_payload(sha, LINE57_TEXT[:40] + "\x00"
                                            + LINE57_TEXT[40:])),
            ("path.json", {**_good_payload(sha), "artifact_path": RD_STATE + "\x00"})):
        path = _evidence(tmp_path, payload, name)
        loaded = fve.load_evidence_selection(path)
        assert isinstance(loaded, fve.PreflightResult), name
        assert loaded.failure == "evidence_file_malformed", name
        assert "U+0000" in loaded.detail, name
        result = fve.run_preflight(path, repo_dir=repo, now_utc=NOW)
        assert (result.failure, result.facts) == ("evidence_file_malformed", None), name

    # Counterpart: the same selection WITHOUT the NUL is a whole line of that
    # artifact (line 58) and reads facts.
    ok = fve.run_preflight(_evidence(tmp_path, _good_payload(sha), "ok.json"),
                           repo_dir=repo, now_utc=NOW)
    assert ok.failure is None and ok.facts is not None


# --------------------------------------------------------------------------- A2-35

def test_a2_35_line57_world_yields_author_instant_ancestry_and_remote_tip(
    tmp_path: Path,
) -> None:
    world, sha = _world(tmp_path)
    result = fve.run_preflight(_evidence(tmp_path, _good_payload(sha)),
                               repo_dir=world.work, now_utc=NOW)
    assert result.failure is None, result.detail
    facts = result.facts
    assert facts is not None
    assert facts.selection.artifact_commit_sha == sha
    assert facts.selection.quoted_text == LINE57_TEXT
    assert facts.author_instant.isoformat() == AUTHOR_9F315CC6
    assert facts.author_instant.utcoffset() is not None
    assert facts.committer_instant.isoformat() == AUTHOR_9F315CC6
    assert facts.is_ancestor is True
    assert facts.resolved_remote_ref_sha == world.remote_tip()
    assert facts.descendant_count == 0
    world.grow_remote(2)
    grown = fve.run_preflight(_evidence(tmp_path, _good_payload(sha)),
                              repo_dir=world.work, now_utc=NOW)
    assert grown.facts is not None
    assert grown.facts.descendant_count == 2
    assert grown.facts.resolved_remote_ref_sha == world.remote_tip()


# --------------------------------------------------------------------------- A2-36

def test_a2_36_local_commit_not_ancestor_of_remote_ref_reads_false(tmp_path: Path) -> None:
    world, published = _world(tmp_path)
    # The evidence commit exists locally but was never pushed.
    local_only = world.commit(RD_STATE, _rd_state_bytes() + b"local edit\n",
                              author_date=AUTHOR_9F315CC6)
    result = fve.run_preflight(_evidence(tmp_path, _good_payload(local_only)),
                               repo_dir=world.work, now_utc=NOW)
    assert result.failure is None, result.detail
    assert result.facts is not None
    assert result.facts.is_ancestor is False
    # Pre-fix arithmetic: the commit IS reachable from local HEAD, so an
    # implementation that checks local reachability (or none) reads True.
    assert git(world.work, "merge-base", "--is-ancestor", local_only, "HEAD") == b""
    assert result.facts.descendant_count is None
    # Rewritten published history: the published commit drops out too.
    world.rewrite_remote_dropping(published)
    dropped = fve.run_preflight(_evidence(tmp_path, _good_payload(published), "d.json"),
                                repo_dir=world.work, now_utc=NOW)
    assert dropped.facts is not None
    assert dropped.facts.is_ancestor is False


# --------------------------------------------------------------------------- A2-37

def test_a2_37_non_ascii_line_round_trips_as_bytes(tmp_path: Path) -> None:
    world, sha = _world(tmp_path)
    assert "—" in LINE57_TEXT                      # the em-dash
    # MEASURED: 1015 bytes, 1005 chars (five 3-byte em-dashes).  The plan and
    # ledger say "1006 chars"; the bytes, sha256 and offsets they pin agree.
    assert len(LINE57) == 1015 and len(LINE57_TEXT) == 1005
    assert LINE57_TEXT.count("—") == 5
    result = fve.run_preflight(_evidence(tmp_path, _good_payload(sha)),
                               repo_dir=world.work, now_utc=NOW)
    assert result.failure is None, result.detail
    # Pre-fix arithmetic: the same artifact DECODED as cp1252 (the
    # ``text=True`` default on this box) does not contain the selection.
    artifact = git(world.work, "cat-file", "blob", f"{sha}:{RD_STATE}")
    assert LINE57_TEXT not in artifact.decode("cp1252", errors="replace")
    # And the module never asks subprocess to decode.
    tree = ast.parse(inspect.getsource(fve))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "run":
            kws = {k.arg for k in node.keywords}
            assert not ({"text", "encoding", "universal_newlines", "errors"} & kws)


# --------------------------------------------------------------------------- A2-38

def test_a2_38_git_timeout_reads_tier2_unverifiable_without_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    world, sha = _world(tmp_path)
    seen: list[float | None] = []

    def timed_out(*args: object, **kwargs: object) -> object:
        seen.append(kwargs.get("timeout"))  # type: ignore[arg-type]
        raise subprocess.TimeoutExpired(cmd="git", timeout=fve.GIT_TIMEOUT_SECONDS)

    monkeypatch.setattr(fve.subprocess, "run", timed_out)
    result = fve.run_preflight(_evidence(tmp_path, _good_payload(sha)),
                               repo_dir=world.work, now_utc=NOW)
    assert result.failure == "tier2_unverifiable"
    assert result.facts is None
    assert "timed out" in result.detail
    assert seen == [fve.GIT_TIMEOUT_SECONDS]

    def git_missing(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("git")

    monkeypatch.setattr(fve.subprocess, "run", git_missing)
    missing = fve.run_preflight(_evidence(tmp_path, _good_payload(sha), "m.json"),
                                repo_dir=world.work, now_utc=NOW)
    assert missing.failure == "tier2_unverifiable"


# --------------------------------------------------------------------------- A2-39

def test_a2_39_no_remote_ref_reads_tier2_unverifiable(tmp_path: Path) -> None:
    world, sha = _world(tmp_path, push=False)
    result = fve.run_preflight(_evidence(tmp_path, _good_payload(sha)),
                               repo_dir=world.work, now_utc=NOW)
    assert result.failure == "tier2_unverifiable"
    assert fve.REMOTE_REF in result.detail
    assert result.facts is None


# --------------------------------------------------------------------------- A2-40

def test_a2_40_reflog_absent_reads_null_present_reads_age(tmp_path: Path) -> None:
    world, sha = _world(tmp_path, push=False)
    # The ref exists but was written with reflogs off: no reflog entry.
    git(world.work, "-c", "core.logAllRefUpdates=false", "update-ref",
        fve.REMOTE_REF, sha)
    absent = fve.run_preflight(_evidence(tmp_path, _good_payload(sha)),
                               repo_dir=world.work, now_utc=NOW)
    assert absent.failure is None, absent.detail
    assert absent.facts is not None
    assert absent.facts.remote_ref_updated_at is None
    assert absent.facts.remote_ref_age_seconds is None

    world2 = GitWorld(tmp_path / "git2")
    world2.commit("README.md", b"base\n")
    sha2 = world2.commit(RD_STATE, _rd_state_bytes(), author_date=AUTHOR_9F315CC6)
    world2.push(push_date=DEFAULT_PUSH_DATE)
    present = fve.run_preflight(_evidence(tmp_path, _good_payload(sha2), "p.json"),
                                repo_dir=world2.work, now_utc=NOW)
    assert present.facts is not None
    updated = datetime.fromisoformat(DEFAULT_PUSH_DATE)
    assert present.facts.remote_ref_updated_at == updated
    # 2026-09-20T12:00Z -> 2026-09-23T12:00Z = 3 days.
    assert present.facts.remote_ref_age_seconds == 3 * 86400
    assert present.facts.remote_ref_age_seconds == int((NOW - updated).total_seconds())


# --------------------------------------------------------------------------- A2-41

_WRITE_SQL = ("INSERT", "UPDATE", "DELETE", "REPLACE", "BEGIN", "COMMIT", "CREATE", "DROP")


def _string_parts(node: ast.AST) -> list[str]:
    out: list[str] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            out.append(sub.value)
    return out


def test_a2_41_preflight_never_raises_and_module_writes_no_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # (1) Never raises over every A2-32..A2-40 input shape.
    world, sha = _world(tmp_path)
    inputs: list[Path] = []
    for name, writer in _MALFORMED.items():
        case_dir = tmp_path / f"m_{name}"
        case_dir.mkdir()
        inputs.append(writer(case_dir))
    good = _evidence(tmp_path, _good_payload(sha), "good.json")
    inputs += [
        good,
        _evidence(tmp_path, _good_payload(sha, "not in the artifact"), "absent.json"),
        _evidence(tmp_path, _good_payload(sha, LINE57_TEXT + "\nline 58"), "two.json"),
        _evidence(tmp_path, _good_payload("f" * 40), "nosha.json"),
        _evidence(tmp_path, {**_good_payload(sha), "artifact_path": "no/such.md"}, "p.json"),
        _evidence(tmp_path, {**_good_payload(sha), "artifact_path": "docs"}, "tree.json"),
    ]
    for path in inputs:
        for repo in (world.work, tmp_path / "not-a-repo"):
            result = fve.run_preflight(path, repo_dir=repo, now_utc=NOW)
            assert isinstance(result, fve.PreflightResult)
            assert (result.facts is None) != (result.failure is None)
    # A naive ``now`` is a caller defect; still no raise, fails closed.
    naive = fve.run_preflight(good, repo_dir=world.work,
                              now_utc=datetime(2026, 9, 23, 12, 0))
    assert naive.failure == "tier2_unverifiable"

    def boom(*args: object, **kwargs: object) -> object:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(fve.subprocess, "run", boom)
    assert fve.run_preflight(good, repo_dir=world.work,
                             now_utc=NOW).failure == "tier2_unverifiable"
    monkeypatch.undo()

    # (2) The module performs no DB write and opens no transaction: no
    # ``.execute*`` / ``.commit`` call carries write SQL, anywhere.
    tree = ast.parse(Path(fve.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        attr = getattr(node.func, "attr", "")
        assert attr not in {"commit", "executescript", "executemany", "rollback"}, attr
        if attr == "execute":
            for text in _string_parts(node):
                upper = " ".join(text.upper().split())
                assert not any(upper.startswith(k) or f" {k} " in f" {upper} "
                               for k in _WRITE_SQL), text

    # (3) The preflight half touches no DB at all (the conjunction half, Task 5,
    # READS one; the preflight functions and their git helpers never name it).
    for name in fve.PREFLIGHT_FUNCTIONS:
        src = inspect.getsource(getattr(fve, name))
        assert "sqlite3" not in src and ".execute(" not in src and "conn" not in src, name
