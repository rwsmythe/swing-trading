from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main


def _exemplar_csv(path: Path) -> None:
    header = (
        "exemplar_id,ticker,setup_label,detector_class,entry_date,buy_point_price,"
        "stop_price,base_start_date,base_end_date,date_precision,source,page,extracted_by,curated,notes"
    )
    rows = [
        "twosmw-fig11-1-amzn,AMZN,pb,unmapped,1997-09,,,,,month,T,p,claude,yes,n",
        "ttlc-fig10-1-body,BODY,pb,vcp,2011-01-05,,,,,day,T,p,claude,yes,n",
        "twosmw-fig11-6-dks,DKS,pb,double_bottom_w,2003-04,,,,,month,T,p,claude,yes,n",
        "twosmw-fig11-7-jnpr,JNPR,pb,unmapped,1999-07-30,,,,,day,T,p,claude,yes,n",
        "twosmw-fig11-3-yhoo,YHOO,pb,unmapped,1997-06-20,,,,,day,T,p,claude,yes,n",
    ]
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def test_value_error_becomes_click_exception(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["diagnose", "primary-base-recall", "--exemplars-csv", str(tmp_path / "nope.csv"),
         "--tiingo-dir", str(tmp_path), "--output-dir", str(tmp_path / "out")],
    )
    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "Traceback" not in result.output


def test_command_is_registered():
    runner = CliRunner()
    result = runner.invoke(main, ["diagnose", "primary-base-recall", "--help"])
    assert result.exit_code == 0
    assert "--exemplars-csv" in result.output
    assert "--tiingo-dir" in result.output
    # No --db flag (pure on bars).
    assert "--db" not in result.output


@pytest.mark.skipif(shutil.which("powershell.exe") is None, reason="powershell.exe not available")
def test_cli_stdout_is_ascii_through_powershell(tmp_path):
    # Exercise the REAL OS encoder (capsys bypasses cp1252; this is the gotcha guard).
    ex = tmp_path / "ex.csv"
    _exemplar_csv(ex)
    out = tmp_path / "out"
    cmd = (
        f"{sys.executable} -m research.harness.minervini_primary_base_recall.run "
        f"--exemplars-csv {ex} --tiingo-dir {tmp_path} --output-dir {out}"
    )
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", cmd],
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[3]),
    )
    assert "UnicodeEncodeError" not in proc.stderr
    assert proc.returncode == 0, proc.stderr
