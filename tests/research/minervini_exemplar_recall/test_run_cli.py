# tests/research/minervini_exemplar_recall/test_run_cli.py
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main


def _make_exemplar_csv(path: Path) -> None:
    header = (
        "exemplar_id,ticker,setup_label,detector_class,entry_date,buy_point_price,"
        "stop_price,base_start_date,base_end_date,date_precision,source,page,extracted_by,curated,notes"
    )
    path.write_text(header + "\nid-a,AAA,VCP,vcp,2010-03-30,,,,,day,S,P,claude,yes,n\n", encoding="utf-8")


def test_value_error_becomes_click_exception(tmp_path):
    runner = CliRunner()
    # Nonexistent exemplars CSV -> run_harness raises ValueError -> ClickException (exit 1, no traceback).
    result = runner.invoke(
        main,
        ["diagnose", "minervini-recall", "--exemplars-csv", str(tmp_path / "nope.csv"),
         "--tiingo-dir", str(tmp_path), "--output-dir", str(tmp_path / "out")],
    )
    assert result.exit_code != 0
    assert "Error:" in result.output  # ClickException renders as 'Error: ...'
    assert "Traceback" not in result.output


@pytest.mark.skipif(shutil.which("powershell.exe") is None, reason="powershell.exe not available")
def test_cli_stdout_is_ascii_through_powershell(tmp_path):
    # Exercise the REAL OS encoder (capsys bypasses cp1252; this is the gotcha guard).
    ex = tmp_path / "ex.csv"
    _make_exemplar_csv(ex)
    out = tmp_path / "out"
    # No Tiingo data present -> every exemplar is no_data, but the run still completes and prints ASCII.
    cmd = (
        f"{sys.executable} -m research.harness.minervini_exemplar_recall.run "
        f"--exemplars-csv {ex} --tiingo-dir {tmp_path} --output-dir {out}"
    )
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", cmd],
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[3]),
    )
    # Must not crash with UnicodeEncodeError on cp1252 stdout.
    assert "UnicodeEncodeError" not in proc.stderr
    assert proc.returncode == 0, proc.stderr


def test_h2_all_windows_writes_separate_file_only_when_flagged(tmp_path):
    from research.harness.minervini_exemplar_recall.run import run_harness

    ex = tmp_path / "ex.csv"
    _make_exemplar_csv(ex)
    # Flag OFF -> no diagnostic file (results.csv stays production-faithful windows[-1]).
    r_off, _p, _s, _m = run_harness(exemplars_csv=ex, tiingo_dir=tmp_path, output_dir=tmp_path / "off", bootstrap_b=10)
    assert not (r_off.parent / "h2_all_windows_diagnostic.csv").exists()
    # Flag ON -> a SEPARATE non-production file is written (even if empty under no_data).
    r_on, _p2, _s2, _m2 = run_harness(exemplars_csv=ex, tiingo_dir=tmp_path, output_dir=tmp_path / "on",
                                      h2_all_windows=True, bootstrap_b=10)
    diag = r_on.parent / "h2_all_windows_diagnostic.csv"
    assert diag.exists()
    # The diagnostic carries timing_mode (covers both single_session + sweep, not just entry).
    assert "timing_mode" in diag.read_text(encoding="utf-8").splitlines()[0].split(",")


def test_manifest_has_spec_required_fields(tmp_path):
    from research.harness.minervini_exemplar_recall.run import run_harness

    ex = tmp_path / "ex.csv"
    _make_exemplar_csv(ex)
    _r, _p, _s, manifest = run_harness(exemplars_csv=ex, tiingo_dir=tmp_path, output_dir=tmp_path / "out", bootstrap_b=10)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    for key in ("n_total", "n_screenable", "n_excluded", "finished_iso_utc",
                "skip_reason_counts", "per_exemplar_provenance", "config_snapshot", "l2_lock_preserved"):
        assert key in data, f"manifest missing {key}"
    # CSV with 1 curated row, 0 non-curated -> n_excluded 0.
    assert data["n_excluded"] == 0
