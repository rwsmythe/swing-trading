from __future__ import annotations

import csv
import io
import json
from pathlib import Path

RESULTS_HEADER = (
    "exemplar_id",
    "ticker",
    "role",
    "timing_mode",
    "fired",
    "first_rejecting_criterion",
    "base_start_date",
    "base_high",
    "correction_depth_pct",
    "base_duration_bars",
    "emergence_close",
    "data_source",
    "bars_through_anchor",
    "date_precision",
)

PER_SESSION_HEADER = (
    "exemplar_id",
    "ticker",
    "timing_mode",
    "session",
    "fired",
    "first_rejecting_criterion",
)


def _assert_ascii(text: str) -> str:
    text.encode("ascii")  # spec section 8: ASCII-only (stricter than cp1252; rejects em dash etc.)
    return text


def _write_csv(header, rows, path: Path) -> None:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(header), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    Path(path).write_text(_assert_ascii(buf.getvalue()), encoding="utf-8")


def write_results_csv(rows, path: Path) -> None:
    _write_csv(RESULTS_HEADER, rows, path)


def write_per_session_csv(rows, path: Path) -> None:
    _write_csv(PER_SESSION_HEADER, rows, path)


def write_summary_md(lines: list[str], path: Path) -> None:
    Path(path).write_text(_assert_ascii("\n".join(lines) + "\n"), encoding="utf-8")


def write_manifest_json(manifest: dict, path: Path) -> None:
    payload = dict(manifest)
    payload.setdefault("l2_lock_preserved", True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    Path(path).write_text(_assert_ascii(text), encoding="utf-8")
