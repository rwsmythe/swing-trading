from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main


def test_command_is_registered():
    runner = CliRunner()
    result = runner.invoke(main, ["diagnose", "shadow-expectancy", "--help"])
    assert result.exit_code == 0
    assert "--db" in result.output
    assert "--source" in result.output


def test_missing_db_is_friendly_error(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["diagnose", "shadow-expectancy", "--db",
                                  str(tmp_path / "nope.db"), "--output-dir", str(tmp_path)])
    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "Traceback" not in result.output


@pytest.mark.skipif(shutil.which("powershell.exe") is None, reason="powershell.exe absent")
def test_cli_stdout_is_ascii_through_powershell(tmp_path):
    # Build a minimal real DB via the harness testkit, then run through the OS encoder.
    # make_db runs migration 0008 which seeds the active hypothesis registry.
    from tests.research.shadow_expectancy.testkit import make_db
    make_db(tmp_path)
    out = tmp_path / "out"
    cmd = (
        f"{sys.executable} -m research.harness.shadow_expectancy.run "
        f"--db {tmp_path / 't.db'} --output-dir {out}"
    )
    proc = subprocess.run(["powershell.exe", "-NoProfile", "-Command", cmd],
                          capture_output=True, text=True,
                          cwd=str(Path(__file__).resolve().parents[3]))
    assert "UnicodeEncodeError" not in proc.stderr
    assert proc.returncode == 0, proc.stderr


def test_ensure_research_importable_is_idempotent_and_root_guarded(monkeypatch):
    import sys as _sys
    from pathlib import Path as _Path

    from swing.cli import _ensure_research_importable

    # A path entry resolves to a research-root if (its dir, or cwd for a falsey "" entry) contains
    # research/harness. Falsey entries ("" = cwd) MUST be treated as cwd: under pytest from the
    # repo root, "" resolves to a research-root and would otherwise mask a non-insert (Codex R3-#1).
    def _is_research_root(p):
        base = _Path(p) if p else _Path.cwd()
        return (base / "research" / "harness").is_dir()

    pruned = [p for p in _sys.path if not _is_research_root(p)]
    monkeypatch.setattr(_sys, "path", pruned)
    assert not any(_is_research_root(p) for p in _sys.path), \
        "precondition: pruning must remove every research-root (incl. cwd via an empty entry)"
    _ensure_research_importable()
    # DIRECT proof the helper inserted a NON-EMPTY ABSOLUTE source root at sys.path[0] containing
    # research/harness. A bare "" (cwd) does NOT count. Do NOT use importlib.import_module as the
    # proof: test_run.py imports run_harness at module load, so the module is already cached and
    # importlib would false-pass off sys.modules even if the insert failed (Codex R2-#1, R3-#1).
    head = _sys.path[0]
    assert head and _Path(head).is_absolute() and (_Path(head) / "research" / "harness").is_dir()
    before = list(_sys.path)
    _ensure_research_importable()   # idempotent: no duplicate insert.
    assert _sys.path == before


def test_no_unguarded_research_harness_import_under_diagnose():
    # spec 5.1 (Codex R1-#5): the rule is MECHANICAL -- EVERY `from research.harness` import site
    # under the diagnose group must be preceded (within its enclosing function) by a
    # _ensure_research_importable() call. This grep guard fails if any new un-guarded site lands.
    from pathlib import Path

    import swing.cli as cli_mod

    src = Path(cli_mod.__file__).read_text(encoding="utf-8").splitlines()
    import_lines = [i for i, ln in enumerate(src) if "from research.harness" in ln]
    assert import_lines, "expected at least one deferred research.harness import in cli.py"
    for i in import_lines:
        # scan upward within the same function for a _ensure_research_importable() call. A call on
        # a COMMENTED line does not count (skip lines starting with '#'); stop at the enclosing
        # top-level command function header (a `def ` not indented two levels in).
        guarded = False
        for j in range(i - 1, -1, -1):
            line = src[j]
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if "_ensure_research_importable()" in line:
                guarded = True
                break
            if stripped.startswith("def ") and not line.startswith("    " * 2):
                break   # hit the enclosing top-level/command function header
        assert guarded, (
            f"un-guarded `from research.harness` at cli.py line {i + 1}: "
            f"{src[i].strip()!r} -- add _ensure_research_importable() before it")
