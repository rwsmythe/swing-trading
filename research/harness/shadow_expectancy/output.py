from __future__ import annotations

import csv
import io
import json
from pathlib import Path

RESULTS_HEADER = (
    "ticker", "detection_date", "run_id", "hypothesis", "bucket",
    "realistic_r", "favorable_r", "exit_reason", "open_at_horizon",
    "entry_bar_ambiguous", "entry_bar_weak_close",
)
PER_SESSION_HEADER = ("ticker", "hypothesis", "action", "qty", "price",
                      "price_favorable", "session")  # m3: both arms for terminal legs


def _assert_ascii(text: str) -> str:
    text.encode("ascii")  # spec section 8: ASCII-only (stricter than cp1252)
    return text


def _write_csv(header, rows, path: Path) -> None:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(header), lineterminator="\n",
                            extrasaction="ignore")
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
