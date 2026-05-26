"""R2-A cohort CSV generator from V2 OHLCV sensitivity drill-down.

Parses a V2 sensitivity markdown artifact (e.g.,
`exports/diagnostics/aplus-sensitivity-v2-<ISO>.md`), extracts the
`### vcp.tightness_days_required` drill-down table, filters to:

  - sweep_point == 1
  - old_bucket == 'watch'
  - new_bucket == 'aplus'

Deduplicates by (ticker, data_asof_date) to produce the input cohort CSV
for `pattern_cohort_detect`. Multiple eval_run_id rows for the same
(ticker, date) collapse to one entry (eval_run_id is V1 audit-only; the
pattern detector operates on the asof_date snapshot of OHLCV).

Per dispatch brief, the V2 sensitivity 20260524T205849Z artifact's
vcp.tightness_days_required section yields 15 flip records / 7 unique
tickers / 7 unique (ticker, asof_date) tuples (FRO/KOD/NAT/OII/RLMD/SEI/TROX).

Forward-binding note: cumulative gotcha #33 (cohort-validity-vs-verdict-criteria)
is applied at the manifest+findings layer (NOT here): this module produces
the bias-CHARACTERIZED cohort (`v2_binding_variable_flips`) and downstream
consumers (manifest, study writeup) MUST document the cohort selection
method explicitly.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable


R2A_COHORT_LABEL = "r2a_vcp_tightness_days_required_sp1"
R2A_VARIABLE_NAME = "vcp.tightness_days_required"
R2A_SWEEP_POINT = 1
R2A_OLD_BUCKET = "watch"
R2A_NEW_BUCKET = "aplus"


@dataclass(frozen=True)
class FlipRecord:
    """One row from the V2 sensitivity drill-down vcp.tightness_days_required
    section filtered to sweep_point=1 + watch->aplus.

    eval_run_id is preserved for audit (per gotcha #15 + #23 attribution
    metadata propagation); it is NOT used for cohort deduplication
    (multiple eval_runs on the same data_asof_date are by definition
    the same OHLCV snapshot).
    """

    ticker: str
    eval_run_id: int
    data_asof_date: date


def extract_flips_from_sensitivity_md(md_path: Path) -> list[FlipRecord]:
    """Parse a V2 sensitivity markdown file + extract the
    vcp.tightness_days_required watch->aplus flips at sweep_point=1.

    Raises:
        FileNotFoundError: when md_path does not exist.
        ValueError: when the file does not contain the
            `### vcp.tightness_days_required` section (per cumulative
            gotcha discipline against silent-empty-result anti-pattern).

    Returns flips in the order they appear in the markdown (per V2's
    descending eval_run_id ordering; preserves audit-trail ordering).
    """
    md_path = Path(md_path)
    if not md_path.exists():
        raise FileNotFoundError(f"V2 sensitivity artifact not found at {md_path}")

    text = md_path.read_text(encoding="utf-8")
    section_marker = f"### {R2A_VARIABLE_NAME}"
    section_start = text.find(section_marker)
    if section_start < 0:
        raise ValueError(
            f"V2 sensitivity artifact at {md_path} lacks the "
            f"`{section_marker}` section; verify the artifact is a "
            f"full-reproduction smoke (not truncated)"
        )
    # Find the next `### ` heading boundary OR end-of-file
    after_section = text.find("\n### ", section_start + len(section_marker))
    if after_section < 0:
        after_section = len(text)
    section_body = text[section_start:after_section]

    flips: list[FlipRecord] = []
    for line in section_body.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        # Skip header rows and the markdown separator row
        if "---" in line:
            continue
        if "ticker" in line and "eval_run_id" in line:
            continue
        # Parse pipe-delimited columns
        cols = [c.strip() for c in line.split("|")]
        # Leading + trailing empty cols from |..| delimiters; need >= 8 mid cols
        if len(cols) < 9:
            continue
        # cols[0]='' cols[1]=ticker cols[2]=eval_run_id cols[3]=asof
        # cols[4]=sweep_point cols[5]=old_bucket cols[6]=new_bucket ...
        try:
            ticker = cols[1]
            eval_run_id = int(cols[2])
            asof_date = date.fromisoformat(cols[3])
            sweep_point = int(cols[4])
            old_bucket = cols[5]
            new_bucket = cols[6]
        except (ValueError, IndexError):
            continue
        if sweep_point != R2A_SWEEP_POINT:
            continue
        if old_bucket != R2A_OLD_BUCKET:
            continue
        if new_bucket != R2A_NEW_BUCKET:
            continue
        flips.append(
            FlipRecord(
                ticker=ticker,
                eval_run_id=eval_run_id,
                data_asof_date=asof_date,
            )
        )
    return flips


def write_cohort_csv(flips: Iterable[FlipRecord], output_path: Path) -> int:
    """Emit cohort CSV with header `ticker,asof_date,cohort_label` and
    one row per unique (ticker, asof_date) pair (eval_run_id ignored
    for dedup).

    Returns the number of unique rows written. Output is sorted by
    asof_date desc, then ticker asc, for deterministic ordering across
    runs (matches V1 audit-stability discipline).
    """
    output_path = Path(output_path)
    seen: set[tuple[str, date]] = set()
    unique: list[tuple[str, date]] = []
    for f in flips:
        key = (f.ticker, f.data_asof_date)
        if key in seen:
            continue
        seen.add(key)
        unique.append(key)
    # Sort: asof_date desc, ticker asc -- stable, audit-friendly
    unique.sort(key=lambda x: (-x[1].toordinal(), x[0]))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "asof_date", "cohort_label"])
        for ticker, asof in unique:
            w.writerow([ticker, asof.isoformat(), R2A_COHORT_LABEL])
    return len(unique)
