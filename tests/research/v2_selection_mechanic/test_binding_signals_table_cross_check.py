"""Gotcha #34 first canonical application: BINDING_SIGNALS_TABLE cross-table verification.

Per V2-selection-mechanic dispatch brief Sec 4.4 BINDING discriminating
test: PROGRAMMATICALLY parses BOTH the V2 sensitivity SUMMARY TABLE
(lines 13-22 of the canonical source artifact) AND the Sensitivity
Matrix (lines 66+) and cross-verifies the 5 (variable, max_delta_aplus,
binding_sweep_point) tuples against the LOCKED BINDING_SIGNALS_TABLE
constant in `research/harness/v2_selection_mechanic/__init__.py`.

Convention LOCK (per dispatch brief Sec 2.3 first-crossing convention):
when multiple sweep_points in the Sensitivity Matrix yield the same
max delta_aplus for a given variable, the LOWEST sweep_point is locked
(applies to vcp.orderliness_max_bar_ratio where both sp=3.75 and sp=4.5
yield +1 delta_aplus).

Cross-table verification methodology (per gotcha #34 second canonical
application LOCK at investigation greenlight 2026-05-26 PM): the
SUMMARY TABLE's max_delta_aplus and the Sensitivity Matrix's delta_aplus
column agree exactly (the Matrix is the per-sweep-point breakdown of
the SUMMARY's headline). The drill-down sections' watch->aplus filter
counts have small gaps vs SUMMARY for 2 of 5 variables (per
NON_WATCH_TRANSITION_GAP_TABLE LOCK); this test focuses on the
SUMMARY-vs-Matrix cross-check which is the canonical brief-prescription
cross-table discipline.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from research.harness.v2_selection_mechanic import (
    BINDING_SIGNALS_TABLE,
    CANONICAL_SOURCE_PATH,
    CANONICAL_SOURCE_SHA256,
    CANONICAL_SOURCE_SIZE_BYTES,
    NON_WATCH_TRANSITION_GAP_TABLE,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_SOURCE = REPO_ROOT / CANONICAL_SOURCE_PATH


# -----------------------------------------------------------------------
# Source-artifact parsers (gotcha #34 cross-table verification primitives)
# -----------------------------------------------------------------------


def _parse_summary_table(md_text: str) -> dict[str, int]:
    """Parse the SUMMARY TABLE (Headline: Top Binding Variables section).

    Returns dict mapping variable_name -> max_delta_aplus. The SUMMARY
    TABLE is bounded by `## Headline: Top Binding Variables` heading and
    the next h2 heading (`## CRITERION DRIFT DETECTED` in V1).
    """
    headline = re.search(r"^## Headline: Top Binding Variables\s*$", md_text, re.MULTILINE)
    assert headline is not None, "SUMMARY TABLE Headline section missing"
    rest = md_text[headline.end():]
    next_h2 = re.search(r"^## ", rest, re.MULTILINE)
    section = rest[: next_h2.start() if next_h2 else None]
    out: dict[str, int] = {}
    for line in section.splitlines():
        line_s = line.strip()
        if not line_s.startswith("|"):
            continue
        if "---" in line_s:
            continue
        cols = [c.strip() for c in line_s.split("|")]
        cols = [c for c in cols if c != ""]
        if len(cols) != 2:
            continue
        if cols[0] == "variable_name":
            continue
        try:
            max_delta = int(cols[1])
        except ValueError:
            continue
        out[cols[0]] = max_delta
    return out


def _parse_sensitivity_matrix(md_text: str) -> list[dict[str, object]]:
    """Parse the Sensitivity Matrix (one row per (variable, sweep_point)).

    Returns list of dicts with keys: variable_name / kind / sweep_point /
    aplus_count / delta_aplus. Bounded by `## Sensitivity Matrix` heading
    and next h2 heading.
    """
    heading = re.search(r"^## Sensitivity Matrix\s*$", md_text, re.MULTILINE)
    assert heading is not None, "Sensitivity Matrix section missing"
    rest = md_text[heading.end():]
    next_h2 = re.search(r"^## ", rest, re.MULTILINE)
    section = rest[: next_h2.start() if next_h2 else None]
    rows: list[dict[str, object]] = []
    header_seen = False
    column_index: dict[str, int] | None = None
    for line in section.splitlines():
        line_s = line.strip()
        if not line_s.startswith("|"):
            continue
        if "---" in line_s:
            continue
        cols = [c.strip() for c in line_s.split("|")]
        cols = [c for c in cols if c != ""]
        if not header_seen:
            if cols and cols[0] == "variable_name":
                column_index = {name: i for i, name in enumerate(cols)}
                header_seen = True
            continue
        if column_index is None:
            continue
        if len(cols) < 8:
            continue
        try:
            row = {
                "variable_name": cols[column_index["variable_name"]],
                "kind": cols[column_index["kind"]],
                "sweep_point": float(cols[column_index["sweep_point"]]),
                "aplus_count": int(cols[column_index["aplus_count"]]),
                "delta_aplus": int(cols[column_index["delta_aplus"]]),
            }
        except (ValueError, KeyError, IndexError):
            continue
        rows.append(row)
    return rows


# -----------------------------------------------------------------------
# Discriminating tests
# -----------------------------------------------------------------------


def test_canonical_source_present_and_locked() -> None:
    """Source artifact SHA + size match the canonical lock."""
    import hashlib
    assert CANONICAL_SOURCE.exists(), f"missing source at {CANONICAL_SOURCE}"
    h = hashlib.sha256()
    with CANONICAL_SOURCE.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    assert h.hexdigest() == CANONICAL_SOURCE_SHA256
    assert CANONICAL_SOURCE.stat().st_size == CANONICAL_SOURCE_SIZE_BYTES


def test_summary_table_parses_5_v2_binding_variables() -> None:
    """Parse SUMMARY TABLE; expect exactly the 5 V2 binding variables."""
    text = CANONICAL_SOURCE.read_text(encoding="utf-8")
    summary = _parse_summary_table(text)
    expected = {
        "vcp.tightness_range_factor",
        "vcp.tightness_days_required",
        "vcp.adr_min_pct",
        "vcp.proximity_max_pct",
        "vcp.orderliness_max_bar_ratio",
    }
    assert set(summary.keys()) == expected, (
        f"SUMMARY TABLE has variables: {set(summary.keys())}; expected: {expected}"
    )


def test_summary_table_max_delta_aplus_lock() -> None:
    """SUMMARY TABLE max_delta_aplus values match BINDING_SIGNALS_TABLE."""
    text = CANONICAL_SOURCE.read_text(encoding="utf-8")
    summary = _parse_summary_table(text)
    for variable, max_delta, _ in BINDING_SIGNALS_TABLE:
        assert summary[variable] == max_delta, (
            f"SUMMARY TABLE {variable} = {summary[variable]}; "
            f"BINDING_SIGNALS_TABLE expects {max_delta}"
        )


def test_sensitivity_matrix_parses_all_5_binding_variables() -> None:
    """Sensitivity Matrix has rows for all 5 V2 binding variables."""
    text = CANONICAL_SOURCE.read_text(encoding="utf-8")
    matrix = _parse_sensitivity_matrix(text)
    variables_in_matrix = {row["variable_name"] for row in matrix}
    for variable, _, _ in BINDING_SIGNALS_TABLE:
        assert variable in variables_in_matrix, (
            f"Sensitivity Matrix missing variable: {variable}"
        )


def test_gotcha_34_cross_table_verification() -> None:
    """Gotcha #34 first canonical application BINDING test.

    For each variable in BINDING_SIGNALS_TABLE:
      1. Parse SUMMARY TABLE; assert max_delta_aplus matches
      2. Parse Sensitivity Matrix; find rows for that variable
      3. Identify the sweep_point(s) where delta_aplus == max_delta_aplus
      4. Assert the LOWEST such sweep_point (first crossing convention)
         matches the LOCKED binding_sweep_point
    """
    text = CANONICAL_SOURCE.read_text(encoding="utf-8")
    summary = _parse_summary_table(text)
    matrix = _parse_sensitivity_matrix(text)

    for variable, max_delta_aplus, expected_binding_sp in BINDING_SIGNALS_TABLE:
        # Step 1: SUMMARY TABLE agreement
        assert summary[variable] == max_delta_aplus, (
            f"SUMMARY TABLE {variable} = {summary[variable]}; expected {max_delta_aplus}"
        )
        # Steps 2-4: Sensitivity Matrix derivation
        variable_rows = [
            r for r in matrix if r["variable_name"] == variable
        ]
        assert variable_rows, (
            f"Sensitivity Matrix has no rows for {variable}"
        )
        max_sp_candidates = [
            r["sweep_point"]
            for r in variable_rows
            if r["delta_aplus"] == max_delta_aplus
        ]
        assert max_sp_candidates, (
            f"Sensitivity Matrix has no row for {variable} with "
            f"delta_aplus == {max_delta_aplus}"
        )
        derived_binding_sp = min(max_sp_candidates)
        # Float equality is safe here because all binding sweep_points
        # are clean decimal values (1.005, 1.0, 2.0, 7.5, 3.75) and
        # parsed via float() from canonical-source strings of the same form.
        assert derived_binding_sp == expected_binding_sp, (
            f"{variable}: derived first-crossing sweep_point "
            f"{derived_binding_sp} != LOCKED {expected_binding_sp}"
        )


def test_orderliness_first_crossing_lock_sp_3_75_not_sp_4_5() -> None:
    """Discriminating test for vcp.orderliness_max_bar_ratio first-crossing LOCK.

    Both sp=3.75 AND sp=4.5 yield +1 delta_aplus. The LOCK is sp=3.75
    (lowest; first crossing convention). This test verifies that BOTH
    sweep_points are present in the Matrix AND that sp=3.75 is selected.
    """
    text = CANONICAL_SOURCE.read_text(encoding="utf-8")
    matrix = _parse_sensitivity_matrix(text)
    orderliness_rows = [
        r for r in matrix if r["variable_name"] == "vcp.orderliness_max_bar_ratio"
    ]
    plus_one_sps = [
        r["sweep_point"] for r in orderliness_rows if r["delta_aplus"] == 1
    ]
    assert sorted(plus_one_sps) == [3.75, 4.5], (
        f"Expected vcp.orderliness_max_bar_ratio +1 delta at exactly "
        f"sp=3.75 AND sp=4.5; got {sorted(plus_one_sps)}"
    )
    # Verify LOCK chooses the LOWER (first crossing)
    locked_sp = next(
        sp for var, _, sp in BINDING_SIGNALS_TABLE
        if var == "vcp.orderliness_max_bar_ratio"
    )
    assert locked_sp == min(plus_one_sps) == 3.75


def test_binding_signals_table_has_5_entries() -> None:
    """LOCK: exactly 5 V2 binding variables in scope (per dispatch brief Q2)."""
    assert len(BINDING_SIGNALS_TABLE) == 5
    # Variable name uniqueness
    names = [v[0] for v in BINDING_SIGNALS_TABLE]
    assert len(set(names)) == 5


def test_non_watch_transition_gap_table_lock() -> None:
    """Gotcha #34 SECOND canonical application: per-variable drill-down gap LOCK.

    Validates the LOCKed per-variable non-watch-transition gap (SUMMARY -
    drill-down watch->aplus count). LOCKs operator-paired finding at
    investigation greenlight 2026-05-26 PM: 11% / 6% / 0% / 0% / 0%.
    """
    expected_gaps = {
        "vcp.tightness_range_factor": (75, 67, 8),
        "vcp.tightness_days_required": (16, 15, 1),
        "vcp.adr_min_pct": (11, 11, 0),
        "vcp.proximity_max_pct": (5, 5, 0),
        "vcp.orderliness_max_bar_ratio": (1, 1, 0),
    }
    for variable, max_delta, drill_count, gap, gap_pct in NON_WATCH_TRANSITION_GAP_TABLE:
        exp = expected_gaps[variable]
        assert (max_delta, drill_count, gap) == exp, (
            f"NON_WATCH_TRANSITION_GAP_TABLE {variable} = "
            f"({max_delta}, {drill_count}, {gap}); expected {exp}"
        )
        # gap_pct is gap / max_delta * 100 (or 0 if max_delta == 0)
        if max_delta > 0:
            assert abs(gap_pct - gap / max_delta * 100) < 1e-9


def test_non_watch_transition_gap_matches_sibling_modules() -> None:
    """Per-variable drill_count matches each sibling module's EXPECTED_FLIP_COUNT.

    Cross-checks NON_WATCH_TRANSITION_GAP_TABLE drill_down counts against
    the sibling module LOCKs already in place (R2-A + R2-D +
    v2_tightness_range_factor + v2_proximity_max_pct +
    v2_orderliness_max_bar_ratio).
    """
    from research.harness.r2a_tightness_days_required.cohort_csv import (
        EXPECTED_FLIP_COUNT as R2A_COUNT,
    )
    from research.harness.r2d_adr_min_pct.cohort_csv import (
        EXPECTED_FLIP_COUNT as R2D_COUNT,
    )
    from research.harness.v2_orderliness_max_bar_ratio.cohort_csv import (
        EXPECTED_FLIP_COUNT as V2OBR_COUNT,
    )
    from research.harness.v2_proximity_max_pct.cohort_csv import (
        EXPECTED_FLIP_COUNT as V2PMP_COUNT,
    )
    from research.harness.v2_tightness_range_factor.cohort_csv import (
        EXPECTED_FLIP_COUNT as V2TRF_COUNT,
    )

    by_variable = {entry[0]: entry[2] for entry in NON_WATCH_TRANSITION_GAP_TABLE}
    assert by_variable["vcp.tightness_range_factor"] == V2TRF_COUNT
    assert by_variable["vcp.tightness_days_required"] == R2A_COUNT
    assert by_variable["vcp.adr_min_pct"] == R2D_COUNT
    assert by_variable["vcp.proximity_max_pct"] == V2PMP_COUNT
    assert by_variable["vcp.orderliness_max_bar_ratio"] == V2OBR_COUNT
