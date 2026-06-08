# research/harness/minervini_exemplar_recall/output.py
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

RESULTS_HEADER = (
    "exemplar_id",
    "ticker",
    "timing_mode",
    "h1_outcome",
    "best_bucket",
    "first_rejecting_gate",
    "h2_fired_faithful",
    "h2_fired_isolated",
    "fired_classes_faithful",
    "fired_classes_isolated",
    "rs_path",
    "data_source",
    "n_bars",
    "screenable",
    "h2_anchor_mode_limited_possible",
    "h2_anchor_mode_limited_reason",
)

PER_SESSION_HEADER = (
    "exemplar_id",
    "ticker",
    "timing_mode",
    "session",
    "h1_outcome",
    "bucket",
    "fired_faithful_expected",
    "fired_isolated_expected",
    "fired_classes_faithful",
    "fired_classes_isolated",
)

H2_ALL_WINDOWS_HEADER = (
    "exemplar_id",
    "ticker",
    "timing_mode",
    "session",
    "window_index",
    "anchor_date",
    "fired_classes",
)


def _assert_ascii(text: str) -> str:
    text.encode("cp1252")  # raises if a non-cp1252 glyph slipped in
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


def write_h2_all_windows_csv(rows, path: Path) -> None:
    _write_csv(H2_ALL_WINDOWS_HEADER, rows, path)


def write_manifest_json(manifest: dict, path: Path) -> None:
    payload = dict(manifest)
    payload.setdefault("l2_lock_preserved", True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    Path(path).write_text(_assert_ascii(text), encoding="utf-8")


def write_summary_md(lines: list[str], path: Path) -> None:
    body = "\n".join(lines) + "\n"
    Path(path).write_text(_assert_ascii(body), encoding="utf-8")
