"""V2 orderliness_max_bar_ratio cohort CSV generator.

Parses a V2 sensitivity markdown artifact, extracts the
`### vcp.orderliness_max_bar_ratio` drill-down table, filters to:

  - sweep_point == 3.75  (binding +1 max_delta_aplus per V2 sensitivity
    SUMMARY TABLE; FIRST CROSSING convention LOCK per dispatch brief
    Sec 2.3 -- sp=4.5 also yields +1 with IDENTICAL flip set but
    sp=3.75 is the canonical lower threshold)
  - old_bucket == 'watch'
  - new_bucket == 'aplus'

Per dispatch brief Sec 2.3, the 2026-05-24 V2 sensitivity smoke artifact's
vcp.orderliness_max_bar_ratio section at sweep_point=3.75 yields 1 flip
record / 1 unique ticker / 1 unique (ticker, asof_date) tuple
(LASR:52:2026-05-15).
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


V2OBR_COHORT_LABEL = "v2_vcp_orderliness_max_bar_ratio_sp3_75"
V2OBR_VARIABLE_NAME = "vcp.orderliness_max_bar_ratio"
V2OBR_SWEEP_POINT = 3.75
V2OBR_OLD_BUCKET = "watch"
V2OBR_NEW_BUCKET = "aplus"

# Secondary sweep_point that yields IDENTICAL flip set per dispatch brief
# Sec 2.3 (sp=4.5 also crosses +1 delta_aplus); LOCK is sp=3.75 by
# "first crossing" convention. Discriminating test in the sibling test
# module verifies the LOCK against the secondary value.
SECONDARY_SAME_FLIPS_SWEEP_POINT = 4.5

CANONICAL_SOURCE_SHA256 = (
    "b25bcde944c33c7a44d049167e78e9d5c7b3d4fc5538ccc5e9cdc8e01e27a143"
)
CANONICAL_SOURCE_SIZE_BYTES = 830034

_REQUIRED_COLUMNS = (
    "ticker",
    "eval_run_id",
    "data_asof_date",
    "sweep_point",
    "old_bucket",
    "new_bucket",
)

EXPECTED_FLIP_COUNT = 1
EXPECTED_UNIQUE_TICKER_ASOF = 1
EXPECTED_TICKERS = frozenset({"LASR"})
EXPECTED_TICKER_ASOF: frozenset[tuple[str, date]] = frozenset(
    {("LASR", date(2026, 5, 15))}
)
EXPECTED_FLIPS: frozenset[tuple[str, int, date]] = frozenset(
    {("LASR", 52, date(2026, 5, 15))}
)

_H3_GENERIC_REGEX = re.compile(r"^### .+$", re.MULTILINE)
_H2_GENERIC_REGEX = re.compile(r"^## .+$", re.MULTILINE)
_SWEEP_POINT_TOL = 1e-9


@dataclass(frozen=True)
class FlipRecord:
    ticker: str
    eval_run_id: int
    data_asof_date: date


class CohortExtractionError(ValueError):
    """Raised when the V2 sensitivity drill-down cannot be parsed safely."""


def _section_body(text: str, variable_name: str) -> str:
    variable_regex = re.compile(
        rf"^### {re.escape(variable_name)}\s*$", re.MULTILINE
    )
    start_match = variable_regex.search(text)
    if start_match is None:
        raise CohortExtractionError(
            f"V2 sensitivity artifact lacks the `### {variable_name}` "
            f"line-anchored heading"
        )
    section_start = start_match.start()
    search_from = start_match.end()
    next_h3 = _H3_GENERIC_REGEX.search(text, search_from)
    next_h2 = _H2_GENERIC_REGEX.search(text, search_from)
    candidates = [m.start() for m in (next_h3, next_h2) if m is not None]
    if not candidates:
        return text[section_start:]
    return text[section_start : min(candidates)]


def _parse_header_columns(line: str) -> dict[str, int]:
    cols = [c.strip() for c in line.split("|")]
    if cols and cols[0] == "":
        cols = cols[1:]
    if cols and cols[-1] == "":
        cols = cols[:-1]
    return {name: i for i, name in enumerate(cols)}


def _extract_flips_at_sweep_point(
    md_path: Path, target_sweep_point: float
) -> list[FlipRecord]:
    """Helper: extract watch->aplus flips at a specified sweep_point.

    Public callers should use extract_flips_from_sensitivity_md (which
    locks target_sweep_point=V2OBR_SWEEP_POINT). This helper exists for
    the sp=3.75-vs-sp=4.5 discriminating test in the sibling test module
    (per dispatch brief Sec 2.3 first-crossing LOCK).
    """
    md_path = Path(md_path)
    if not md_path.exists():
        raise FileNotFoundError(f"V2 sensitivity artifact not found at {md_path}")

    text = md_path.read_text(encoding="utf-8")
    section_body = _section_body(text, V2OBR_VARIABLE_NAME)

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
            f"V2 sensitivity drill-down `{V2OBR_VARIABLE_NAME}` section "
            f"lacks a table header row"
        )
    missing = [c for c in _REQUIRED_COLUMNS if c not in column_index]
    if missing:
        raise CohortExtractionError(
            f"V2 sensitivity drill-down `{V2OBR_VARIABLE_NAME}` table "
            f"header missing required columns: {missing}"
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
        if abs(sweep_point - target_sweep_point) > _SWEEP_POINT_TOL:
            continue
        if old_bucket != V2OBR_OLD_BUCKET:
            continue
        if new_bucket != V2OBR_NEW_BUCKET:
            continue
        flips.append(
            FlipRecord(
                ticker=ticker,
                eval_run_id=eval_run_id,
                data_asof_date=asof_date,
            )
        )
    return flips


def extract_flips_from_sensitivity_md(md_path: Path) -> list[FlipRecord]:
    """Extract vcp.orderliness_max_bar_ratio watch->aplus flips at sp=3.75."""
    return _extract_flips_at_sweep_point(md_path, V2OBR_SWEEP_POINT)


def verify_expected_v2obr_cohort(flips: list[FlipRecord]) -> None:
    """3-layer verifier."""
    parsed_flips = {(f.ticker, f.eval_run_id, f.data_asof_date) for f in flips}
    if parsed_flips != EXPECTED_FLIPS:
        missing = EXPECTED_FLIPS - parsed_flips
        extra = parsed_flips - EXPECTED_FLIPS
        raise CohortExtractionError(
            f"V2-OBR flip identity mismatch: missing={sorted(missing)}, "
            f"extra={sorted(extra)}"
        )
    pairs = {(f.ticker, f.data_asof_date) for f in flips}
    if pairs != EXPECTED_TICKER_ASOF:
        missing = EXPECTED_TICKER_ASOF - pairs
        extra = pairs - EXPECTED_TICKER_ASOF
        raise CohortExtractionError(
            f"V2-OBR (ticker, asof_date) set mismatch: missing={sorted(missing)}, "
            f"extra={sorted(extra)}"
        )
    if len(flips) != EXPECTED_FLIP_COUNT:
        raise CohortExtractionError(
            f"V2-OBR flip count mismatch: parsed {len(flips)}, "
            f"expected {EXPECTED_FLIP_COUNT}"
        )
    tickers = {f.ticker for f in flips}
    if tickers != EXPECTED_TICKERS:
        raise CohortExtractionError(
            f"V2-OBR ticker set mismatch: parsed {sorted(tickers)}, "
            f"expected {sorted(EXPECTED_TICKERS)}"
        )
    if len(pairs) != EXPECTED_UNIQUE_TICKER_ASOF:
        raise CohortExtractionError(
            f"V2-OBR unique pair count mismatch: parsed {len(pairs)}, "
            f"expected {EXPECTED_UNIQUE_TICKER_ASOF}"
        )


def write_cohort_csv(flips: Iterable[FlipRecord], output_path: Path) -> int:
    """Emit cohort CSV."""
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
            w.writerow([ticker, asof.isoformat(), V2OBR_COHORT_LABEL])
    return len(unique)


def _sha256_of_file(path: Path) -> str:
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
    """Emit sibling audit JSON."""
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
        "variable_name": V2OBR_VARIABLE_NAME,
        "sweep_point": V2OBR_SWEEP_POINT,
        "old_bucket": V2OBR_OLD_BUCKET,
        "new_bucket": V2OBR_NEW_BUCKET,
        "cohort_label": V2OBR_COHORT_LABEL,
        "cohort_selection_method": "v2_binding_variable_flips",
        "v2_binding_variable": V2OBR_VARIABLE_NAME,
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
    cohort_csv_path: Path
    flips_audit_json_path: Path
    unique_ticker_asof_count: int
    raw_flip_count: int


def verify_canonical_source_identity(source_sensitivity_md: Path) -> None:
    """SHA-256 + byte-size identity check."""
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
            f"actual={actual_sha} vs canonical={CANONICAL_SOURCE_SHA256}"
        )
    if actual_size != CANONICAL_SOURCE_SIZE_BYTES:
        raise CohortExtractionError(
            f"Source artifact size mismatch at {source_sensitivity_md}: "
            f"actual={actual_size} bytes vs canonical={CANONICAL_SOURCE_SIZE_BYTES} bytes"
        )


def generate_v2obr_cohort_artifacts(
    *,
    source_sensitivity_md: Path,
    cohort_csv_path: Path,
    flips_audit_json_path: Path | None = None,
    allow_non_canonical_source: bool = False,
) -> CohortArtifacts:
    """Canonical one-call V2-OBR cohort generation pipeline."""
    cohort_csv_path = Path(cohort_csv_path)
    if flips_audit_json_path is None:
        flips_audit_json_path = cohort_csv_path.with_suffix(".flips_audit.json")
    flips_audit_json_path = Path(flips_audit_json_path)
    if not allow_non_canonical_source:
        verify_canonical_source_identity(source_sensitivity_md)
    flips = extract_flips_from_sensitivity_md(source_sensitivity_md)
    verify_expected_v2obr_cohort(flips)
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
