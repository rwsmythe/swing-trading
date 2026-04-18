"""One-shot: read legacy evaluation.csv files and capture bucket-per-ticker as JSON.

Produces tests/fixtures/parity-baseline.json from existing reports/<YYYY-MM-DD>/evaluation.csv.

Legacy column mapping (verified against reports/2026-04-16/evaluation.csv):
- 'ticker' -> ticker
- 'status' -> bucket (values: 'aplus', 'watch', 'skip', 'error')
  Note: legacy has no 'excluded' — ETF tickers were simply dropped from the CSV.
"""
from __future__ import annotations

import csv as csv_stdlib
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "finviz"
BASELINE_PATH = Path(__file__).parent / "parity-baseline.json"
REPORTS_DIR = PROJECT_ROOT / "reports"

_FN_RE = re.compile(
    r"^finviz(?P<day>\d{1,2})(?P<month>[A-Za-z]{3})(?P<year>\d{4})", re.IGNORECASE
)
_MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def _csv_to_iso_date(finviz_name: str) -> str | None:
    m = _FN_RE.match(finviz_name)
    if not m:
        return None
    day = int(m.group("day"))
    mon = _MONTHS.get(m.group("month").lower())
    year = m.group("year")
    if not mon:
        return None
    return f"{year}-{mon}-{day:02d}"


def _load_legacy_bucket_map(eval_csv: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    with open(eval_csv, newline="", encoding="utf-8") as f:
        reader = csv_stdlib.DictReader(f)
        fieldnames_lower = [fn.lower() for fn in (reader.fieldnames or [])]

        ticker_idx = next(
            (i for i, n in enumerate(fieldnames_lower) if n == "ticker"), None
        )
        bucket_idx = next(
            (i for i, n in enumerate(fieldnames_lower) if n in ("status", "bucket")),
            None,
        )
        if ticker_idx is None or bucket_idx is None:
            raise ValueError(
                f"{eval_csv}: expected 'ticker' and 'status' (or 'bucket') columns; "
                f"got {reader.fieldnames}"
            )

        ticker_key = (reader.fieldnames or [])[ticker_idx]
        bucket_key = (reader.fieldnames or [])[bucket_idx]
        for row in reader:
            t = (row.get(ticker_key) or "").strip().upper()
            b = (row.get(bucket_key) or "").strip().lower()
            if t and b:
                result[t] = b
    return result


def main() -> None:
    baseline: dict[str, dict[str, str]] = {}
    for csv_file in sorted(FIXTURES.glob("finviz*.csv")):
        iso = _csv_to_iso_date(csv_file.name)
        if iso is None:
            print(f"  {csv_file.name}: could not parse date - skipping")
            continue
        report_dir = REPORTS_DIR / iso
        eval_csv = report_dir / "evaluation.csv"
        if not eval_csv.exists():
            print(f"  {csv_file.name}: no legacy report at {eval_csv} - skipping")
            continue
        try:
            baseline[csv_file.name] = _load_legacy_bucket_map(eval_csv)
            print(
                f"  {csv_file.name}: captured {len(baseline[csv_file.name])} tickers "
                f"from {eval_csv}"
            )
        except Exception as exc:
            print(f"  {csv_file.name}: failed to parse - {exc}")

    BASELINE_PATH.write_text(
        json.dumps(baseline, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"Wrote {BASELINE_PATH} with {len(baseline)} CSV(s)")


if __name__ == "__main__":
    main()
