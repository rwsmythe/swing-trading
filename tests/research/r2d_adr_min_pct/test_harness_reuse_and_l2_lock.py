"""Discipline tests for R2-D: D2 harness reuse + R2-A harness immutability
+ L2 LOCK + cohort-validity.

R2-D is a re-execution of D2's 6-ruleset W-bottom comparison against a
DIFFERENT cohort (V2 OHLCV vcp.adr_min_pct +11 binding-variable flips),
distinct from both D2's bias-free S&P 500 cohort and R2-A's
vcp.tightness_days_required +16 selection-biased cohort. These tests verify:

  - R2-D does NOT modify D2's harness modules (REUSE verbatim per brief Section 10).
  - R2-D does NOT modify R2-A's cohort-extraction modules (FROZEN per brief Section 10).
  - R2-D modules do NOT import schwab / yfinance / swing.integrations
    (L2 LOCK preserved per CLAUDE.md gotchas + V2 reinforcement tests).
  - Cohort fixture exists with expected shape + scope.
  - Cohort selection method recorded explicitly per gotcha #33.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Section 5.3 D2 harness REUSE verbatim + R2-A modules FROZEN
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "rel_path",
    [
        # D2 6-ruleset harness (REUSE verbatim; same as R2-A)
        "research/harness/w_bottom_ruleset_comparison/__init__.py",
        "research/harness/w_bottom_ruleset_comparison/walkforward.py",
        "research/harness/w_bottom_ruleset_comparison/rulesets.py",
        "research/harness/w_bottom_ruleset_comparison/io.py",
        "research/harness/w_bottom_ruleset_comparison/run.py",
        "research/harness/double_bottom_w_backtest/cohort.py",
        # R2-A cohort-extraction modules (FROZEN; sibling-module strategy
        # per dispatch brief Section 1.2 LOCK)
        "research/harness/r2a_tightness_days_required/__init__.py",
        "research/harness/r2a_tightness_days_required/cohort_csv.py",
        "research/harness/r2a_tightness_days_required/regenerate_cohort.py",
    ],
)
def test_d2_and_r2a_harness_modules_unchanged_by_r2d(rel_path: str) -> None:
    """R2-D MUST NOT modify D2's or R2-A's harness modules; assert each
    touched file is byte-identical to its merge-base on `main` at the
    dispatch start.

    The brief Section 10 prohibits modifying D2 harness OR R2-A modules. If a
    future ship needs to extend these, the change is part of that arc's
    dispatch -- not a side-effect of R2-D.

    Pattern complement to R2-A's harness-reuse byte-stability test; this
    R2-D version extends the parametrize to include R2-A modules.
    """
    import subprocess
    abs_path = REPO_ROOT / rel_path
    assert abs_path.exists(), f"missing {rel_path}"
    try:
        proc = subprocess.run(
            ["git", "show", f"main:{rel_path}"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip("git not available")
    if proc.returncode != 0:
        pytest.skip(f"git show main:{rel_path} failed (likely shallow clone)")
    main_bytes = proc.stdout
    # Normalize line endings (CRLF on Windows working tree vs LF in git objects)
    main_normalized = main_bytes.replace(b"\r\n", b"\n")
    working_bytes = abs_path.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(working_bytes).hexdigest() == hashlib.sha256(
        main_normalized
    ).hexdigest(), (
        f"{rel_path} differs from main; R2-D must REUSE D2 + R2-A modules "
        f"verbatim (brief Section 10). If a deliberate change is required, "
        f"scope a separate dispatch."
    )


# ---------------------------------------------------------------------------
# Section 5.4 L2 LOCK (R2-D modules do NOT introduce schwab/yfinance imports)
# ---------------------------------------------------------------------------
_FORBIDDEN_IMPORT_PATTERNS = [
    r"\bimport\s+schwabdev\b",
    r"\bfrom\s+schwabdev\b",
    r"\bimport\s+yfinance\b",
    r"\bfrom\s+yfinance\b",
    r"\bfrom\s+swing\.integrations\.schwab\b",
    r"\bimport\s+swing\.integrations\.schwab\b",
]


@pytest.mark.parametrize(
    "rel_path",
    [
        "research/harness/r2d_adr_min_pct/__init__.py",
        "research/harness/r2d_adr_min_pct/cohort_csv.py",
        "research/harness/r2d_adr_min_pct/regenerate_cohort.py",
    ],
)
def test_r2d_module_no_schwab_or_yfinance_imports(rel_path: str) -> None:
    """L2 LOCK: R2-D modules MUST NOT import schwabdev / yfinance /
    swing.integrations.schwab. The dispatch is a research-branch artifact;
    no broker integration; no network calls at backtest time.

    Pattern complement to existing R2-A L2 LOCK tests + 5 BINDING tests
    at tests/research/test_aplus_v2_ohlcv_reader.py (V2 reader source-grep
    + import-graph sentinel + byte-checksum + signature lock + V2 source-grep).
    """
    abs_path = REPO_ROOT / rel_path
    src = abs_path.read_text(encoding="utf-8")
    for pat in _FORBIDDEN_IMPORT_PATTERNS:
        assert re.search(pat, src) is None, (
            f"{rel_path} contains forbidden L2-LOCK violation matching {pat!r}; "
            f"R2-D must not introduce broker/data-fetch integrations"
        )


# ---------------------------------------------------------------------------
# Section 5.2 Cohort-validity cross-check (per gotcha #33 third canonical application)
# ---------------------------------------------------------------------------
def test_r2d_cohort_fixture_exists_and_well_formed() -> None:
    """The R2-D cohort.json fixture exists, parses as JSON, has tickers
    matching the V2 sensitivity binding-variable flips (AMX/GLNG/STNG/XENE
    subset; post-recency-filter the cohort may be smaller -- gotcha #33
    cohort-validity discipline)."""
    fx_path = (
        REPO_ROOT
        / "tests/fixtures/research/r2d_adr_min_pct/cohort.json"
    )
    assert fx_path.exists(), f"R2-D fixture missing at {fx_path}"
    entries = json.loads(fx_path.read_text(encoding="utf-8"))
    assert isinstance(entries, list)
    # Tickers must be a subset of the 4 cohort tickers (post-recency-filter
    # may reduce; full cohort is AMX/GLNG/STNG/XENE).
    expected_superset = {"AMX", "GLNG", "STNG", "XENE"}
    tickers = {e["ticker"] for e in entries}
    assert tickers.issubset(expected_superset), (
        f"R2-D cohort tickers={tickers}; must be subset of {expected_superset} "
        f"(from V2 sensitivity vcp.adr_min_pct +11 watch->aplus flips at sp=2.0)"
    )


def test_r2d_cohort_fixture_shape_mirrors_d1() -> None:
    """The cohort.json entry shape MUST mirror D1's cohort.json (PrimaryVerdict
    serialization) so the same harness consumes it via load_cohort_fixture."""
    from research.harness.double_bottom_w_backtest.cohort import (
        PrimaryVerdict, load_cohort_fixture,
    )
    fx_path = (
        REPO_ROOT
        / "tests/fixtures/research/r2d_adr_min_pct/cohort.json"
    )
    verdicts = load_cohort_fixture(fx_path)
    # Round-trip: every entry yields a fully-constructed PrimaryVerdict
    assert all(isinstance(v, PrimaryVerdict) for v in verdicts)
    # All composite_score values >= 0.5 (canonical evaluation cohort filter)
    if verdicts:
        assert all(v.composite_score >= 0.5 for v in verdicts), (
            "R2-D canonical evaluation cohort is filtered to composite>=0.5; "
            "fixture must NOT contain sub-threshold entries"
        )


def test_r2d_cohort_selection_method_documented_in_brief() -> None:
    """Per gotcha #33: the R2-D dispatch brief must explicitly document
    cohort_selection_method='v2_binding_variable_flips' as a selection-biased
    cohort distinct from D2's bias-free cohort. Forward-binding lock against
    documentation drift.
    """
    brief = (
        REPO_ROOT
        / "docs/r2d-adr-min-pct-cohort-backtest-dispatch-brief.md"
    )
    assert brief.exists(), f"R2-D dispatch brief missing at {brief}"
    text = brief.read_text(encoding="utf-8")
    assert "v2_binding_variable_flips" in text, (
        "Dispatch brief must reference 'v2_binding_variable_flips' selection "
        "method (gotcha #33 cohort-validity-vs-verdict-criteria discipline)"
    )
    assert "selection-biased" in text, (
        "Dispatch brief must explicitly characterize R2-D cohort as "
        "selection-biased vs D2's bias-free cohort"
    )


def test_r2d_brief_documents_variable_distinction_from_r2a() -> None:
    """The R2-D brief must distinguish itself from R2-A by naming the
    different V2 binding variable explicitly (cross-cohort interpretation
    of results requires the reader to know R2-D tests adr_min_pct NOT
    tightness_days_required)."""
    brief = (
        REPO_ROOT
        / "docs/r2d-adr-min-pct-cohort-backtest-dispatch-brief.md"
    )
    text = brief.read_text(encoding="utf-8")
    assert "vcp.adr_min_pct" in text
    # Brief must reference R2-A so future readers see the cross-cohort framing
    assert "R2-A" in text or "r2a" in text


# ---------------------------------------------------------------------------
# Cohort CSV byte-stability (regression safety)
# ---------------------------------------------------------------------------
def test_r2d_cohort_csv_byte_stable() -> None:
    """The R2-D cohort CSV at exports/research/cohorts/ has a stable byte
    content: 4 rows + header + cohort_label column. Locks the file shape
    against accidental rewrites.
    """
    csv_path = (
        REPO_ROOT
        / "exports/research/cohorts/r2d_adr_min_pct_sp2_0.csv"
    )
    assert csv_path.exists()
    lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
    # Header + 4 data rows = 5 lines
    assert len(lines) == 5, f"expected 5 lines (header + 4 rows), got {len(lines)}"
    assert lines[0] == "ticker,asof_date,cohort_label"
    expected_tickers = {"AMX", "GLNG", "STNG", "XENE"}
    actual_tickers = {line.split(",")[0] for line in lines[1:]}
    assert actual_tickers == expected_tickers
    for line in lines[1:]:
        assert line.endswith(",r2d_vcp_adr_min_pct_sp2_0")
