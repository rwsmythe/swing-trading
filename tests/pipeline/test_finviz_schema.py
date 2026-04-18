"""Finviz CSV schema validation + rejection."""
from __future__ import annotations

import json
from pathlib import Path

from swing.pipeline.finviz_schema import (
    REQUIRED_COLUMNS, validate_csv, reject_csv, ValidationResult,
)


def _good_csv(path: Path):
    cols = ",".join(REQUIRED_COLUMNS)
    rows = ["1,AAPL,Tech,Hardware,USA,180.0,2.5%,2.0,1.5,5.0,200.0,150.0,200000000,Computer Hardware",
            "2,MSFT,Tech,Software,USA,420.0,1.5%,1.0,0.8,4.5,440.0,330.0,300000000,Software"]
    path.write_text(cols + "\n" + "\n".join(rows), encoding="utf-8")


def test_valid_csv_passes(tmp_path: Path):
    p = tmp_path / "good.csv"
    _good_csv(p)
    result = validate_csv(p)
    assert result.is_valid
    assert result.row_count == 2


def test_missing_required_column_fails(tmp_path: Path):
    p = tmp_path / "bad.csv"
    cols = [c for c in REQUIRED_COLUMNS if c != "Ticker"]
    p.write_text(",".join(cols) + "\nA,B,C", encoding="utf-8")
    result = validate_csv(p)
    assert not result.is_valid
    assert any("Ticker" in r for r in result.reasons)


def test_empty_csv_fails(tmp_path: Path):
    p = tmp_path / "empty.csv"
    p.write_text("", encoding="utf-8")
    result = validate_csv(p)
    assert not result.is_valid


def test_reject_moves_with_sidecar(tmp_path: Path):
    inbox = tmp_path / "inbox"
    rejected = inbox / "rejected"
    inbox.mkdir()
    bad = inbox / "bad.csv"
    bad.write_text("just,bad\n", encoding="utf-8")

    result = ValidationResult(is_valid=False, reasons=["bad columns"], row_count=0)
    reject_csv(bad, result, rejected_dir=rejected)

    assert not bad.exists()
    moved = list(rejected.glob("*.csv"))
    assert len(moved) == 1
    sidecar = moved[0].with_suffix(moved[0].suffix + ".rejected-reasons.json")
    assert sidecar.exists()
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert "bad columns" in data["reasons"]
