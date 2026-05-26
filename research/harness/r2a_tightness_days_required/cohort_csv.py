"""R2-A cohort CSV generator from V2 OHLCV sensitivity drill-down.

Parses a V2 sensitivity markdown artifact (e.g.,
`exports/diagnostics/aplus-sensitivity-v2-<ISO>.md`), extracts the
`### vcp.tightness_days_required` drill-down table, filters to:

  - sweep_point == 1
  - old_bucket == 'watch'
  - new_bucket == 'aplus'

Deduplicates by (ticker, data_asof_date) to produce the input cohort CSV
for `pattern_cohort_detect`. Multiple eval_run_id rows for the same
(ticker, date) collapse to one entry because the pattern detector
operates on the asof_date snapshot of OHLCV bars; the eval_run_id is V1
audit-only metadata (the pipeline_run that originally produced the
candidate row). All raw flip records (including eval_run_id) are
persisted to a sibling `*.flips_audit.json` file so the V1->R2-A
cohort mapping is fully reproducible.

Per dispatch brief, the V2 sensitivity 20260524T205849Z artifact's
vcp.tightness_days_required section yields 15 flip records / 7 unique
tickers / 7 unique (ticker, asof_date) tuples (FRO/KOD/NAT/OII/RLMD/SEI/TROX).

COHORT-LEVEL TRANSFORMATION (Codex R1 M#5 + M#7 clarification):
The 15 V2 flip events identify 7 candidate TICKERS at specific asof
snapshots. Downstream `pattern_cohort_detect` enumerates ALL Phase 13
chart-shape verdicts (windows) on those (ticker, asof) snapshots; the
D1 cohort extractor then dedupes by (ticker, trough_1_date) selecting
the highest-composite W primary verdict and applies a 5-BD adjacency
merge + recency filter. The resulting backtest cohort is therefore
the population of HISTORICAL W patterns visible on the V2-selected
tickers at their flip-asof snapshots -- NOT the 15 V2 flip events
themselves. Findings doc / study writeup MUST surface this
transformation explicitly so claims of generalization are bounded
to "V2-selected ticker substrate evaluated through the D2 walk-forward
pipeline" rather than to a broader population.

Forward-binding note: cumulative gotcha #33 (cohort-validity-vs-verdict-criteria)
is applied at the manifest + findings layer (NOT here): this module
produces the bias-CHARACTERIZED cohort (`v2_binding_variable_flips`)
and downstream consumers (manifest, study writeup) MUST document the
cohort selection method explicitly.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Iterable


R2A_COHORT_LABEL = "r2a_vcp_tightness_days_required_sp1"
R2A_VARIABLE_NAME = "vcp.tightness_days_required"
R2A_SWEEP_POINT = 1
R2A_OLD_BUCKET = "watch"
R2A_NEW_BUCKET = "aplus"

# Required column-name set in the V2 sensitivity drill-down table header.
# Parser validates ALL these names appear, then resolves indices by name
# (Codex R1 M#4: defense against silent under-extraction if upstream V2
# emitter inserts / removes / reorders columns).
_REQUIRED_COLUMNS = (
    "ticker",
    "eval_run_id",
    "data_asof_date",
    "sweep_point",
    "old_bucket",
    "new_bucket",
)

# Expected canonical counts for the 2026-05-24 V2 sensitivity smoke artifact;
# strict validators below check against these. These constants are the
# canonical truth-source for `verify_expected_r2a_cohort`.
EXPECTED_FLIP_COUNT = 15
EXPECTED_UNIQUE_TICKER_ASOF = 7
EXPECTED_TICKERS = frozenset(
    {"FRO", "KOD", "NAT", "OII", "RLMD", "SEI", "TROX"}
)


@dataclass(frozen=True)
class FlipRecord:
    """One row from the V2 sensitivity drill-down vcp.tightness_days_required
    section filtered to sweep_point=1 + watch->aplus.

    eval_run_id is preserved for audit (per gotcha #15 + #23 attribution
    metadata propagation); it is NOT used for cohort deduplication
    (multiple eval_runs on the same data_asof_date are by definition
    the same OHLCV snapshot at the asof-bar boundary).
    """

    ticker: str
    eval_run_id: int
    data_asof_date: date


class CohortExtractionError(ValueError):
    """Raised when the V2 sensitivity drill-down cannot be parsed safely.

    Distinct from ValueError so callers (CLI / tests / findings doc
    pipelines) can catch this specifically without swallowing unrelated
    ValueError instances from downstream date / int parsing.
    """


def _section_body(text: str, variable_name: str) -> str:
    """Slice the drill-down section bounded by the `### variable_name`
    heading and the NEXT `### ` heading at the SAME level (NOT a 4+ hash
    sub-heading; NOT a 2-hash major heading).

    Codex R1 M#3 defense: explicit boundary detection on heading-level 3
    so nested `#### ...` sub-headings inside the variable's section do
    not prematurely terminate the body.
    """
    section_marker = f"### {variable_name}"
    section_start = text.find(section_marker)
    if section_start < 0:
        raise CohortExtractionError(
            f"V2 sensitivity artifact lacks the `{section_marker}` "
            f"section; verify the artifact is a full-reproduction smoke "
            f"(not truncated)"
        )
    # Walk forward; the next h3 boundary is the NEXT line that starts with
    # exactly `### ` (3 hashes + space) and NOT `#### ` (4 hashes); also
    # accept end-of-file or the next `## ` h2 boundary which would
    # never appear inside a properly-formed drill-down section.
    cursor = section_start + len(section_marker)
    while True:
        nxt_h3 = text.find("\n### ", cursor)
        # Must not be a `#### `: check the character at nxt_h3+5 isn't `#`
        if nxt_h3 < 0:
            return text[section_start:]
        if nxt_h3 + 5 < len(text) and text[nxt_h3 + 5] == "#":
            # The match is actually `\n#### ...` (4-hash sub-heading);
            # continue searching past this match
            cursor = nxt_h3 + 5
            continue
        # Also bound by the next h2 if it appears before the next h3
        nxt_h2 = text.find("\n## ", section_start + len(section_marker))
        if 0 <= nxt_h2 < nxt_h3:
            return text[section_start:nxt_h2]
        return text[section_start:nxt_h3]


def _parse_header_columns(line: str) -> dict[str, int]:
    """Parse a markdown table header row -> column-name -> index map.

    The map's indices are positions in the split-by-pipe list with
    leading/trailing empty cells already stripped.
    """
    cols = [c.strip() for c in line.split("|")]
    # Drop leading/trailing empty cells from `|...|` delimiters
    if cols and cols[0] == "":
        cols = cols[1:]
    if cols and cols[-1] == "":
        cols = cols[:-1]
    return {name: i for i, name in enumerate(cols)}


def extract_flips_from_sensitivity_md(md_path: Path) -> list[FlipRecord]:
    """Parse a V2 sensitivity markdown file + extract the
    vcp.tightness_days_required watch->aplus flips at sweep_point=1.

    Column resolution is BY NAME (Codex R1 M#4 defense): the table header
    row is parsed first to build a column-name -> index map; subsequent
    data rows extract by name. If the table is missing any required
    column, raise CohortExtractionError.

    Raises:
        FileNotFoundError: when md_path does not exist.
        CohortExtractionError: when the file does not contain the
            `### vcp.tightness_days_required` section, or when the
            drill-down table header is missing required columns.

    Returns flips in the order they appear in the markdown (per V2's
    descending eval_run_id ordering; preserves audit-trail ordering).
    """
    md_path = Path(md_path)
    if not md_path.exists():
        raise FileNotFoundError(f"V2 sensitivity artifact not found at {md_path}")

    text = md_path.read_text(encoding="utf-8")
    section_body = _section_body(text, R2A_VARIABLE_NAME)

    # Locate the first table-header row inside the section; abort if
    # required columns are missing (defense against schema drift).
    column_index: dict[str, int] | None = None
    for line in section_body.splitlines():
        if not line.startswith("|") or "---" in line:
            continue
        header = _parse_header_columns(line)
        # A header has at least the `ticker` column literally
        if "ticker" in header:
            column_index = header
            break
    if column_index is None:
        raise CohortExtractionError(
            f"V2 sensitivity drill-down `{R2A_VARIABLE_NAME}` section "
            f"lacks a table header row; cannot extract flips by column name"
        )
    missing = [c for c in _REQUIRED_COLUMNS if c not in column_index]
    if missing:
        raise CohortExtractionError(
            f"V2 sensitivity drill-down `{R2A_VARIABLE_NAME}` section "
            f"table header missing required columns: {missing}; "
            f"upstream V2 emitter may have changed shape; check "
            f"research/harness/aplus_v2_ohlcv_evaluator/output.py"
        )
    idx_ticker = column_index["ticker"]
    idx_eval_run = column_index["eval_run_id"]
    idx_asof = column_index["data_asof_date"]
    idx_sp = column_index["sweep_point"]
    idx_old = column_index["old_bucket"]
    idx_new = column_index["new_bucket"]

    flips: list[FlipRecord] = []
    seen_header = False
    for line in section_body.splitlines():
        line_s = line.strip()
        if not line_s.startswith("|"):
            continue
        if "---" in line_s:
            continue
        if not seen_header:
            # Skip exactly the header line we already parsed
            if "ticker" in line_s:
                seen_header = True
                continue
            continue
        cols = [c.strip() for c in line_s.split("|")]
        if cols and cols[0] == "":
            cols = cols[1:]
        if cols and cols[-1] == "":
            cols = cols[:-1]
        max_required_idx = max(
            idx_ticker, idx_eval_run, idx_asof, idx_sp, idx_old, idx_new
        )
        if len(cols) <= max_required_idx:
            continue
        try:
            ticker = cols[idx_ticker].upper()
            eval_run_id = int(cols[idx_eval_run])
            asof_date = date.fromisoformat(cols[idx_asof])
            sweep_point = int(cols[idx_sp])
            old_bucket = cols[idx_old]
            new_bucket = cols[idx_new]
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


def verify_expected_r2a_cohort(flips: list[FlipRecord]) -> None:
    """Assert the parsed flips match the expected R2-A cohort canonical
    counts (Codex R1 M#2 defense against silent under-extraction).

    The expected canonical counts target the 2026-05-24 V2 sensitivity
    smoke artifact. Any deviation indicates either (a) the upstream V2
    emitter changed table shape, (b) the artifact was truncated, or
    (c) the parser regressed.

    Raises CohortExtractionError on any deviation.
    """
    if len(flips) != EXPECTED_FLIP_COUNT:
        raise CohortExtractionError(
            f"R2-A flip count mismatch: parsed {len(flips)} flips, "
            f"expected {EXPECTED_FLIP_COUNT} from the 2026-05-24 V2 "
            f"sensitivity smoke artifact. Check parser + artifact."
        )
    tickers = {f.ticker for f in flips}
    if tickers != EXPECTED_TICKERS:
        raise CohortExtractionError(
            f"R2-A ticker set mismatch: parsed {sorted(tickers)}, "
            f"expected {sorted(EXPECTED_TICKERS)}"
        )
    pairs = {(f.ticker, f.data_asof_date) for f in flips}
    if len(pairs) != EXPECTED_UNIQUE_TICKER_ASOF:
        raise CohortExtractionError(
            f"R2-A unique (ticker, asof_date) count mismatch: parsed "
            f"{len(pairs)}, expected {EXPECTED_UNIQUE_TICKER_ASOF}"
        )


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


def write_flips_audit_json(
    flips: Iterable[FlipRecord],
    output_path: Path,
    *,
    source_sensitivity_md: Path,
) -> int:
    """Emit a sibling audit JSON file alongside the cohort CSV preserving
    ALL 15 raw flip records (including eval_run_id) for V1->R2-A
    traceability (Codex R1 M#1 + minor #2 defense).

    The cohort CSV emits the 7 unique (ticker, asof_date) tuples (the
    backtest's actual input); this audit file preserves the per-eval_run
    granularity so an analyst can reconstruct which V1 pipeline_run(s)
    produced each cohort row.

    Returns the number of flip records persisted.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_sensitivity_md": str(source_sensitivity_md),
        "variable_name": R2A_VARIABLE_NAME,
        "sweep_point": R2A_SWEEP_POINT,
        "old_bucket": R2A_OLD_BUCKET,
        "new_bucket": R2A_NEW_BUCKET,
        "cohort_label": R2A_COHORT_LABEL,
        "flip_count": 0,
        "flips": [],
    }
    flip_list = list(flips)
    payload["flip_count"] = len(flip_list)
    payload["flips"] = [
        {
            "ticker": f.ticker,
            "eval_run_id": f.eval_run_id,
            "data_asof_date": f.data_asof_date.isoformat(),
        }
        for f in flip_list
    ]
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return len(flip_list)
