"""Finviz CSV schema declaration + validator + rejector."""
from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

REQUIRED_COLUMNS: tuple[str, ...] = (
    "No.", "Ticker", "Sector", "Industry", "Country", "Price",
    "Change", "Average Volume", "Relative Volume",
    "Average True Range", "52-Week High", "52-Week Low",
    "Market Cap",
)


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    reasons: list[str]
    row_count: int


def validate_csv(path: Path) -> ValidationResult:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return ValidationResult(is_valid=False, reasons=["empty file"], row_count=0)

    reader = csv.reader(text.splitlines())
    try:
        header = next(reader)
    except StopIteration:
        return ValidationResult(is_valid=False, reasons=["no header row"], row_count=0)

    header_set = set(h.strip() for h in header)
    missing = [c for c in REQUIRED_COLUMNS if c not in header_set]
    reasons: list[str] = []
    if missing:
        reasons.append(f"missing columns: {missing}")

    rows = list(reader)
    if not rows:
        reasons.append("no data rows")
    return ValidationResult(
        is_valid=not reasons, reasons=reasons, row_count=len(rows),
    )


def reject_csv(
    path: Path, result: ValidationResult, *, rejected_dir: Path,
) -> Path:
    """Move file to rejected/ + write .rejected-reasons.json sidecar.
    Returns the new path."""
    rejected_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    new_name = f"{path.stem}.rejected-{ts}{path.suffix}"
    dst = rejected_dir / new_name
    shutil.move(str(path), str(dst))
    sidecar = dst.with_suffix(dst.suffix + ".rejected-reasons.json")
    sidecar.write_text(
        json.dumps({
            "rejected_at": datetime.now().isoformat(timespec="seconds"),
            "original_path": str(path),
            "reasons": result.reasons,
            "row_count": result.row_count,
        }, indent=2),
        encoding="utf-8",
    )
    return dst
