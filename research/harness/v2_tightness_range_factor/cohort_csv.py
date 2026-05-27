"""V2 tightness_range_factor cohort CSV generator from V2 OHLCV sensitivity drill-down.

Parses a V2 sensitivity markdown artifact (e.g.,
`exports/diagnostics/aplus-sensitivity-v2-<ISO>.md`), extracts the
`### vcp.tightness_range_factor` drill-down table, filters to:

  - sweep_point == 1.005  (the binding +75 max_delta_aplus sweep_point
    per V2 sensitivity SUMMARY TABLE -- documented as the FIRST CANONICAL
    APPLICATION of gotcha #34 brief-prescription cross-table verification;
    the SUMMARY TABLE max_delta_aplus = 75 is the headline binding signal
    while the drill-down `watch -> aplus` filter at sp=1.005 yields exactly
    67 transition rows -- the 8-row gap is the V2 emitter's delta_aplus
    accounting picking up additional aplus-bucket churn beyond strict
    `watch -> aplus` transitions; see module docstring for full reconciliation)
  - old_bucket == 'watch'
  - new_bucket == 'aplus'

Deduplicates by (ticker, data_asof_date) to produce the input cohort CSV
for `pattern_cohort_evaluator`. Multiple eval_run_id rows for the same
(ticker, date) collapse to one entry because the pattern detector
operates on the asof_date snapshot of OHLCV bars; the eval_run_id is V1
audit-only metadata (the pipeline_run that originally produced the
candidate row). All raw flip records (including eval_run_id) are
persisted to a sibling `*.flips_audit.json` file so the V1 -> V2 tightness
cohort mapping is fully reproducible.

Per V2-selection-mechanic investigation dispatch brief Sec 2.1, the
2026-05-24 V2 sensitivity smoke artifact's vcp.tightness_range_factor
section at sweep_point=1.005 yields 67 flip records / 15 unique tickers /
29 unique (ticker, asof_date) tuples (YOU/DK/SSRM/WULF/TSHA/NAT/RLMD/
UCTT/PTEN/KOD/RNG/TROX/FRO/DNTH/OII).

COHORT-LEVEL TRANSFORMATION (inherited from R2-A + R2-D; gotcha #33 applies):
The 67 V2 flip events identify 15 candidate TICKERS at specific asof
snapshots. Downstream `pattern_cohort_evaluator` enumerates ALL Phase 13
chart-shape verdicts (windows) on those (ticker, asof) snapshots; the
analytical orchestration then dedupes by (ticker, trough_1_date) selecting
the highest-composite W primary verdict and applies a 5-BD adjacency
merge + canonical recency filter. The resulting investigation cohort
is therefore the population of HISTORICAL W patterns visible on the
V2-selected tickers at their flip-asof snapshots -- NOT the 67 V2 flip
events themselves. Findings doc / study writeup MUST surface this
transformation explicitly so claims of generalization are bounded
to "V2-selected ticker substrate evaluated through the canonical filter"
rather than to a broader population.

LOCKED PRECEDENT: this module does NOT reuse D1's hand-curated
`exports/research/cohorts/tightness_1.005_flips_67.csv` per dispatch
brief Sec 10. D1's CSV happens to share the 67-row count because it
extracted from the SAME source artifact via the SAME watch->aplus filter
at sp=1.005, but the V2-selection-mechanic investigation extracts
programmatically + locks the canonical layered verifier identity check;
the D1 CSV is a hand-curated artifact whose row identity is NOT
authoritative for this investigation.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable


V2TRF_COHORT_LABEL = "v2_vcp_tightness_range_factor_sp1_005"
V2TRF_VARIABLE_NAME = "vcp.tightness_range_factor"
# Binding sweep_point: the value that yields +75 max_delta_aplus per the
# V2 sensitivity SUMMARY TABLE (line 16 of canonical source MD).
# Float-valued; the parser coerces drill-down sweep_point cells via
# float() not int() to honor the table's numeric formatting (e.g., '1.005').
V2TRF_SWEEP_POINT = 1.005
V2TRF_OLD_BUCKET = "watch"
V2TRF_NEW_BUCKET = "aplus"

# Canonical source artifact SHA-256 + size (locked at write time);
# the regenerate_cohort entrypoint validates against this at run time
# (banked V2 candidate -- see R2-A return report section 6 R5.minor#1).
# IDENTICAL to R2-A + R2-D canonical SHA -- same source artifact.
CANONICAL_SOURCE_SHA256 = (
    "b25bcde944c33c7a44d049167e78e9d5c7b3d4fc5538ccc5e9cdc8e01e27a143"
)
CANONICAL_SOURCE_SIZE_BYTES = 830034

# Required column-name set in the V2 sensitivity drill-down table header.
# Parser validates ALL these names appear, then resolves indices by name
# (Codex R1 M#4 inherited from R2-A; defense against silent under-extraction
# if upstream V2 emitter inserts / removes / reorders columns).
_REQUIRED_COLUMNS = (
    "ticker",
    "eval_run_id",
    "data_asof_date",
    "sweep_point",
    "old_bucket",
    "new_bucket",
)

# Expected canonical counts for the 2026-05-24 V2 sensitivity smoke artifact
# vcp.tightness_range_factor section at sweep_point=1.005; strict validators
# check against these. These constants are the canonical truth-source for
# `verify_expected_v2trf_cohort` (Codex R2.M#1+#2 inherited from R2-A +
# R2-D: extended from counts-only to per-row identity for full content
# fidelity).
EXPECTED_FLIP_COUNT = 67
EXPECTED_UNIQUE_TICKER_ASOF = 29
EXPECTED_TICKERS = frozenset(
    {
        "YOU", "DK", "SSRM", "WULF", "TSHA", "NAT", "RLMD", "UCTT",
        "PTEN", "KOD", "RNG", "TROX", "FRO", "DNTH", "OII",
    }
)
# Canonical (ticker, asof_date) tuples expected post-dedup. Asserting
# the SET guarantees that no flipped asof_date corruption can pass
# count-only checks (Codex R2.M#1 inherited from R2-A + R2-D).
EXPECTED_TICKER_ASOF: frozenset[tuple[str, date]] = frozenset(
    {
        ("YOU", date(2026, 5, 22)),
        ("YOU", date(2026, 5, 18)),
        ("DK", date(2026, 5, 15)),
        ("SSRM", date(2026, 5, 15)),
        ("WULF", date(2026, 5, 15)),
        ("TSHA", date(2026, 5, 13)),
        ("NAT", date(2026, 5, 12)),
        ("RLMD", date(2026, 5, 12)),
        ("UCTT", date(2026, 5, 12)),
        ("RLMD", date(2026, 5, 11)),
        ("PTEN", date(2026, 5, 8)),
        ("RLMD", date(2026, 5, 4)),
        ("KOD", date(2026, 5, 1)),
        ("KOD", date(2026, 4, 30)),
        ("RLMD", date(2026, 4, 30)),
        ("RNG", date(2026, 4, 30)),
        ("KOD", date(2026, 4, 29)),
        ("RNG", date(2026, 4, 29)),
        ("TROX", date(2026, 4, 29)),
        ("FRO", date(2026, 4, 28)),
        ("RNG", date(2026, 4, 28)),
        ("YOU", date(2026, 4, 28)),
        ("DNTH", date(2026, 4, 27)),
        ("FRO", date(2026, 4, 27)),
        ("DNTH", date(2026, 4, 24)),
        ("RLMD", date(2026, 4, 24)),
        ("DNTH", date(2026, 4, 23)),
        ("RLMD", date(2026, 4, 23)),
        ("OII", date(2026, 4, 21)),
    }
)
# Canonical 67-tuple raw flip set (ticker, eval_run_id, asof_date)
# preserves per-eval_run audit identity. Asserting this set protects
# against eval_run_id mis-parse + ticker/asof tuple substitution
# (Codex R2.M#2 inherited from R2-A + R2-D). Implemented as frozenset
# because the canonical rows happen to be unique triples; if upstream
# V2 ever emits duplicate raw triples, the verifier's flip-COUNT check
# (layer 3) still fires.
EXPECTED_FLIPS: frozenset[tuple[str, int, date]] = frozenset(
    {
        ("YOU", 64, date(2026, 5, 22)),
        ("YOU", 57, date(2026, 5, 18)),
        ("YOU", 56, date(2026, 5, 18)),
        ("YOU", 55, date(2026, 5, 18)),
        ("DK", 54, date(2026, 5, 15)),
        ("DK", 53, date(2026, 5, 15)),
        ("SSRM", 52, date(2026, 5, 15)),
        ("WULF", 52, date(2026, 5, 15)),
        ("TSHA", 45, date(2026, 5, 13)),
        ("NAT", 44, date(2026, 5, 12)),
        ("RLMD", 44, date(2026, 5, 12)),
        ("UCTT", 44, date(2026, 5, 12)),
        ("RLMD", 43, date(2026, 5, 11)),
        ("RLMD", 42, date(2026, 5, 11)),
        ("PTEN", 41, date(2026, 5, 8)),
        ("PTEN", 40, date(2026, 5, 8)),
        ("RLMD", 33, date(2026, 5, 4)),
        ("KOD", 32, date(2026, 5, 1)),
        ("KOD", 31, date(2026, 5, 1)),
        ("KOD", 30, date(2026, 4, 30)),
        ("RLMD", 30, date(2026, 4, 30)),
        ("RNG", 30, date(2026, 4, 30)),
        ("KOD", 29, date(2026, 4, 30)),
        ("RLMD", 29, date(2026, 4, 30)),
        ("RNG", 29, date(2026, 4, 30)),
        ("KOD", 28, date(2026, 4, 29)),
        ("RNG", 28, date(2026, 4, 29)),
        ("TROX", 28, date(2026, 4, 29)),
        ("KOD", 27, date(2026, 4, 29)),
        ("RNG", 27, date(2026, 4, 29)),
        ("TROX", 27, date(2026, 4, 29)),
        ("KOD", 26, date(2026, 4, 29)),
        ("RNG", 26, date(2026, 4, 29)),
        ("TROX", 26, date(2026, 4, 29)),
        ("KOD", 25, date(2026, 4, 29)),
        ("RNG", 25, date(2026, 4, 29)),
        ("TROX", 25, date(2026, 4, 29)),
        ("FRO", 24, date(2026, 4, 28)),
        ("RNG", 24, date(2026, 4, 28)),
        ("YOU", 24, date(2026, 4, 28)),
        ("FRO", 23, date(2026, 4, 28)),
        ("RNG", 23, date(2026, 4, 28)),
        ("YOU", 23, date(2026, 4, 28)),
        ("FRO", 22, date(2026, 4, 28)),
        ("RNG", 22, date(2026, 4, 28)),
        ("YOU", 22, date(2026, 4, 28)),
        ("DNTH", 21, date(2026, 4, 27)),
        ("FRO", 21, date(2026, 4, 27)),
        ("DNTH", 20, date(2026, 4, 27)),
        ("FRO", 20, date(2026, 4, 27)),
        ("DNTH", 19, date(2026, 4, 27)),
        ("FRO", 19, date(2026, 4, 27)),
        ("DNTH", 18, date(2026, 4, 24)),
        ("RLMD", 18, date(2026, 4, 24)),
        ("DNTH", 17, date(2026, 4, 24)),
        ("RLMD", 17, date(2026, 4, 24)),
        ("DNTH", 16, date(2026, 4, 24)),
        ("RLMD", 16, date(2026, 4, 24)),
        ("DNTH", 15, date(2026, 4, 24)),
        ("RLMD", 15, date(2026, 4, 24)),
        ("DNTH", 14, date(2026, 4, 23)),
        ("RLMD", 14, date(2026, 4, 23)),
        ("DNTH", 13, date(2026, 4, 23)),
        ("RLMD", 13, date(2026, 4, 23)),
        ("DNTH", 12, date(2026, 4, 23)),
        ("OII", 10, date(2026, 4, 21)),
        ("OII", 9, date(2026, 4, 21)),
    }
)

# Anchored heading regex notes (Codex R2.M#4 inherited from R2-A + R2-D):
# _section_body constructs a per-call variable regex via re.escape(variable_name)
# so the helper is reusable across drill-down sections. The anchored
# regex matches `^### <variable>\s*$` MULTILINE; defends against
# inline prose substring matches AND longer-title h3 like
# `### vcp.tightness_range_factor (deprecated)`.
# NOTE: markdown triple-backtick code fences are NOT detected -- a
# heading-like line at start-of-line INSIDE a code block WILL be
# matched. The canonical defense against accidental in-code matches
# is the strict verifier (verify_expected_v2trf_cohort) downstream
# (Codex R3.M#2 ACCEPTED inherited from R2-A).
_H3_GENERIC_REGEX = re.compile(r"^### .+$", re.MULTILINE)
_H2_GENERIC_REGEX = re.compile(r"^## .+$", re.MULTILINE)

# Numeric-comparison tolerance for sweep_point coercion. Drill-down cells
# render the float as '1.005'; float() parses to 1.005 (no surprises with
# binary representation here because 1.005 has a well-defined float repr);
# math.isclose-style tolerance gives defense-in-depth if upstream V2 ever
# emits subtly different rendering ('1.0050', '1.00500', etc.).
_SWEEP_POINT_TOL = 1e-9


@dataclass(frozen=True)
class FlipRecord:
    """One row from the V2 sensitivity drill-down vcp.tightness_range_factor
    section filtered to sweep_point=1.005 + watch->aplus.

    eval_run_id is preserved for audit (per cumulative gotcha #15 + #23
    attribution metadata propagation); it is NOT used for cohort
    deduplication (multiple eval_runs on the same data_asof_date are
    by definition the same OHLCV snapshot at the asof-bar boundary).
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
    heading and the next h3 OR h2 heading line, whichever comes first.

    Boundary discipline (inherited from R2-A + R2-D; Codex R1.M#3 + R2.M#3 +
    R2.M#4 + R3.M#2-ACCEPTED):
      - Section start: MULTILINE-anchored regex matches ONLY a real h3
        heading line for the target variable.
      - Section end: the EARLIEST of (a) next h3 heading line, (b) next
        h2 heading line, (c) end-of-file. h4 (`#### ...`) and lower
        sub-headings INSIDE the section do NOT terminate parsing.
      - Codex R2.M#3 fix: independently compute next h2 + next h3.
    """
    variable_regex = re.compile(
        rf"^### {re.escape(variable_name)}\s*$", re.MULTILINE
    )
    start_match = variable_regex.search(text)
    if start_match is None:
        raise CohortExtractionError(
            f"V2 sensitivity artifact lacks the `### {variable_name}` "
            f"line-anchored heading; verify the artifact is a "
            f"full-reproduction smoke (not truncated) and the heading "
            f"appears at the start of a line. NOTE: the parser intentionally "
            f"does NOT implement markdown-code-fence detection -- a heading "
            f"line inside a triple-backtick code block WILL be matched. The "
            f"defense-in-depth against accidental in-prose / in-code matches "
            f"is the canonical strict verifier (verify_expected_v2trf_cohort), "
            f"which raises on any deviation from the 67-tuple multiset"
        )
    section_start = start_match.start()
    search_from = start_match.end()
    next_h3 = _H3_GENERIC_REGEX.search(text, search_from)
    next_h2 = _H2_GENERIC_REGEX.search(text, search_from)
    candidates = [m.start() for m in (next_h3, next_h2) if m is not None]
    if not candidates:
        return text[section_start:]
    section_end = min(candidates)
    return text[section_start:section_end]


def _parse_header_columns(line: str) -> dict[str, int]:
    """Parse a markdown table header row -> column-name -> index map.

    The map's indices are positions in the split-by-pipe list with
    leading/trailing empty cells already stripped.
    """
    cols = [c.strip() for c in line.split("|")]
    if cols and cols[0] == "":
        cols = cols[1:]
    if cols and cols[-1] == "":
        cols = cols[:-1]
    return {name: i for i, name in enumerate(cols)}


def extract_flips_from_sensitivity_md(md_path: Path) -> list[FlipRecord]:
    """Parse a V2 sensitivity markdown file + extract the
    vcp.tightness_range_factor watch->aplus flips at sweep_point=1.005.

    Column resolution is BY NAME (Codex R1 M#4 inherited from R2-A):
    the table header row is parsed first to build a column-name -> index
    map; subsequent data rows extract by name. If the table is missing
    any required column, raise CohortExtractionError.

    sweep_point is coerced via float() (NOT int()) because the V2
    drill-down emits the threshold_multiplicative sweep_point values
    as decimal floats (e.g., '1.005', '1.01', '1.015'). This matches
    R2-D's float coercion path; both paths handle their respective
    binding variables. A future common-parser refactor (V2 candidate
    per dispatch brief Sec 2.1) would parameterize the coercion.

    Raises:
        FileNotFoundError: when md_path does not exist.
        CohortExtractionError: when the file does not contain the
            `### vcp.tightness_range_factor` section, or when the
            drill-down table header is missing required columns.

    Returns flips in the order they appear in the markdown (per V2's
    descending eval_run_id ordering; preserves audit-trail ordering).
    """
    md_path = Path(md_path)
    if not md_path.exists():
        raise FileNotFoundError(f"V2 sensitivity artifact not found at {md_path}")

    text = md_path.read_text(encoding="utf-8")
    section_body = _section_body(text, V2TRF_VARIABLE_NAME)

    column_index: dict[str, int] | None = None
    for line in section_body.splitlines():
        if not line.startswith("|") or "---" in line:
            continue
        header = _parse_header_columns(line)
        if "ticker" in header:
            column_index = header
            break
    if column_index is None:
        raise CohortExtractionError(
            f"V2 sensitivity drill-down `{V2TRF_VARIABLE_NAME}` section "
            f"lacks a table header row; cannot extract flips by column name"
        )
    missing = [c for c in _REQUIRED_COLUMNS if c not in column_index]
    if missing:
        raise CohortExtractionError(
            f"V2 sensitivity drill-down `{V2TRF_VARIABLE_NAME}` section "
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
            sweep_point = float(cols[idx_sp])
            old_bucket = cols[idx_old]
            new_bucket = cols[idx_new]
        except (ValueError, IndexError):
            continue
        if abs(sweep_point - V2TRF_SWEEP_POINT) > _SWEEP_POINT_TOL:
            continue
        if old_bucket != V2TRF_OLD_BUCKET:
            continue
        if new_bucket != V2TRF_NEW_BUCKET:
            continue
        flips.append(
            FlipRecord(
                ticker=ticker,
                eval_run_id=eval_run_id,
                data_asof_date=asof_date,
            )
        )
    return flips


def verify_expected_v2trf_cohort(flips: list[FlipRecord]) -> None:
    """Assert the parsed flips match the canonical V2 tightness_range_factor
    cohort verbatim.

    Validates THREE layers (Codex R1.M#2 + R2.M#1 + R2.M#2 inherited from
    R2-A + R2-D):
      1. Raw flip multiset identity: every (ticker, eval_run_id,
         data_asof_date) triple must appear exactly once and the set
         must equal EXPECTED_FLIPS (67 entries).
      2. Unique (ticker, asof_date) tuple set: must equal
         EXPECTED_TICKER_ASOF (29 entries; defends against asof-date
         corruption that preserves count but flips a date).
      3. Aggregate counts: flip count == 67, ticker count == 15,
         unique pair count == 29 (sanity).

    Raises CohortExtractionError on any deviation.
    """
    parsed_flips = {
        (f.ticker, f.eval_run_id, f.data_asof_date) for f in flips
    }
    if parsed_flips != EXPECTED_FLIPS:
        missing = EXPECTED_FLIPS - parsed_flips
        extra = parsed_flips - EXPECTED_FLIPS
        raise CohortExtractionError(
            f"V2-TRF flip identity mismatch: missing={sorted(missing)}, "
            f"extra={sorted(extra)}. The parser produced a different raw "
            f"flip multiset than the canonical 67-tuple set; check the "
            f"V2 sensitivity artifact + parser logic"
        )
    pairs = {(f.ticker, f.data_asof_date) for f in flips}
    if pairs != EXPECTED_TICKER_ASOF:
        missing = EXPECTED_TICKER_ASOF - pairs
        extra = pairs - EXPECTED_TICKER_ASOF
        raise CohortExtractionError(
            f"V2-TRF (ticker, asof_date) set mismatch: missing={sorted(missing)}, "
            f"extra={sorted(extra)}"
        )
    if len(flips) != EXPECTED_FLIP_COUNT:
        raise CohortExtractionError(
            f"V2-TRF flip count mismatch: parsed {len(flips)} flips, "
            f"expected {EXPECTED_FLIP_COUNT}. Check for duplicates."
        )
    tickers = {f.ticker for f in flips}
    if tickers != EXPECTED_TICKERS:
        raise CohortExtractionError(
            f"V2-TRF ticker set mismatch: parsed {sorted(tickers)}, "
            f"expected {sorted(EXPECTED_TICKERS)}"
        )
    if len(pairs) != EXPECTED_UNIQUE_TICKER_ASOF:
        raise CohortExtractionError(
            f"V2-TRF unique (ticker, asof_date) count mismatch: parsed "
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
    unique.sort(key=lambda x: (-x[1].toordinal(), x[0]))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "asof_date", "cohort_label"])
        for ticker, asof in unique:
            w.writerow([ticker, asof.isoformat(), V2TRF_COHORT_LABEL])
    return len(unique)


def _sha256_of_file(path: Path) -> str:
    """Streaming SHA-256 hexdigest of a file (audit durability:
    source artifact identity locked alongside the path)."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def write_flips_audit_json(
    flips: Iterable[FlipRecord],
    output_path: Path,
    *,
    source_sensitivity_md: Path,
) -> int:
    """Emit a sibling audit JSON file alongside the cohort CSV preserving
    ALL 67 raw flip records (including eval_run_id) for V1 -> V2-TRF
    traceability (Codex R1 M#1 + minor #2 inherited from R2-A + R2-D).

    The cohort CSV emits the 29 unique (ticker, asof_date) tuples (the
    downstream `pattern_cohort_evaluator` input); this audit file
    preserves the per-eval_run granularity so an analyst can reconstruct
    which V1 pipeline_run(s) produced each cohort row.

    Returns the number of flip records persisted.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    src_path = Path(source_sensitivity_md)
    src_sha = _sha256_of_file(src_path) if src_path.exists() else None
    src_stat = src_path.stat() if src_path.exists() else None
    payload = {
        "source_sensitivity_md": Path(source_sensitivity_md).as_posix(),
        "source_sensitivity_md_sha256": src_sha,
        "source_sensitivity_md_size_bytes": (
            src_stat.st_size if src_stat else None
        ),
        "variable_name": V2TRF_VARIABLE_NAME,
        "sweep_point": V2TRF_SWEEP_POINT,
        "old_bucket": V2TRF_OLD_BUCKET,
        "new_bucket": V2TRF_NEW_BUCKET,
        "cohort_label": V2TRF_COHORT_LABEL,
        "cohort_selection_method": "v2_binding_variable_flips",
        "v2_binding_variable": V2TRF_VARIABLE_NAME,
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


@dataclass(frozen=True)
class CohortArtifacts:
    """Output paths + counts from a canonical V2-TRF cohort generation."""

    cohort_csv_path: Path
    flips_audit_json_path: Path
    unique_ticker_asof_count: int
    raw_flip_count: int


def verify_canonical_source_identity(source_sensitivity_md: Path) -> None:
    """Raise CohortExtractionError if the source file's SHA-256 or byte size
    does not match CANONICAL_SOURCE_SHA256 / CANONICAL_SOURCE_SIZE_BYTES.
    """
    source_sensitivity_md = Path(source_sensitivity_md)
    if not source_sensitivity_md.exists():
        raise FileNotFoundError(
            f"V2 sensitivity artifact not found at {source_sensitivity_md}"
        )
    actual_sha = _sha256_of_file(source_sensitivity_md)
    actual_size = source_sensitivity_md.stat().st_size
    if actual_sha != CANONICAL_SOURCE_SHA256:
        raise CohortExtractionError(
            f"Source artifact SHA-256 mismatch at {source_sensitivity_md}: "
            f"actual={actual_sha} vs canonical={CANONICAL_SOURCE_SHA256}. "
            f"To regenerate cohort against a non-canonical source, pass "
            f"allow_non_canonical_source=True (cohort identity will still be "
            f"verified via EXPECTED_FLIPS layered verifier)."
        )
    if actual_size != CANONICAL_SOURCE_SIZE_BYTES:
        raise CohortExtractionError(
            f"Source artifact size mismatch at {source_sensitivity_md}: "
            f"actual={actual_size} bytes vs canonical={CANONICAL_SOURCE_SIZE_BYTES} bytes"
        )


def generate_v2trf_cohort_artifacts(
    *,
    source_sensitivity_md: Path,
    cohort_csv_path: Path,
    flips_audit_json_path: Path | None = None,
    allow_non_canonical_source: bool = False,
) -> CohortArtifacts:
    """Canonical one-call V2-TRF cohort generation pipeline.

    Sequence (Codex R2.M#6 + R3.M#3 inherited from R2-A + R1.M#5 R2-D-local):
      1. verify_canonical_source_identity(source_sensitivity_md) UNLESS
         allow_non_canonical_source=True
      2. extract_flips_from_sensitivity_md(source_sensitivity_md)
      3. verify_expected_v2trf_cohort(flips) -- ALWAYS fires
      4. write_cohort_csv(flips, cohort_csv_path)
      5. write_flips_audit_json(flips, audit_path, source_sensitivity_md=...)

    The audit JSON path defaults to `<cohort_csv_path>.flips_audit.json`.

    Returns a CohortArtifacts dataclass with paths + counts. Raises
    CohortExtractionError on any deviation from the canonical 67/15/29
    cohort.

    Parameters:
        allow_non_canonical_source: when True, skip the source SHA + size
            check. The cohort-identity layered verifier still fires.
    """
    cohort_csv_path = Path(cohort_csv_path)
    if flips_audit_json_path is None:
        flips_audit_json_path = cohort_csv_path.with_suffix(".flips_audit.json")
    flips_audit_json_path = Path(flips_audit_json_path)
    if not allow_non_canonical_source:
        verify_canonical_source_identity(source_sensitivity_md)
    flips = extract_flips_from_sensitivity_md(source_sensitivity_md)
    verify_expected_v2trf_cohort(flips)
    n_unique = write_cohort_csv(flips, cohort_csv_path)
    n_audit = write_flips_audit_json(
        flips, flips_audit_json_path, source_sensitivity_md=source_sensitivity_md
    )
    return CohortArtifacts(
        cohort_csv_path=cohort_csv_path,
        flips_audit_json_path=flips_audit_json_path,
        unique_ticker_asof_count=n_unique,
        raw_flip_count=n_audit,
    )
